#!/usr/bin/env python3
"""
预计算脚本：对知识库中每个条目调用 DeepSeek 进行 AI 分析，
结果存入 precomputed_ai.json，前端直接读取，无需后端。

仿 AIHot 架构 — 数据在构建时固化，运行时纯静态。
"""
import json
import os
import sys
import time
from datetime import datetime
from openai import OpenAI

# ==================== 配置 ====================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
KB_PATH = os.path.join(BASE_DIR, "knowledge_base.json")
OUTPUT_PATH = os.path.join(BASE_DIR, "precomputed_ai.json")

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
if not DEEPSEEK_API_KEY:
    # 尝试从 .env 读取
    env_path = os.path.join(BASE_DIR, ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                if line.startswith("DEEPSEEK_API_KEY="):
                    DEEPSEEK_API_KEY = line.split("=", 1)[1].strip()
                    break

if not DEEPSEEK_API_KEY:
    print("[ERROR] DEEPSEEK_API_KEY not found. Set it in .env or environment.")
    sys.exit(1)

client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")

SYSTEM_PROMPT = """你是一个专业的猪肠道微生物组与表观遗传学证据评估助手。
你的任务是对给定的益生菌或代谢物条目进行结构化证据评估。

## 证据等级标准（参照已发表论文的四级框架）

**益生菌功能声称（4级）：**
- Level 1：关联推断（共现网络分析、丰度-表型统计关联、体外实验、同属异种间接证据）
- Level 2：中度推断（猪模型中直接验证了效应分子功能，附机制通路数据，但不区分菌株来源）
- Level 3：强推断（小鼠单菌定植因果验证，人源菌株）
- Level 4：确立证据（猪源菌株在断奶仔猪中的单菌定植实验，经独立重复证实）

**代谢物四维矩阵（双向通路评估）：**
- 正向通路（Forward）：Level 0(无证据) → Level 1(关联推断/体外) → Level 2a(猪体外) → Level 2b(猪体内) → Level 3(因果验证) → Level 4(跨代证据)
- 反向通路（Reverse）：同上分级
- 耦合验证（Coupling）：Level 0(无) → Level 1(独立验证) → Level 2(同实验观察) → Level 3(干预因果) → Level 4(跨尺度耦合)
- 测量深度（Measurement）：Level 0(单隔室单时间点) → Level 1(多隔室或多时间点) → Level 2(多隔室+多时间点+多组学)

## 输出格式
你必须仅输出一个合法的 JSON 对象，不要包含任何其他文字：

{
  "name": "中文名称",
  "name_en": "英文名称",
  "type": "probiotics 或 metabolites",
  "evidence_level": "证据等级",
  "scores": {
    "effectiveness": 0到5的整数,
    "safety": 0到5的整数,
    "accessibility": 0到5的整数,
    "evidence_strength": 0到5的整数
  },
  "summary": "中文摘要（200-400字）",
  "summary_en": "English summary",
  "key_references": ["Author (Year) Key Finding"],
  "research_priority": "P1/P2/P3 或 N/A",
  "confidence": "high/medium/low"
}"""


def analyze_entry(entry: dict) -> dict:
    """对单个知识库条目进行 AI 分析"""
    name = entry["name"]
    name_en = entry.get("name_en", "")
    category = entry.get("category", "unknown")
    existing_summary = entry.get("summary", "")[:300]

    user_message = f"""## 条目信息
名称: {name}
英文名: {name_en}
类别: {category}
已知摘要: {existing_summary}

请对该条目进行结构化证据评估，直接输出 JSON。"""

    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            temperature=0.3,
            max_tokens=2048,
            extra_body={"enable_search": True},
        )

        raw = response.choices[0].message.content.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1]
            if raw.endswith("```"):
                raw = raw[:-3]
        if raw.startswith("json"):
            raw = raw[4:].strip()

        result = json.loads(raw)
        result["_analyzed_at"] = datetime.now().isoformat()
        result["_query_name"] = name
        return result

    except Exception as e:
        print(f"  [ERROR] {name}: {e}")
        return {
            "name": name, "name_en": name_en, "type": category,
            "evidence_level": entry.get("evidence_level", "N/A"),
            "scores": entry.get("scores", {}),
            "summary": entry.get("summary", ""),
            "summary_en": entry.get("summary_en", ""),
            "key_references": [],
            "research_priority": "N/A",
            "confidence": "low",
            "_analyzed_at": datetime.now().isoformat(),
            "_query_name": name,
            "_error": str(e),
        }


def main():
    print("=" * 60)
    print("  Precompute AI Analyses for Knowledge Base")
    print(f"  Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # 加载知识库
    with open(KB_PATH, "r", encoding="utf-8") as f:
        kb = json.load(f)

    # 加载已有的预计算结果（增量更新）
    existing = {}
    if os.path.exists(OUTPUT_PATH):
        with open(OUTPUT_PATH, "r", encoding="utf-8") as f:
            existing_data = json.load(f)
            for e in existing_data.get("analyses", []):
                existing[e["_query_name"]] = e
        print(f"[Load] {len(existing)} existing analyses")

    # 收集所有需要分析的条目
    entries = []
    for cat in ["probiotics", "metabolites"]:
        for item in kb.get(cat, []):
            item_copy = dict(item)
            item_copy["category"] = cat
            entries.append(item_copy)

    print(f"[Analyze] {len(entries)} total entries")

    # 逐条分析
    analyses = []
    new_count = 0
    skip_count = 0
    for i, entry in enumerate(entries):
        name = entry["name"]
        if name in existing:
            analyses.append(existing[name])
            skip_count += 1
            print(f"  [{i+1}/{len(entries)}] {name} — (cached)")
        else:
            print(f"  [{i+1}/{len(entries)}] {name} — analyzing...")
            result = analyze_entry(entry)
            analyses.append(result)
            new_count += 1
            # 每次分析后保存（防止中断丢失）
            with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
                json.dump({
                    "generated_at": datetime.now().isoformat(),
                    "total": len(analyses),
                    "analyses": analyses,
                }, f, ensure_ascii=False, indent=2)
            time.sleep(1)  # 避免限流

    print(f"\n  Done: {new_count} new, {skip_count} cached, {len(analyses)} total")
    print(f"  Saved to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
