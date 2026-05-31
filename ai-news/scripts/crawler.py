#!/usr/bin/env python3
"""
每日文献爬虫 — 五个代谢物节点 (Butyrate, Bile Acids, Tryptophan, Polyamines, B12)
数据源: PubMed (E-utilities API) + bioRxiv (API)
过滤: 排除预警期刊/普刊，仅保留权威学术来源
"""

import json
import os
import sys
import time
import hashlib
import re
from datetime import datetime, timedelta
from urllib.parse import quote
from xml.etree import ElementTree as ET

import requests
import feedparser
from bs4 import BeautifulSoup

# ==================== 配置 ====================

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
RAW_ARTICLES_FILE = os.path.join(DATA_DIR, "raw_articles.json")

# PubMed E-utilities 配置 (免费，无需 API Key)
PUBMED_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
PUBMED_SEARCH_URL = f"{PUBMED_BASE}/esearch.fcgi"
PUBMED_FETCH_URL = f"{PUBMED_BASE}/efetch.fcgi"

# 扩展后的 PubMed 检索式 — 三类节点：代谢物、维生素、菌株
SEARCH_QUERIES = {
    # ============ SCFA 亚类 ============
    "Butyrate": (
        '(butyrate OR butyric OR butyryl-CoA OR butyrate-producing) '
        'AND (gut OR intestinal OR colon OR colonic) '
        'AND (microbiome OR microbiota OR "gut microbiota" OR bacteria)'
    ),
    "Propionate": (
        '(propionate OR propionic OR "methylmalonyl-CoA" OR succinate-to-propionate) '
        'AND (gut OR intestinal OR colon OR colonic) '
        'AND (microbiome OR microbiota OR bacteria)'
    ),
    "Acetate": (
        '(acetate OR acetic OR "acetyl-CoA" OR acetogenic) '
        'AND (gut OR intestinal OR colon OR colonic) '
        'AND (microbiome OR microbiota OR bacteria)'
    ),
    "Branched SCFAs": (
        '(isobutyrate OR isovalerate OR valerate OR "branched-chain fatty acid" OR BCFA) '
        'AND (gut OR intestinal OR colon) '
        'AND (microbiome OR microbiota OR bacteria)'
    ),
    # ============ 胆汁酸 ============
    "Bile Acids": (
        '("bile acid" OR "bile acids" OR FXR OR TGR5 '
        'OR hyodeoxycholic OR HDCA OR obeticholic) '
        'AND (gut OR intestinal OR ileum OR colon) '
        'AND (microbiome OR microbiota OR bacteria)'
    ),
    # ============ 色氨酸代谢物 ============
    "Tryptophan Metabolites": (
        '(tryptophan OR indole OR kynurenine OR "AhR" '
        'OR "aryl hydrocarbon receptor" OR indole-3-propionic OR IPA) '
        'AND (gut OR intestinal OR colon) '
        'AND (microbiome OR microbiota OR metabolism)'
    ),
    # ============ 多胺 ============
    "Polyamines": (
        '(polyamine OR spermidine OR spermine OR putrescine OR cadaverine '
        'OR ornithine decarboxylase) '
        'AND (gut OR intestinal OR colon) '
        'AND (microbiome OR microbiota OR bacteria)'
    ),
    # ============ 维生素家族 ============
    "Vitamin B12": (
        '("vitamin B12" OR cobalamin OR adenosylcobalamin '
        'OR "methylmalonyl-CoA mutase") '
        'AND (gut OR intestinal OR colon) '
        'AND (microbiome OR microbiota OR bacteria)'
    ),
    "Folate/B9": (
        '(folate OR "folic acid" OR "vitamin B9" OR tetrahydrofolate '
        'OR "one-carbon metabolism" OR "methyl donor" OR MTHFR) '
        'AND (gut OR intestinal OR colon) '
        'AND (microbiome OR microbiota OR bacteria)'
    ),
    "Riboflavin/B2": (
        '(riboflavin OR "vitamin B2" OR FAD OR FMN OR flavin) '
        'AND (gut OR intestinal OR colon) '
        'AND (microbiome OR microbiota OR bacteria)'
    ),
    "Biotin/B7": (
        '(biotin OR "vitamin B7" OR biotinylation OR biotinidase) '
        'AND (gut OR intestinal OR colon) '
        'AND (microbiome OR microbiota OR bacteria)'
    ),
    "Vitamin A/Retinoic Acid": (
        '("vitamin A" OR retinoic OR retinol OR RAR OR RXR '
        'OR "retinoic acid receptor") '
        'AND (gut OR intestinal OR colon) '
        'AND (microbiome OR microbiota OR bacteria OR immune)'
    ),
    "Vitamin D": (
        '("vitamin D" OR calcitriol OR "VDR" OR "vitamin D receptor" '
        'OR cholecalciferol) '
        'AND (gut OR intestinal OR colon) '
        'AND (microbiome OR microbiota OR bacteria OR immune)'
    ),
    "B-Vitamins (B1/B3/B5/B6)": (
        '(thiamine OR "vitamin B1" OR niacin OR "vitamin B3" OR NAD '
        'OR pantothenate OR "vitamin B5" OR CoA OR pyridoxine OR "vitamin B6") '
        'AND (gut OR intestinal OR colon) '
        'AND (microbiome OR microbiota OR bacteria)'
    ),
    # ============ 其他代谢物 ============
    "Lactate": (
        '(lactate OR lactic OR "lactic acid" OR D-lactate OR L-lactate '
        'OR lactate-utilizing) '
        'AND (gut OR intestinal OR colon) '
        'AND (microbiome OR microbiota OR bacteria)'
    ),
    "Succinate": (
        '(succinate OR succinic OR "succinate accumulation" '
        'OR succinate-producing OR succinate-consuming) '
        'AND (gut OR intestinal OR colon) '
        'AND (microbiome OR microbiota OR bacteria)'
    ),
    "GABA/Glutamate": (
        '(GABA OR gamma-aminobutyric OR glutamate OR glutamic '
        'OR "gut-brain axis" OR gadB) '
        'AND (gut OR intestinal OR colon) '
        'AND (microbiome OR microbiota OR bacteria)'
    ),
    # ============ 菌株/分类学 ============
    "Phascolarctobacterium": (
        '(Phascolarctobacterium OR "P. succinatutens" OR succinatutens) '
        'AND (gut OR intestinal OR succinate OR propionate)'
    ),
    "Lactobacillus": (
        '(Lactobacillus OR Lactiplantibacillus OR Limosilactobacillus '
        'OR Ligilactobacillus) '
        'AND (gut OR intestinal OR colon OR porcine OR piglet) '
        'AND (microbiome OR microbiota OR probiotic OR SCFA)'
    ),
    "Bifidobacterium": (
        '(Bifidobacterium OR Bifidobacteriales) '
        'AND (gut OR intestinal OR colon) '
        'AND (microbiome OR microbiota OR probiotic OR acetate)'
    ),
    "Bacteroides": (
        '(Bacteroides OR Bacteroidetes OR Bacteroidota) '
        'AND (gut OR intestinal OR colon) '
        'AND (microbiome OR microbiota OR polysaccharide OR propionate)'
    ),
    "Clostridium": (
        '(Clostridium OR Clostridiales OR Clostridia) '
        'AND (gut OR intestinal OR colon) '
        'AND (microbiome OR microbiota OR butyrate OR SCFA)'
    ),
    "Prevotella": (
        '(Prevotella OR Prevotellaceae) '
        'AND (gut OR intestinal OR colon) '
        'AND (microbiome OR microbiota OR porcine OR succinate)'
    ),
    "Akkermansia": (
        '(Akkermansia OR "A. muciniphila" OR muciniphila) '
        'AND (gut OR intestinal OR colon) '
        'AND (microbiome OR microbiota OR mucin OR barrier)'
    ),
    "Faecalibacterium": (
        '(Faecalibacterium OR "F. prausnitzii" OR prausnitzii) '
        'AND (gut OR intestinal OR colon) '
        'AND (microbiome OR microbiota OR butyrate OR anti-inflammatory)'
    ),
}

# 父级分组 — 子节点自动归入父组，前端可大类筛选
NODE_GROUPS = {
    "SCFAs": ["Butyrate", "Propionate", "Acetate", "Branched SCFAs"],
    "Vitamin B Family": ["Vitamin B12", "Folate/B9", "Riboflavin/B2", "Biotin/B7",
                          "B-Vitamins (B1/B3/B5/B6)"],
    "Fat-Soluble Vitamins": ["Vitamin A/Retinoic Acid", "Vitamin D"],
    "Gut Strains": ["Phascolarctobacterium", "Lactobacillus", "Bifidobacterium",
                    "Bacteroides", "Clostridium", "Prevotella",
                    "Akkermansia", "Faecalibacterium"],
}


def add_parent_nodes(nodes: list[str]) -> list[str]:
    """给定细粒度节点列表，自动补入父级分组标签"""
    expanded = list(nodes)
    for parent, children in NODE_GROUPS.items():
        if any(child in nodes for child in children) and parent not in expanded:
            expanded.append(parent)
    return expanded


# 权威期刊白名单
REPUTABLE_JOURNALS = [
    "Nature", "Science", "Cell",
    "Nature Microbiology", "Nature Communications", "Nature Medicine",
    "Cell Host & Microbe", "Cell Metabolism", "Cell Reports",
    "Gut Microbes", "Microbiome", "ISME Journal", "ISME Communications",
    "Gastroenterology", "Gut", "Hepatology",
    "mBio", "mSystems", "Microbiology Spectrum",
    "eLife", "PNAS", "PLOS Biology",
    "EMBO Journal", "EMBO Reports",
    "Nucleic Acids Research", "Genome Biology",
    "Microbial Genomics", "Environmental Microbiology",
    "Applied and Environmental Microbiology",
    "Journal of Biological Chemistry", "Molecular Systems Biology",
    "Current Biology", "BMC Biology",
    "FEMS Microbiology Ecology", "FEMS Microbiology Reviews",
    "Trends in Microbiology", "Trends in Biotechnology",
    "Annual Review of Microbiology", "Annual Review of Nutrition",
    "British Journal of Nutrition", "Journal of Nutrition",
    "American Journal of Clinical Nutrition",
    "Animal Microbiome", "Animal Nutrition",
    "Frontiers in Microbiology", "npj Biofilms and Microbiomes",
]

# 掠夺性/预警期刊黑名单关键词
PREDATORY_KEYWORDS = [
    "Hindawi", "MDPI", "PLOS ONE",
    "Medicine (United States)",
    "Cureus", "Heliyon",
    "International Journal of Molecular Sciences",
    "World Journal of",
    "Scientific Reports",
]

HEADERS = {
    "User-Agent": "AcademicLiteratureCrawler/1.0 (mailto:research@example.com)",
}
TIMEOUT = 30
SEARCH_DAYS = 7


# ==================== 工具函数 ====================

def make_id(title: str, source: str) -> str:
    return hashlib.sha256(f"{title}|{source}".encode("utf-8")).hexdigest()[:12]


def clean_html(text: str) -> str:
    if not text:
        return ""
    return " ".join(BeautifulSoup(text, "html.parser")
                    .get_text(separator=" ", strip=True).split())


def is_reputable(journal_name: str) -> bool:
    """期刊权威性检查"""
    jn = journal_name.lower()
    for kw in PREDATORY_KEYWORDS:
        if kw.lower() in jn:
            return False
    for good in REPUTABLE_JOURNALS:
        if good.lower() in jn:
            return True
    # 不在任何名单中：标记为待评估
    return True


def assign_nodes(title: str, abstract: str) -> list[str]:
    """Assign co-metabolism + strain nodes. Requires node keyword + gut/microbiome context.
    Covers: SCFAs, Bile Acids, Tryptophan, Polyamines, Vitamins (B1-B12, A, D),
    Lactate, Succinate, GABA/Glutamate, and 8+ gut bacterial taxa."""

    text = (title + " " + abstract).lower()

    # Must have gut/microbiome context (relaxed for strain queries where papers discuss pure genomics)
    gut_context = ["gut", "intestine", "intestinal", "colon", "colonic",
                   "microbiome", "microbiota", "fecal", "faecal", "cecal", "cecum"]
    has_gut = any(kw in text for kw in gut_context)

    nodes = []
    checks = [
        # ======== SCFA 亚类 ========
        ("Butyrate", ["butyrate", "butyric", "butyryl-coa", "butyryl coa",
                      "butyrate-producing", "butyrate producing"]),
        ("Propionate", ["propionate", "propionic", "methylmalonyl-coa", "methylmalonyl coa",
                        "succinate-to-propionate", "succinate to propionate"]),
        ("Acetate", ["acetate", "acetic", "acetyl-coa", "acetyl coa", "acetogenic",
                     "acetogen", "acetogenesis"]),
        ("Branched SCFAs", ["isobutyrate", "isovalerate", "valerate", "branched-chain fatty acid",
                            "branched chain fatty acid", "bcfa"]),
        # ======== 胆汁酸 ========
        ("Bile Acids", ["bile acid", "fxr", "tgr5", "hyodeoxycholic", "hdca", "obeticholic",
                        "farnesoid x receptor", "bile salt", "bsep", "ibat", "asbt"]),
        # ======== 色氨酸代谢物 ========
        ("Tryptophan Metabolites", ["tryptophan", "indole", "kynurenine", "aryl hydrocarbon",
                                    "ahr", "indole-3", "ipa", "indoleacrylic"]),
        # ======== 多胺 ========
        ("Polyamines", ["polyamine", "spermidine", "spermine", "putrescine", "cadaverine",
                        "ornithine decarboxylase", "agmatine"]),
        # ======== 维生素家族 ========
        ("Vitamin B12", ["vitamin b12", "cobalamin", "adenosylcobalamin",
                         "methylmalonyl-coa mutase"]),
        ("Folate/B9", ["folate", "folic acid", "vitamin b9", "tetrahydrofolate",
                       "methyl donor", "mthfr", "one-carbon metabolism",
                       "one carbon metabolism", "dhfr"]),
        ("Riboflavin/B2", ["riboflavin", "vitamin b2", "fad", "fmn", "flavin",
                           "flavoprotein"]),
        ("Biotin/B7", ["biotin", "vitamin b7", "biotinylation", "biotinidase",
                       "biotin-dependent"]),
        ("Vitamin A/Retinoic Acid", ["vitamin a", "retinoic", "retinol", "rar", "rxr",
                                     "retinoic acid receptor", "retinaldehyde"]),
        ("Vitamin D", ["vitamin d", "calcitriol", "vitamin d receptor", "vdr",
                       "cholecalciferol", "calcidiol"]),
        ("B-Vitamins (B1/B3/B5/B6)", ["thiamine", "vitamin b1", "niacin", "vitamin b3",
                                       "nad", "pantothenate", "vitamin b5", "coa",
                                       "pyridoxine", "vitamin b6", "pyridoxal"]),
        # ======== 其他代谢物 ========
        ("Lactate", ["lactate", "lactic acid", "lactate-utilizing", "lactate producing",
                     "d-lactate", "l-lactate"]),
        ("Succinate", ["succinate", "succinic", "succinate accumulation",
                       "succinate-producing", "succinate consuming"]),
        ("GABA/Glutamate", ["gaba", "gamma-aminobutyric", "glutamate", "glutamic",
                            "gut-brain axis", "gadb", "glutamate decarboxylase"]),
        # ======== 菌株/分类学 ========
        ("Phascolarctobacterium", ["phascolarctobacterium", "p. succinatutens",
                                   "succinatutens"]),
        ("Lactobacillus", ["lactobacillus", "lactiplantibacillus", "limosilactobacillus",
                           "ligilactobacillus", "lactobacilli"]),
        ("Bifidobacterium", ["bifidobacterium", "bifidobacteriales", "bifidobacteria"]),
        ("Bacteroides", ["bacteroides", "bacteroidetes", "bacteroidota",
                         "bacteroidales"]),
        ("Clostridium", ["clostridium", "clostridiales", "clostridia",
                         "clostridial"]),
        ("Prevotella", ["prevotella", "prevotellaceae"]),
        ("Akkermansia", ["akkermansia", "a. muciniphila", "muciniphila"]),
        ("Faecalibacterium", ["faecalibacterium", "f. prausnitzii", "prausnitzii"]),
    ]
    for node, keywords in checks:
        if any(kw in text for kw in keywords):
            nodes.append(node)

    # Gut context required for metabolite papers; relaxed for well-known gut taxa
    gut_taxa = {"Phascolarctobacterium", "Akkermansia", "Faecalibacterium",
                "Bacteroides", "Prevotella", "Clostridium",
                "Lactobacillus", "Bifidobacterium"}
    if not has_gut and not (set(nodes) & gut_taxa):
        return []
    return nodes


# ==================== PubMed ====================

def search_pubmed(query: str, max_results: int = 20) -> list[str]:
    """搜索 PubMed，返回 PMID 列表"""
    params = {
        "db": "pubmed", "term": query,
        "retmax": max_results, "retmode": "json", "sort": "date",
        "datetype": "pdat",
        "mindate": (datetime.now() - timedelta(days=SEARCH_DAYS)).strftime("%Y/%m/%d"),
        "maxdate": datetime.now().strftime("%Y/%m/%d"),
    }
    try:
        resp = requests.get(PUBMED_SEARCH_URL, params=params,
                           headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()
        return resp.json().get("esearchresult", {}).get("idlist", [])
    except Exception as e:
        print(f"    PubMed search error: {e}")
        return []


def fetch_pubmed_details(pmids: list[str]) -> list[dict]:
    """获取 PubMed 文章详情"""
    if not pmids:
        return []
    params = {"db": "pubmed", "id": ",".join(pmids),
              "retmode": "xml", "rettype": "abstract"}
    try:
        resp = requests.get(PUBMED_FETCH_URL, params=params,
                           headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
        articles = []
        for art_elem in root.findall(".//PubmedArticle"):
            try:
                med = art_elem.find(".//MedlineCitation")
                article = med.find(".//Article")
                if article is None:
                    continue

                title_elem = article.find(".//ArticleTitle")
                title = "".join(title_elem.itertext()) if title_elem is not None else ""

                abst_elem = article.find(".//Abstract/AbstractText")
                abstract = "".join(abst_elem.itertext()) if abst_elem is not None else ""

                jn_elem = article.find(".//Journal/Title")
                journal = jn_elem.text if jn_elem is not None else ""

                doi_elem = article.find(".//ELocationID[@EIdType='doi']")
                doi = doi_elem.text if doi_elem is not None else ""

                pmid_elem = med.find(".//PMID")
                pmid = pmid_elem.text if pmid_elem is not None else ""

                pub_date_elem = article.find(".//Journal/JournalIssue/PubDate")
                pub_date = ""
                if pub_date_elem is not None:
                    y = pub_date_elem.findtext("Year", "")
                    m = pub_date_elem.findtext("Month", "")
                    d = pub_date_elem.findtext("Day", "01")
                    pub_date = f"{y}-{m}-{d}"

                authors = []
                for au in article.findall(".//AuthorList/Author"):
                    ln = au.findtext("LastName", "")
                    ini = au.findtext("Initials", "")
                    if ln:
                        authors.append(f"{ln} {ini}")

                url = f"https://doi.org/{quote(doi, safe='')}" if doi else f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
                # Multi-backup links
                links = []
                if doi:
                    links.append({"type": "doi", "label": "DOI", "url": url})
                if pmid:
                    links.append({"type": "pubmed", "label": "PubMed", "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"})

                articles.append({
                    "journal": journal, "doi": doi, "pmid": pmid,
                    "first_author": authors[0] if authors else "",
                    "url": url, "title": title.strip(),
                    "abstract": abstract.strip()[:800],
                    "pub_date": pub_date, "source": "PubMed",
                    "links": links if links else [],
                })
            except Exception:
                continue
        return articles
    except Exception as e:
        print(f"    PubMed fetch error: {e}")
        return []


# ==================== bioRxiv ====================

def fetch_biorxiv() -> list[dict]:
    """Fetch bioRxiv preprints from microbiology subject RSS"""
    articles = []
    rss_url = "https://connect.biorxiv.org/biorxiv_xml.php?subject=microbiology"
    try:
        feed = feedparser.parse(rss_url)
        for entry in feed.entries[:30]:
            title = entry.get("title", "").strip()
            abstract = entry.get("summary", "").strip()
            abstract = clean_html(abstract)
            nodes = assign_nodes(title, abstract)
            if not nodes:
                continue
            link = entry.get("link", "")
            pub_date = entry.get("published", "")
            articles.append({
                "journal": "bioRxiv (microbiology)",
                "doi": "", "pmid": "",
                "first_author": "",
                "url": link,
                "title": title[:300], "abstract": abstract[:800],
                "pub_date": pub_date, "source": "bioRxiv",
                "links": [{"type": "biorxiv", "label": "bioRxiv", "url": link}],
            })
    except Exception as e:
        print(f"    bioRxiv error: {e}")
    return articles


# ==================== 主流程 ====================

def main():
    print("=" * 60)
    print("  Co-Metabolism Literature Crawler (25 Nodes)")
    print(f"  Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    all_articles = []

    # PubMed
    print("\n[PubMed]")
    for node_name, query in SEARCH_QUERIES.items():
        print(f"  [{node_name}]")
        pmids = search_pubmed(query)
        if pmids:
            details = fetch_pubmed_details(pmids)
            for art in details:
                art["query_node"] = node_name
            all_articles.extend(details)
            print(f"    {len(details)} papers")
        else:
            print(f"    No results")
        time.sleep(0.4)

    # bioRxiv
    print("\n[bioRxiv]")
    biorxiv_articles = fetch_biorxiv()
    print(f"    {len(biorxiv_articles)} preprints")
    all_articles.extend(biorxiv_articles)

    # 去重
    seen = {}
    unique = []
    for art in all_articles:
        key = art.get("title", "")[:80]
        if hashlib.md5(key.encode()).hexdigest() not in seen:
            seen[hashlib.md5(key.encode()).hexdigest()] = True
            unique.append(art)
    print(f"\n  Dedup: {len(all_articles)} -> {len(unique)}")

    # 期刊过滤
    filtered = []
    rejected = 0
    for art in unique:
        jn = art.get("journal", "")
        if is_reputable(jn):
            filtered.append(art)
        else:
            rejected += 1
    print(f"  Journal filter: {len(filtered)} kept, {rejected} rejected")

    # 统一格式 + 剔除无节点匹配的论文
    articles = []
    for art in filtered:
        nodes = assign_nodes(art.get("title", ""), art.get("abstract", ""))
        if not nodes:
            continue  # Skip papers not matching any of the five nodes
        articles.append({
            "id": make_id(art.get("title", ""), art.get("source", "")),
            "title": art.get("title", ""),
            "url": art.get("url", ""),
            "abstract": art.get("abstract", "")[:500],
            "journal": art.get("journal", ""),
            "doi": art.get("doi", ""),
            "pmid": art.get("pmid", ""),
            "first_author": art.get("first_author", ""),
            "pub_date": art.get("pub_date", ""),
            "source": art.get("source", ""),
            "nodes": add_parent_nodes(nodes),
            "crawled_at": datetime.now().isoformat(),
        })

    articles.sort(key=lambda a: a.get("pub_date", ""), reverse=True)

    # 统计
    node_counts = {}
    for art in articles:
        for n in art["nodes"]:
            node_counts[n] = node_counts.get(n, 0) + 1
    print(f"\n  Node distribution:")
    # Show SCFA sub-nodes first, then bile acids/tryptophan, then vitamins, then strains
    priority_nodes = [
        "Butyrate", "Propionate", "Acetate", "Branched SCFAs",
        "Bile Acids", "Tryptophan Metabolites", "Polyamines",
        "Vitamin B12", "Folate/B9", "Riboflavin/B2", "Biotin/B7",
        "Vitamin A/Retinoic Acid", "Vitamin D", "B-Vitamins (B1/B3/B5/B6)",
        "Lactate", "Succinate", "GABA/Glutamate",
        "Phascolarctobacterium", "Lactobacillus", "Bifidobacterium",
        "Bacteroides", "Clostridium", "Prevotella",
        "Akkermansia", "Faecalibacterium",
    ]
    for node in priority_nodes:
        if node_counts.get(node, 0) > 0:
            print(f"    {node}: {node_counts[node]}")
    # catch any unexpected nodes
    for node, count in sorted(node_counts.items()):
        if node not in priority_nodes:
            print(f"    {node}: {count}")

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(RAW_ARTICLES_FILE, "w", encoding="utf-8") as f:
        json.dump(articles, f, ensure_ascii=False, indent=2)
    print(f"\n  Saved: {len(articles)} articles to {RAW_ARTICLES_FILE}")

    with open(os.path.join(DATA_DIR, "crawl_count.txt"), "w") as f:
        f.write(str(len(articles)))
    return len(articles)


if __name__ == "__main__":
    sys.exit(0 if main() >= 0 else 1)
