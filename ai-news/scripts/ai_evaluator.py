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

EVALUATION_PROMPT = """You are a senior researcher in gut microbiome and host-microbe co-metabolism. Evaluate the following research paper using a rigorous evidence-based framework.

## Evaluation Framework

### A. Evidence Level (choose one)
- **L4**: Complete causal chain validated in relevant model — intervention → molecular mechanism → phenotype, all measured in the SAME experimental system. Multi-compartment, multi-timepoint data.
- **L3**: Strong causal evidence in a different model species (e.g., mouse mono-colonization, germ-free model), but NOT yet validated in porcine/large-animal models.
- **L2b**: Direct in vivo validation in porcine/large-animal model, but mechanism is partially validated or from mixed interventions (not strain/metabolite-specific).
- **L2a**: Preliminary in vivo evidence in porcine/large-animal model (correlation, association, or dietary intervention) without direct causal validation.
- **L1**: In vitro only, computational prediction, cross-species extrapolation without any experimental validation, or review/opinion.

### B. Four-Dimensional Matrix (score each 0-5)
1. **Effectiveness** (Forward pathway): How strongly does this paper demonstrate microbial metabolite → host effect? Consider: direct measurement, causal design, effect size, dose-response.
2. **Safety/Reversibility** (Reverse pathway): Does this paper address host → microbial feedback? Are there adverse effects or compensatory mechanisms discussed?
3. **Coupling Verification**: Are forward AND reverse pathways measured in the same experimental system? Is the co-metabolism loop closed?
4. **Measurement Depth**: Single compartment (luminal only, score 1) → Multi-compartment (lumen + epithelium, score 3) → Multi-compartment + time-series + concentration gradients (score 5).

### C. Journal & Methodology
- **Journal Quality**: Assess reputation, impact, and rigor.
- **Model System**: What species/organoid/cell line? Note if porcine-relevant.
- **Key Limitation**: One sentence on the most critical methodological weakness.

### D. Node Relevance
Which of these five co-metabolism nodes does this paper primarily contribute to?
Choose ALL that apply: Butyrate/SCFAs, Bile Acids, Tryptophan Metabolites, Polyamines, Vitamin B12

## Output Format
Return ONLY a JSON object (no other text):
```json
{
  "evidence_level": "L1/L2a/L2b/L3/L4",
  "evidence_justification": "one sentence why",
  "effectiveness": 0,
  "safety": 0,
  "coupling": 0,
  "measurement_depth": 0,
  "total_score": 0,
  "journal_quality": "high/medium/low",
  "model_system": "e.g., mouse mono-colonization, porcine dietary intervention, Caco-2 cells",
  "porcine_relevant": true,
  "key_limitation": "one sentence",
  "nodes": ["Node1", "Node2"],
  "summary": "2-3 sentence summary of what new data this paper contributes to the co-metabolism framework",
  "should_include": true
}
```

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
    """本地降级：基于期刊和摘要做基础评估"""
    jn = article.get("journal", "").lower()
    source = article.get("source", "")
    abstract_len = len(article.get("abstract", ""))

    # 期刊质量估计
    top_tier = any(n in jn for n in ["nature", "science", "cell", "lancet", "nejm", "pnas", "elife"])
    good_tier = any(n in jn for n in ["microbiome", "gut microbes", "isme", "mbio", "msystems",
                                       "gastroenterology", "gut", "hepatology", "plos biology",
                                       "embo", "genome biology", "current biology"])

    if top_tier:
        base_level = "L3"
        jq = "high"
        eff_base = 4
    elif good_tier:
        base_level = "L2b"
        jq = "high"
        eff_base = 3
    elif source == "bioRxiv":
        base_level = "L1"
        jq = "unverified"
        eff_base = 1
    else:
        base_level = "L2a"
        jq = "medium"
        eff_base = 2

    # 摘要长度代表信息量
    if abstract_len > 300:
        eff_base = min(5, eff_base + 1)

    return {
        "evidence_level": base_level,
        "evidence_justification": "Local estimation based on journal tier and abstract",
        "effectiveness": eff_base,
        "safety": max(0, eff_base - 2),
        "coupling": max(0, eff_base - 3),
        "measurement_depth": max(0, eff_base - 2),
        "total_score": eff_base,
        "journal_quality": jq,
        "model_system": "unknown",
        "porcine_relevant": False,
        "key_limitation": "Local fallback evaluation: needs AI assessment",
        "nodes": article.get("nodes", []),
        "summary": f"From {article.get('journal', 'unknown journal')}. Full AI evaluation pending.",
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
