#!/usr/bin/env python3
"""
Broad OA literature crawler — covers free SCI journals via Europe PMC + Semantic Scholar.
No node-specific queries; uses broad topical searches with open-access filters.
"""
import json, os, sys, time, hashlib
from datetime import datetime, timedelta
from urllib.parse import quote
import requests

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ai-news", "data")
HEADERS = {"User-Agent": "bioHot-Curator/1.0 (mailto:research@example.com)"}
TIMEOUT = 30
SEARCH_DAYS = 7

# Broad bioinformatics queries — one per lightweight channel
CHANNEL_QUERIES = {
    "computational-genomics": [
        '(genomics OR genome) AND (computational OR bioinformatics OR algorithm) AND (variant OR assembly OR annotation OR GWAS)',
        '(epigenomics OR epigenetics) AND (methylation OR "histone modification" OR chromatin) AND (computational OR tool OR pipeline)',
    ],
    "metagenomics-informatics": [
        '(metagenomics OR metagenome) AND (assembly OR binning OR "taxonomic profiling" OR "functional annotation")',
        '("microbiome-wide association" OR MWAS) AND (method OR tool OR pipeline)',
    ],
    "structural-bioinformatics": [
        '("protein structure" OR AlphaFold OR "molecular dynamics" OR docking) AND (prediction OR simulation)',
        '("structure-based" OR "rational design") AND (protein OR enzyme OR antibody)',
    ],
    "systems-biology": [
        '("gene regulatory network" OR GRN) AND (inference OR reconstruction)',
        '("flux balance analysis" OR FBA OR "metabolic model") AND (genome-scale OR constraint-based)',
    ],
    "ml-biology": [
        '("machine learning" OR "deep learning" OR "graph neural network") AND (protein OR genome OR sequence) AND (method OR tool)',
        '("language model" OR LLM) AND (protein OR DNA OR RNA OR biological)',
    ],
    "single-cell-omics": [
        '("single-cell" OR "single cell") AND (RNA-seq OR ATAC-seq OR multiome) AND (method OR tool OR algorithm)',
        '("spatial transcriptomics" OR "spatial genomics") AND (computation OR analysis)',
    ],
    "databases-knowledge-graphs": [
        '("biological database" OR "knowledge graph" OR ontology) AND (resource OR update OR release)',
        '("FAIR data" OR "data integration") AND (biology OR life sciences)',
    ],
    "ai-drug-discovery": [
        '("drug discovery" OR "virtual screening") AND ("machine learning" OR "deep learning" OR AI)',
        '("ADMET" OR "drug repurposing") AND (prediction OR computational)',
    ],
}

def fetch_europepmc(query: str, max_results: int = 20) -> list:
    """Fetch OA papers from Europe PMC."""
    articles = []
    base = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
    params = {
        "query": f"({query}) AND (OPEN_ACCESS:Y)",
        "format": "json", "pageSize": max_results,
        "sort": "FIRST_PUBLICATION_DATE desc",
        "resultType": "core",
    }
    try:
        resp = requests.get(base, params=params, headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()
        for item in resp.json().get("resultList", {}).get("result", []):
            title = (item.get("title") or "").strip()
            abstract = (item.get("abstractText") or "")[:600]
            if not title: continue
            doi = item.get("doi", "")
            pmid = str(item.get("pmid", ""))
            journal = item.get("journalTitle", "") or item.get("bookOrReportDetails", {}).get("publisher", "")
            pub_date = item.get("firstPublicationDate", "")
            url = f"https://doi.org/{quote(doi, safe='')}" if doi else f"https://europepmc.org/article/MED/{pmid}"
            links = []
            if doi: links.append({"type": "doi", "label": "DOI", "url": url})
            if pmid: links.append({"type": "pubmed", "label": "PubMed", "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"})
            articles.append({
                "id": hashlib.sha256(f"{title}|europepmc".encode()).hexdigest()[:12],
                "title": title[:300], "abstract": abstract, "journal": journal,
                "doi": doi, "pmid": pmid, "first_author": "",
                "pub_date": pub_date, "source": "Europe PMC", "url": url, "links": links,
            })
    except Exception as e:
        print(f"    Europe PMC error: {e}")
    return articles

def fetch_semantic_scholar(query: str, max_results: int = 15) -> list:
    """Fetch OA papers from Semantic Scholar API."""
    articles = []
    base = "https://api.semanticscholar.org/graph/v1/paper/search"
    fields = "title,abstract,year,externalIds,journal,publicationDate,authors,openAccessPdf"
    params = {"query": query, "limit": max_results, "fields": fields, "openAccessPdf": ""}
    try:
        resp = requests.get(base, params=params, headers=HEADERS, timeout=TIMEOUT)
        if resp.status_code == 429:
            time.sleep(5); return articles
        resp.raise_for_status()
        for item in resp.json().get("data", []):
            title = (item.get("title") or "").strip()
            abstract = (item.get("abstract") or "")[:600]
            if not title: continue
            doi = (item.get("externalIds") or {}).get("DOI", "")
            journal = (item.get("journal") or {}).get("name", "") if item.get("journal") else ""
            pub_date = str(item.get("year", ""))
            paper_id = item.get("paperId", "")
            url = f"https://doi.org/{quote(doi, safe='')}" if doi else f"https://www.semanticscholar.org/paper/{paper_id}"
            links = []
            if doi: links.append({"type": "doi", "label": "DOI", "url": url})
            links.append({"type": "semantic-scholar", "label": "Semantic Scholar", "url": f"https://www.semanticscholar.org/paper/{paper_id}"})
            # Only include if OA PDF is available or DOI exists
            if item.get("openAccessPdf") or doi:
                articles.append({
                    "id": hashlib.sha256(f"{title}|s2".encode()).hexdigest()[:12],
                    "title": title[:300], "abstract": abstract, "journal": journal,
                    "doi": doi, "pmid": "", "first_author": "",
                    "pub_date": pub_date, "source": "Semantic Scholar", "url": url, "links": links,
                })
    except Exception as e:
        print(f"    Semantic Scholar error: {e}")
    return articles

def fetch_biorxiv() -> list:
    """Fetch recent bioinformatics preprints from bioRxiv."""
    articles = []
    try:
        import feedparser
        feed = feedparser.parse("https://connect.biorxiv.org/biorxiv_xml.php?subject=bioinformatics")
        for entry in feed.entries[:20]:
            title = entry.get("title", "").strip()
            abstract = entry.get("summary", "").strip()
            from bs4 import BeautifulSoup
            abstract = " ".join(BeautifulSoup(abstract, "html.parser").get_text(separator=" ", strip=True).split())[:600]
            if not title: continue
            link = entry.get("link", "")
            pub_date = entry.get("published", "")
            articles.append({
                "id": hashlib.sha256(f"{title}|biorxiv".encode()).hexdigest()[:12],
                "title": title[:300], "abstract": abstract, "journal": "bioRxiv (Bioinformatics)",
                "doi": "", "pmid": "", "first_author": "", "pub_date": pub_date,
                "source": "bioRxiv", "url": link,
                "links": [{"type": "biorxiv", "label": "bioRxiv", "url": link}],
            })
    except Exception as e:
        print(f"    bioRxiv error: {e}")
    return articles

def crawl_channel(channel_key: str) -> list:
    """Crawl papers for one lightweight channel."""
    queries = CHANNEL_QUERIES.get(channel_key, [])
    if not queries:
        print(f"  Unknown channel: {channel_key}")
        return []

    all_articles = []
    for q in queries[:2]:
        all_articles.extend(fetch_europepmc(q, 15))
        time.sleep(0.3)
        all_articles.extend(fetch_semantic_scholar(q, 10))
        time.sleep(0.5)

    all_articles.extend(fetch_biorxiv())

    # Deduplicate
    seen = set()
    unique = []
    for a in all_articles:
        key = a["title"][:80].lower()
        h = hashlib.md5(key.encode()).hexdigest()
        if h not in seen:
            seen.add(h)
            unique.append(a)

    unique.sort(key=lambda a: a.get("pub_date", ""), reverse=True)
    return unique

def crawl_all(channels: list = None) -> dict:
    """Crawl all specified channels, returning {channel_key: [papers]}."""
    if channels is None:
        channels = list(CHANNEL_QUERIES.keys())
    results = {}
    for ch in channels:
        print(f"\n[{ch}]")
        papers = crawl_channel(ch)
        print(f"  {len(papers)} papers")
        results[ch] = papers
    return results

if __name__ == "__main__":
    # Test: crawl one channel
    ch = sys.argv[1] if len(sys.argv) > 1 else "computational-genomics"
    papers = crawl_channel(ch)
    print(f"\nTotal: {len(papers)} papers for {ch}")
    for p in papers[:3]:
        print(f"  - {p['title'][:80]}")
        print(f"    {p['journal']} | {p['pub_date']}")
