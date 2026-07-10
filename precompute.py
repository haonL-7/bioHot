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
本评估系统基于两篇已发表的方法学论文：
- 论文一：Liu H, Feng W. "Compartmentalized Co-metabolism in the Porcine Gut: Systematic Evidence Mapping and a Theoretical Framework for Epigenetic–Microbiome Interactions" — 定义了区室化共代谢网络模型和四维矩阵评分系统。
- 论文二：Liu H, Feng W. "A Tiered Evidence Framework for Assessing Translational Readiness of Candidate Probiotics in Livestock: A Systematic Evidence Mapping with Methodological Development" — 定义了六级证据评估体系（L1a–L4，含 Level 3.5）。

## 证据等级标准

### 益生菌功能声称 — 六级证据体系（L1a→L4）：

| 等级 | 定义 |
|------|------|
| **L0** | 无相关证据 |
| **L1a** | 机制证据：体外纯培养代谢实验、离体组织/细胞实验、同属异种间接机制证据 |
| **L1b** | 关联推断：属级共现网络分析、丰度-表型统计关联、宏基因组功能推断 |
| **L2a** | 中度推断：效应分子在猪模型中直接验证（如丙酸→TLR4/NF-κB抑制），但未区分菌株来源 |
| **L2b** | 猪体内直接验证：至少一个方向的猪体内因果证据，机制部分验证，干预措施菌株/代谢物靶向 |
| **L3** | 强推断：人源菌株小鼠单菌定植因果验证 |
| **L3.5** | 过渡验证：人源菌株在猪模型中的单菌定植实验（分离宿主转移与菌株来源转移） |
| **L4** | 确立证据：猪源菌株在断奶仔猪中的单菌定植实验，经独立重复证实 |

**关键区分**：L1–L3 回答"在受控条件下是否可行"（机制合理性）；L4 回答"在生态真实条件下是否有效"（转化效能）。

### 代谢物 — 四维矩阵评分：

**维度 I — 正向通路（微生物→宿主）：0-4分**
- 0: 无正向证据
- 1: 猪肠道数据中的关联推断（共现网络/统计关联）
- 2a: 体外猪模型验证（猪回肠类器官、IPEC-J2细胞）
- 2b: 猪体内验证（口服代谢物补充实验）
- 3: 小鼠模型因果验证（单菌定植、基因敲除）
- 4: 猪模型因果验证，经独立实验室重复

**维度 II — 反向通路（宿主→微生物组）：0-4分**
- 0: 无反向证据
- 1: 宿主遗传-微生物组关联研究、母体营养编程研究、无菌猪转录组比较
- 2a: 体外猪模型验证显示宿主表观遗传改变影响微生物组成/功能
- 2b: 猪体内验证（HDAC抑制剂处理、膳食甲基供体操作）
- 3: 小鼠模型因果验证（SIRT1、HDAC6、Tet2、KDM5敲除）
- 4: 猪模型因果验证，经独立实验室重复

**维度 III — 耦合验证深度：0-4分**
- 0: 仅一个方向被测量，无耦合尝试
- 1: 正向和反向通路独立验证，但不在同一实验系统内
- 2: 同一实验中同时观察到正向和反向效应，但无因果连接的干预证明
- 3: 干预实验证明阻断一个通路影响另一个通路，建立因果耦合
- 4: 跨尺度耦合验证：单次实验中同时多隔室多时间点测量，显示正向效应时间上先于反向效应

**维度 IV — 测量深度：0-2分（仅三级）**
- 0: 单隔室单时间点测量；未跨隔室同步测量代谢物和表观遗传标记
- 1: 多隔室测量 OR 多时间点采样（但非两者兼具）
- 2: 多隔室测量 AND 多时间点采样，在单个实验系统内

**注意**：维度 IV 仅 0-2 分，反映当前技术上限 — 已发表的实证研究均未达到 Level 2。

## 区室化覆盖
条目涉及的肠道区室（可多选）：
- `luminal` — 肠腔，微生物代谢场所，代谢物浓度毫摩尔级
- `epithelial` — 上皮细胞，宿主表观遗传调控场所，胞内浓度微摩尔级（差三个数量级）
- `microenvironment` — 微环境，反馈通路场所，免疫因子/pH/氧/黏液层

## 研究优先级
- **P1**：高可行性+高重要性（如丁酸在肠腔-上皮界面），时间线2-3年
- **P2**：中可行性+高重要性（如胆汁酸、色氨酸代谢物）
- **P3**：低可行性+中重要性（如多胺、维生素B12）
- **N/A**：不直接对应转化研究缺口

## 输出格式
你必须仅输出一个合法的 JSON 对象，不要包含任何其他文字：

{
  "name": "中文名称",
  "name_en": "英文名称",
  "type": "probiotics 或 metabolites",
  "evidence_level": "L0 | L1a | L1b | L2a | L2b | L3 | L3.5 | L4",
  "entry_type": "probiotics 或 metabolites",
  "forward_pathway": 0,
  "reverse_pathway": 0,
  "coupling_depth": 0,
  "measurement_depth": 0,
  "total_score": 0,
  "compartments_covered": ["luminal"],
  "forward_justification": "正向通路证据一句话说明",
  "reverse_justification": "反向通路证据一句话说明 — 如缺失则明确说明",
  "summary": "中文摘要（3-4句话）：(1)新增正向通路数据，(2)反向通路证据（如有），(3)耦合状态，(4)关键证据缺口",
  "summary_en": "English summary",
  "key_references": ["Author (Year) Key Finding"],
  "research_priority": "P1 | P2 | P3 | N/A",
  "framework_alignment": "Tiered Evidence (论文二) | Compartmentalized Co-metabolism (论文一) | Both",
  "confidence": "high | medium | low"
}

**重要提示**：
- `forward_pathway`、`reverse_pathway`、`coupling_depth` 评分范围为 0-4
- `measurement_depth` 评分范围为 0-2（仅三级）
- `total_score` = forward_pathway + reverse_pathway + coupling_depth + measurement_depth（最大14分）
- `compartments_covered` 必须是包含 "luminal"、"epithelial"、"microenvironment" 中至少一个的数组
- `research_priority` 为必填项，不适用时填 "N/A"
- `framework_alignment` 为必填项，注明条目与哪篇论文框架最相关"""


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
            "entry_type": category,
            "forward_pathway": entry.get("forward_pathway", entry.get("scores", {}).get("effectiveness", 0)),
            "reverse_pathway": entry.get("reverse_pathway", entry.get("scores", {}).get("safety", 0)),
            "coupling_depth": entry.get("coupling_depth", entry.get("scores", {}).get("accessibility", 0)),
            "measurement_depth": entry.get("measurement_depth", entry.get("scores", {}).get("evidence_strength", 0)),
            "total_score": 0,
            "compartments_covered": ["luminal"],
            "forward_justification": "",
            "reverse_justification": "",
            "summary": entry.get("summary", ""),
            "summary_en": entry.get("summary_en", ""),
            "key_references": [],
            "research_priority": "N/A",
            "framework_alignment": "Pending",
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
