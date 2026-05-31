#!/usr/bin/env python3
"""
文献评估脚本 — 四级证据评估框架 + 四维矩阵评分
使用 DeepSeek API 对每篇新论文进行系统评估
评估维度完全对齐项目一 & 项目二的方法学框架
"""

import json
import os
import sys
import time
from datetime import datetime
from typing import Optional

# ==================== 配置 ====================

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
RAW_ARTICLES_FILE = os.path.join(DATA_DIR, "raw_articles.json")
SCORED_ARTICLES_FILE = os.path.join(DATA_DIR, "scored_articles.json")

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-chat"

GLM_API_KEY = os.environ.get("GLM_API_KEY", "")
GLM_BASE_URL = "https://open.bigmodel.cn/api/paas/v4"
GLM_MODEL = "glm-4-flash"

MAX_ARTICLES_PER_RUN = int(os.environ.get("MAX_ARTICLES", "30"))

# ==================== 评估 Prompt ====================

EVALUATION_PROMPT = """You are a senior researcher in gut microbiome and host-microbe co-metabolism. Evaluate the following research paper using a rigorous BIDIRECTIONAL evidence-based framework.

## Evaluation Framework

### A. Evidence Level (choose one)
- **L4**: Complete bidirectional causal chain validated in relevant model — forward (microbe→host) AND reverse (host→microbe) pathways both measured in the SAME experimental system. Multi-compartment, multi-timepoint data.
- **L3**: Strong causal evidence in ONE direction (either forward OR reverse), typically in a model species (mouse mono-colonization, germ-free model), but NOT yet validated in porcine/large-animal models.
- **L2b**: Direct in vivo validation in porcine/large-animal model for at least one direction, but mechanism is partially validated or from mixed interventions (not strain/metabolite-specific).
- **L2a**: Preliminary in vivo evidence in porcine/large-animal model (correlation, association, or dietary intervention) without direct causal validation.
- **L1**: In vitro only, computational prediction, cross-species extrapolation without any experimental validation, or review/opinion.

### B. Four-Dimensional Bidirectional Matrix (score each 0-5)

**IMPORTANT**: Score BOTH directions with EQUAL rigor. A paper may have strong forward evidence but weak/no reverse evidence — document the asymmetry.

1. **Forward Pathway (Microbe → Host)** — score 0-5:
   How strongly does this paper demonstrate that gut microbes or microbial metabolites CAUSE changes in the host? Consider:
   - Direct causality: Is a specific strain/metabolite shown to PRODUCE the host effect? (intervention → mechanism → phenotype)
   - Mechanistic depth: Is the molecular mechanism identified (receptor binding, signaling cascade, epigenetic modification)?
   - Quantitative rigor: Are dose-response relationships, effect sizes, and concentration gradients measured?
   - Score 0: No forward evidence (pure association, review). Score 5: Complete causal chain from defined microbial effector to host molecular target to physiological outcome, with quantitative dose-response.

2. **Reverse Pathway (Host → Microbiome)** — score 0-5:
   How strongly does this paper demonstrate that host factors (diet, genetics, immunity, disease state) CAUSE changes in the gut microbial community or microbial metabolism? Consider:
   - Host control mechanisms: Is a specific host factor (immune response, dietary change, genetic manipulation, epithelial signaling) shown to ALTER microbial composition or function?
   - Mechanistic pathway: Is the molecular link from host signal to microbial response identified (e.g., host AMP secretion → altered bacterial survival; host bile acid synthesis → altered bacterial FXR signaling)?
   - Feedback evidence: Does the paper measure how host-initiated changes feed back to alter microbial metabolite output?
   - Score 0: No reverse evidence whatsoever. Score 5: Complete causal chain from defined host factor → specific microbial population shift or metabolic change → quantified alteration in microbial metabolite pool.

3. **Bidirectional Coupling** — score 0-5:
   Are forward AND reverse pathways measured in the SAME experimental system? Is the co-metabolism loop closed?
   - Score 0: Only one direction measured; no coupling attempt.
   - Score 1-2: Both directions mentioned but measured in separate experiments/systems.
   - Score 3-4: Both directions measured in the same experiment, but not simultaneously or without cross-validation.
   - Score 5: True bidirectional measurement — host and microbial variables tracked simultaneously in the same animals/samples, with causal links verified in both directions.

4. **Measurement Depth** — score 0-5:
   - Score 0-1: Single compartment (luminal only), single timepoint, bulk measurements.
   - Score 2-3: Two compartments (lumen + epithelium or lumen + systemic), or multiple timepoints.
   - Score 4-5: Multi-compartment (lumen + epithelium + lamina propria/submucosa OR portal blood), time-series sampling, concentration gradients quantified across compartments. Spatial resolution (e.g., imaging, laser-capture microdissection) counts strongly.

### C. Journal & Methodology
- **Journal Quality**: Assess reputation, impact, and rigor.
- **Model System**: What species/organoid/cell line? Note if porcine-relevant.
- **Key Limitation**: One sentence on the most critical methodological weakness — pay special attention to which DIRECTION (forward or reverse) is missing.

### D. Node Relevance
Which co-metabolism nodes does this paper primarily contribute to? Choose ALL that apply.

Metabolite nodes: Butyrate, Propionate, Acetate, Branched SCFAs, Bile Acids, Tryptophan Metabolites, Polyamines, Vitamin B12, Folate/B9, Riboflavin/B2, Biotin/B7, Vitamin A/Retinoic Acid, Vitamin D, B-Vitamins (B1/B3/B5/B6), Lactate, Succinate, GABA/Glutamate

Strain/Taxa nodes: Phascolarctobacterium, Lactobacillus, Bifidobacterium, Bacteroides, Clostridium, Prevotella, Akkermansia, Faecalibacterium

## Output Format
Return ONLY a JSON object (no other text):
```json
{
  "evidence_level": "L1/L2a/L2b/L3/L4",
  "evidence_justification": "one sentence why, noting which direction(s) are validated",
  "effectiveness": 0,
  "safety": 0,
  "coupling": 0,
  "measurement_depth": 0,
  "total_score": 0,
  "forward_score": 0,
  "reverse_score": 0,
  "forward_justification": "one sentence on forward pathway evidence",
  "reverse_justification": "one sentence on reverse pathway evidence",
  "journal_quality": "high/medium/low",
  "model_system": "e.g., mouse mono-colonization, porcine dietary intervention, Caco-2 cells",
  "porcine_relevant": true,
  "key_limitation": "one sentence — specify which direction is the bottleneck",
  "nodes": ["Node1", "Node2"],
  "summary": "3-4 sentence summary covering: (1) what new forward-pathway data this paper contributes, (2) what (if any) reverse-pathway evidence it provides, (3) how well the two directions are coupled, and (4) the key evidence gap",
  "should_include": true
}
```

NOTE: `effectiveness` maps to Forward Pathway (Microbe→Host), `safety` maps to Reverse Pathway (Host→Microbiome). Score them symmetrically — a paper with strong reverse evidence should get a high safety score.

CRITICAL: Set "should_include" to FALSE if:
- The paper only tangentially mentions a metabolite without studying its mechanistic role in gut microbiome
- It is about a non-gut system (skin, lung, ocean, soil, etc.) even if the metabolite is mentioned
- It is a pure clinical/epidemiological study with no mechanistic insight
- It is about host metabolism without any microbial component
- It does not contribute new data to the co-metabolism framework

Be selective. Only include papers that genuinely advance understanding of microbial metabolite-host interactions in the gut context.

## Paper to Evaluate
Title: {title}
Journal: {journal}
Source: {source}
Authors (first): {first_author}
Abstract: {abstract}
Query Node: {query_node}
"""


# ==================== API 调用 ====================

def evaluate_with_deepseek(article: dict, retries: int = 3) -> Optional[dict]:
    """DeepSeek API 评估"""
    if not DEEPSEEK_API_KEY:
        return None

    from openai import OpenAI
    client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)

    prompt = EVALUATION_PROMPT.format(
        title=article.get("title", ""),
        journal=article.get("journal", ""),
        source=article.get("source", ""),
        first_author=article.get("first_author", ""),
        abstract=article.get("abstract", ""),
        query_node=article.get("query_node", ""),
    )

    for attempt in range(retries + 1):
        try:
            response = client.chat.completions.create(
                model=DEEPSEEK_MODEL,
                messages=[
                    {"role": "system", "content": "You are a rigorous academic reviewer. Output ONLY valid JSON, no other text."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
                max_tokens=800,
            )
            return _parse_json(response.choices[0].message.content.strip())
        except Exception as e:
            msg = str(e)
            if any(kw in msg.lower() for kw in ["rate_limit", "429", "503", "overloaded"]):
                time.sleep((attempt + 1) * 4)
            elif attempt < retries:
                time.sleep(2)
            else:
                print(f"    DeepSeek failed: {msg[:100]}")
                return None
    return None


def evaluate_with_glm(article: dict) -> Optional[dict]:
    """GLM 备用评估"""
    if not GLM_API_KEY:
        return None
    try:
        from openai import OpenAI
        client = OpenAI(api_key=GLM_API_KEY, base_url=GLM_BASE_URL)

        prompt = EVALUATION_PROMPT.format(
            title=article.get("title", ""),
            journal=article.get("journal", ""),
            source=article.get("source", ""),
            first_author=article.get("first_author", ""),
            abstract=article.get("abstract", ""),
            query_node=article.get("query_node", ""),
        )

        response = client.chat.completions.create(
            model=GLM_MODEL,
            messages=[
                {"role": "system", "content": "You are a rigorous academic reviewer. Output ONLY valid JSON."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=800,
        )
        return _parse_json(response.choices[0].message.content.strip())
    except Exception as e:
        print(f"    GLM failed: {str(e)[:100]}")
        return None


def evaluate_local(article: dict) -> dict:
    """本地降级：基于期刊和摘要做基础双向评估"""
    jn = article.get("journal", "").lower()
    source = article.get("source", "")
    abstract_len = len(article.get("abstract", ""))
    abstract_lower = article.get("abstract", "").lower()
    title_lower = article.get("title", "").lower()

    # 期刊质量估计
    top_tier = any(n in jn for n in ["nature", "science", "cell", "lancet", "nejm", "pnas", "elife"])
    good_tier = any(n in jn for n in ["microbiome", "gut microbes", "isme", "mbio", "msystems",
                                       "gastroenterology", "gut", "hepatology", "plos biology",
                                       "embo", "genome biology", "current biology"])

    if top_tier:
        base_level = "L3"
        jq = "high"
        fwd_base = 4
    elif good_tier:
        base_level = "L2b"
        jq = "high"
        fwd_base = 3
    elif source == "bioRxiv":
        base_level = "L1"
        jq = "unverified"
        fwd_base = 1
    else:
        base_level = "L2a"
        jq = "medium"
        fwd_base = 2

    # 检测反向通路 (Host→Microbiome) 关键词
    reverse_keywords = ["host immune", "host genetics", "diet-induced", "diet induced",
                        "host-microbe feedback", "host-microbiome", "epithelial signaling",
                        "amp secretion", "antimicrobial peptide", "defensin", "reg3",
                        "bile acid synthesis", "fxr", "tgr5", "vdr", "vitamin d receptor"]
    has_reverse_hint = any(kw in abstract_lower or kw in title_lower
                          for kw in reverse_keywords)

    rev_base = max(0, fwd_base - 1) if has_reverse_hint else max(0, fwd_base - 2)

    # 摘要长度代表信息量
    if abstract_len > 300:
        fwd_base = min(5, fwd_base + 1)
        if has_reverse_hint:
            rev_base = min(5, rev_base + 1)

    total = fwd_base + rev_base

    return {
        "evidence_level": base_level,
        "evidence_justification": "Local bidirectional estimation based on journal tier and abstract",
        "effectiveness": fwd_base,
        "safety": rev_base,
        "coupling": max(0, min(fwd_base, rev_base) - 1),
        "measurement_depth": max(0, min(fwd_base, rev_base)),
        "total_score": total,
        "forward_score": fwd_base,
        "reverse_score": rev_base,
        "forward_justification": f"Local estimate: forward pathway evidence scored at {fwd_base}/5 based on journal tier.",
        "reverse_justification": f"Local estimate: reverse pathway evidence scored at {rev_base}/5 {'(reverse hints detected)' if has_reverse_hint else '(no reverse hints detected)'}.",
        "journal_quality": jq,
        "model_system": "unknown",
        "porcine_relevant": False,
        "key_limitation": "Local fallback evaluation: needs AI assessment for bidirectional scoring",
        "nodes": article.get("nodes", []),
        "summary": f"From {article.get('journal', 'unknown journal')}. Forward: {fwd_base}/5, Reverse: {rev_base}/5. Full AI evaluation pending.",
        "should_include": True,
        "eval_method": "local",
    }


# ==================== 工具函数 ====================

def _parse_json(text: str) -> Optional[dict]:
    import re
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    for pattern in [r"```(?:json)?\s*([\s\S]*?)```", r"\{[\s\S]*\}"]:
        m = re.search(pattern, text)
        if m:
            try:
                return json.loads(m.group(1) if "```" in pattern else m.group(0))
            except json.JSONDecodeError:
                pass
    print(f"    JSON parse failed: {text[:150]}")
    return None


def load_articles(filepath: str) -> list:
    if not os.path.exists(filepath):
        print(f"  File not found: {filepath}")
        return []
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def save_scored(articles: list, filepath: str):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(articles, f, ensure_ascii=False, indent=2)
    print(f"  Saved: {len(articles)} scored articles")


# ==================== 主入口 ====================

def main():
    print("=" * 60)
    print("  Co-Metabolism Evidence Evaluator")
    print(f"  Framework: 4-Level Evidence + 4-D Matrix")
    print(f"  Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  DeepSeek: {'configured' if DEEPSEEK_API_KEY else 'MISSING'}")
    print(f"  GLM fallback: {'configured' if GLM_API_KEY else 'not set'}")
    print("=" * 60)

    articles = load_articles(RAW_ARTICLES_FILE)
    if not articles:
        print("  No articles to evaluate.")
        return 0

    print(f"\n  Loaded: {len(articles)} articles")

    to_evaluate = articles[:MAX_ARTICLES_PER_RUN]
    if len(articles) > MAX_ARTICLES_PER_RUN:
        print(f"  Limiting to first {MAX_ARTICLES_PER_RUN}")

    scored = []
    ds_count, glm_count, local_count = 0, 0, 0

    for i, article in enumerate(to_evaluate, 1):
        title_short = article.get("title", "")[:70]
        print(f"  [{i}/{len(to_evaluate)}] {title_short}")

        scores = None
        if DEEPSEEK_API_KEY:
            scores = evaluate_with_deepseek(article)
            if scores:
                ds_count += 1
                scores["eval_method"] = "deepseek"
                scores["eval_model"] = DEEPSEEK_MODEL

        if not scores and GLM_API_KEY:
            scores = evaluate_with_glm(article)
            if scores:
                glm_count += 1
                scores["eval_method"] = "glm"
                scores["eval_model"] = GLM_MODEL

        if not scores:
            scores = evaluate_local(article)
            local_count += 1

        scored.append({**article, "evaluation": scores})
        if i < len(to_evaluate):
            time.sleep(0.3)

    # 排除 should_include=false 的文章
    scored = [a for a in scored if a.get("evaluation", {}).get("should_include", True)]

    # 排序: 证据等级优先 + 总分降序
    level_order = {"L4": 5, "L3": 4, "L2b": 3, "L2a": 2, "L1": 1}
    scored.sort(key=lambda a: (
        -level_order.get(a.get("evaluation", {}).get("evidence_level", "L1"), 1),
        -a.get("evaluation", {}).get("total_score", 0),
    ))

    print(f"\n  === Evaluation Summary ===")
    print(f"  DeepSeek: {ds_count}  |  GLM: {glm_count}  |  Local: {local_count}")

    level_counts = {}
    for a in scored:
        lv = a.get("evaluation", {}).get("evidence_level", "L1")
        level_counts[lv] = level_counts.get(lv, 0) + 1
    print(f"  Evidence levels: {dict(sorted(level_counts.items()))}")

    save_scored(scored, SCORED_ARTICLES_FILE)

    with open(os.path.join(DATA_DIR, "eval_stats.txt"), "w") as f:
        f.write(f"total={len(scored)},deepseek={ds_count},glm={glm_count},local={local_count}")

    return len(scored)


if __name__ == "__main__":
    sys.exit(0 if main() > 0 else 1)
