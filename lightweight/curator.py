#!/usr/bin/env python3
"""
Lightweight literature curator — AI summarization + significance rating + topic classification.
Designed for broad OA coverage. Much cheaper than the full evidence evaluation pipeline.
~200 tokens in, ~150 tokens out per paper.
"""
import json, os, sys, time, re
from datetime import datetime
from openai import OpenAI

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ai-news", "data")
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
if not DEEPSEEK_API_KEY:
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                if line.startswith("DEEPSEEK_API_KEY="):
                    DEEPSEEK_API_KEY = line.split("=", 1)[1].strip()
                    break

SYSTEM_PROMPT = """You are a bioinformatics researcher curating papers for a daily literature digest.
For each paper, provide: (1) a 2-3 sentence plain-English summary of the key finding, (2) a significance rating, (3) relevant topic tags.

## Significance Rating
- **High**: Methodological breakthrough, new resource of broad utility, or finding that changes current understanding.
- **Medium**: Solid contribution extending existing methods or knowledge. Worth reading for specialists.
- **Low**: Incremental work, narrow scope, or preliminary. May still be useful for specific audiences.

## Topic Tags
Choose 1-3 from: genomics, transcriptomics, epigenomics, proteomics, metabolomics, single-cell, spatial-omics, metagenomics, microbiome, structural-biology, systems-biology, network-analysis, machine-learning, deep-learning, LLM, protein-structure, drug-discovery, database, tool, methodology, review, clinical, population-genetics, evolution, synthetic-biology, CRISPR, immunology, neuroscience, cancer, development, aging, plants, microbiology.

## Output Format
Return ONLY a valid JSON object:
{
  "summary": "2-3 sentence plain-English summary of the key contribution.",
  "significance": "High | Medium | Low",
  "tags": ["tag1", "tag2"]
}
"""

CLIENT = None

def get_client():
    global CLIENT
    if CLIENT is None and DEEPSEEK_API_KEY:
        CLIENT = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")
    return CLIENT

def curate_paper(title: str, abstract: str, journal: str = "") -> dict:
    """AI-curate a single paper: summarize, rate significance, tag."""
    client = get_client()
    if not client:
        return _local_curate(title, abstract, journal)

    user_msg = f"Title: {title[:300]}\nJournal: {journal}\nAbstract: {abstract[:600]}"

    for attempt in range(3):
        try:
            resp = client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
                temperature=0.3,
                max_tokens=300,
            )
            raw = resp.choices[0].message.content.strip()
            if raw.startswith("```"):
                raw = re.sub(r"^```(?:json)?\s*", "", raw)
                raw = re.sub(r"\s*```$", "", raw)
            return json.loads(raw)
        except json.JSONDecodeError:
            if attempt < 2:
                time.sleep(1)
            else:
                return _local_curate(title, abstract, journal)
        except Exception as e:
            msg = str(e)
            if any(kw in msg.lower() for kw in ["rate_limit", "429", "503"]):
                time.sleep((attempt + 1) * 3)
            elif attempt < 2:
                time.sleep(1)
            else:
                return _local_curate(title, abstract, journal)
    return _local_curate(title, abstract, journal)

def _local_curate(title: str, abstract: str, journal: str) -> dict:
    """Heuristic fallback — no API call."""
    text = (title + " " + abstract).lower()
    tags = []
    if any(kw in text for kw in ["genom", "variant", "gwas", "assembly"]): tags.append("genomics")
    if any(kw in text for kw in ["transcriptom", "rna-seq", "expression"]): tags.append("transcriptomics")
    if any(kw in text for kw in ["epigen", "methylation", "histone", "chromatin"]): tags.append("epigenomics")
    if any(kw in text for kw in ["single.cell", "scrna", "scatac"]): tags.append("single-cell")
    if any(kw in text for kw in ["metagenom", "microbiome", "microbiota"]): tags.append("microbiome")
    if any(kw in text for kw in ["protein", "structure", "alphafold", "docking"]): tags.append("structural-biology")
    if any(kw in text for kw in ["network", "pathway", "system"]): tags.append("systems-biology")
    if any(kw in text for kw in ["machine.learning", "deep.learning", "neural", "llm", "gpt", "bert"]): tags.append("machine-learning")
    if any(kw in text for kw in ["drug", "pharm", "screening"]): tags.append("drug-discovery")
    if any(kw in text for kw in ["crispr", "edit", "synthetic"]): tags.append("synthetic-biology")
    if any(kw in text for kw in ["review", "survey", "systematic"]): tags.append("review")
    if not tags: tags = ["methodology"]

    sig = "Medium"
    if any(kw in journal.lower() for kw in ["nature", "science", "cell", "pnas", "elife"]): sig = "High"
    elif len(abstract) < 200: sig = "Low"

    return {
        "summary": abstract[:300] if abstract else title[:300],
        "significance": sig,
        "tags": tags[:3],
        "curation_method": "local"
    }

def curate_batch(papers: list, delay: float = 0.3) -> list:
    """Curate a batch of papers, returning papers with curation fields added."""
    curated = []
    for i, p in enumerate(papers):
        print(f"  [{i+1}/{len(papers)}] {p.get('title','')[:70]}")
        curation = curate_paper(
            p.get("title", ""),
            p.get("abstract", ""),
            p.get("journal", "")
        )
        curated.append({**p, **curation})
        if i < len(papers) - 1:
            time.sleep(delay)
    return curated
