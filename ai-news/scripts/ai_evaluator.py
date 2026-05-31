#!/usr/bin/env python3
"""
AI 资讯评估脚本
功能：读取爬虫产出的原始文章，调用 DeepSeek API 进行多维度打分
DeepSeek API 兼容 OpenAI SDK，国内网络直接可用，价格低廉

评分维度：
  - 权威度 (authority): 信息来源的可靠程度 (1-10)
  - 新颖度 (novelty):  信息的新鲜/独家程度 (1-10)
  - 价值度 (value):    对 AI 从业者的实用价值 (1-10)
  - 总分 (total):      综合评分 (1-10)
  - 标签 (tags):       文章关键词/领域标签
  - 推荐理由 (reason):  简短推荐理由 (20-50字)
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

# DeepSeek API 配置（兼容 OpenAI SDK）
# 文档: https://platform.deepseek.com/api-docs
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-chat"  # DeepSeek-V3，性价比最高

# 备用：智谱 GLM API（国内可用，免费额度）
GLM_API_KEY = os.environ.get("GLM_API_KEY", "")
GLM_BASE_URL = "https://open.bigmodel.cn/api/paas/v4"
GLM_MODEL = "glm-4-flash"  # 免费模型

# 每次评估的文章数量上限（可通过环境变量 MAX_ARTICLES 调整）
MAX_ARTICLES_PER_RUN = int(os.environ.get("MAX_ARTICLES", "50"))

# 评分 prompt 模板
SCORING_PROMPT = """你是一位资深的 AI 行业分析师。请对以下 AI 资讯文章进行专业评估。

评估维度：
1. **权威度** (1-10)：信息来源是否权威？是否来自知名机构、官方发布或资深研究者？
2. **新颖度** (1-10)：信息是否新鲜？是独家报道、首发消息，还是转载/总结类内容？
3. **价值度** (1-10)：对 AI 从业者、研究人员或创业者的实用价值如何？
4. **总分** (1-10)：综合评分，无需为前三项的平均值。
5. **标签**：2-4 个关键词标签（如："大模型"、"开源"、"Agent"、"多模态"等）
6. **推荐理由**：用 20-50 字说明这篇文章为什么值得（或不值得）阅读。

请以 JSON 格式返回评估结果，不要输出任何其他内容：
```json
{
  "authority": <1-10>,
  "novelty": <1-10>,
  "value": <1-10>,
  "total": <1-10>,
  "tags": ["标签1", "标签2", "标签3"],
  "reason": "推荐理由（20-50字）"
}
```

以下是需要评估的文章：
---
标题：{title}
来源：{source_name}（权威度基准：{source_authority}/10）
摘要：{summary}
语言：{lang}
"""


# ==================== DeepSeek API 调用（主力） ====================

def evaluate_with_deepseek(article: dict, retries: int = 3) -> Optional[dict]:
    """使用 DeepSeek API 评估单篇文章"""
    if not DEEPSEEK_API_KEY:
        return None

    from openai import OpenAI

    client = OpenAI(
        api_key=DEEPSEEK_API_KEY,
        base_url=DEEPSEEK_BASE_URL,
    )
    prompt = SCORING_PROMPT.format(
        title=article.get("title", ""),
        source_name=article.get("source_name", ""),
        source_authority=article.get("source_authority", 5),
        summary=article.get("summary", ""),
        lang=article.get("lang", "zh"),
    )

    for attempt in range(retries + 1):
        try:
            response = client.chat.completions.create(
                model=DEEPSEEK_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": "你是一个专业的内容评估助手。你只输出 JSON，不输出任何其他内容。",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=512,
            )
            result_text = response.choices[0].message.content.strip()
            return _parse_json_response(result_text)

        except Exception as e:
            error_msg = str(e)
            if "rate_limit" in error_msg.lower() or "429" in error_msg:
                wait = (attempt + 1) * 5
                print(f"    ⚠ DeepSeek 限流，等待 {wait}s...")
                time.sleep(wait)
            elif "503" in error_msg or "overloaded" in error_msg.lower():
                wait = (attempt + 1) * 3
                print(f"    ⚠ DeepSeek 服务繁忙，等待 {wait}s...")
                time.sleep(wait)
            elif attempt < retries:
                print(f"    ⚠ DeepSeek 错误 (尝试 {attempt+1}/{retries}): {error_msg[:100]}")
                time.sleep(2)
            else:
                print(f"    ✗ DeepSeek 最终失败: {error_msg[:100]}")
                return None
    return None


# ==================== 智谱 GLM 备用 ====================

def evaluate_with_glm(article: dict) -> Optional[dict]:
    """使用智谱 GLM API 作为备用评估（国内免费额度）"""
    if not GLM_API_KEY:
        return None

    try:
        from openai import OpenAI

        client = OpenAI(
            api_key=GLM_API_KEY,
            base_url=GLM_BASE_URL,
        )
        prompt = SCORING_PROMPT.format(
            title=article.get("title", ""),
            source_name=article.get("source_name", ""),
            source_authority=article.get("source_authority", 5),
            summary=article.get("summary", ""),
            lang=article.get("lang", "zh"),
        )

        response = client.chat.completions.create(
            model=GLM_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "你是一个专业的内容评估助手。你只输出 JSON，不输出任何其他内容。",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=512,
        )
        result_text = response.choices[0].message.content.strip()
        return _parse_json_response(result_text)

    except Exception as e:
        print(f"    ✗ GLM 错误: {str(e)[:100]}")
        return None


# ==================== 本地降级评分（无 API 时使用） ====================

def evaluate_local(article: dict) -> dict:
    """
    无 API 可用时的本地基础评分
    仅基于来源权威度和标题长度做简单评估
    """
    title_len = len(article.get("title", ""))
    source_auth = article.get("source_authority", 5)

    # 根据标题长度估算新颖度（标题越长往往信息量越大）
    if title_len > 40:
        novelty_boost = 2
    elif title_len > 20:
        novelty_boost = 1
    else:
        novelty_boost = 0

    # 根据来源权威度计算基础分
    authority = min(10, source_auth)
    novelty = min(10, 4 + novelty_boost)
    value = min(10, 5 + novelty_boost)
    total = min(10, (authority + novelty + value) // 3)

    # 简单标签提取
    title_lower = article.get("title", "").lower()
    tags = []
    if any(kw in title_lower for kw in ["大模型", "llm", "gpt", "claude", "gemini", "deepseek"]):
        tags.append("大模型")
    if any(kw in title_lower for kw in ["开源", "open source", "open-source"]):
        tags.append("开源")
    if any(kw in title_lower for kw in ["agent", "智能体"]):
        tags.append("Agent")
    if any(kw in title_lower for kw in ["多模态", "multimodal", "视觉"]):
        tags.append("多模态")
    if any(kw in title_lower for kw in ["芯片", "gpu", "算力"]):
        tags.append("算力")
    if not tags:
        tags.append("AI资讯")

    return {
        "authority": authority,
        "novelty": novelty,
        "value": value,
        "total": total,
        "tags": tags[:4],
        "reason": f"来自{article.get('source_name', '未知来源')}的AI资讯"[:50],
        "eval_method": "local",
    }


# ==================== 工具函数 ====================

def _parse_json_response(text: str) -> Optional[dict]:
    """从 AI 返回的文本中解析 JSON"""
    import re

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 尝试从 markdown 代码块中提取
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # 尝试找到 { ... } 块
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    print(f"    ⚠ 无法解析 JSON 响应: {text[:200]}")
    return None


def load_articles(filepath: str) -> list[dict]:
    """加载爬虫产出的文章"""
    if not os.path.exists(filepath):
        print(f"✗ 文件不存在: {filepath}")
        return []
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def save_scored_articles(articles: list[dict], filepath: str):
    """保存评分后的文章"""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(articles, f, ensure_ascii=False, indent=2)
    print(f"\n💾 已保存 {len(articles)} 条评分文章到 {filepath}")


# ==================== 主入口 ====================

def main():
    print("=" * 60)
    print("🤖 AI 资讯评估器启动")
    print(f"   时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   DeepSeek API: {'✓ 已配置 (' + DEEPSEEK_API_KEY[:6] + '...)' if DEEPSEEK_API_KEY else '✗ 未配置'}")
    print(f"   GLM 备用 API: {'✓ 已配置' if GLM_API_KEY else '✗ 未配置（可选）'}")
    print("=" * 60)
    print()

    # 加载原始文章
    articles = load_articles(RAW_ARTICLES_FILE)
    if not articles:
        print("⚠ 没有文章需要评估，请先运行 crawler.py")
        return 0

    print(f"📚 共加载 {len(articles)} 条文章")

    # 限制数量
    articles_to_evaluate = articles[:MAX_ARTICLES_PER_RUN]
    if len(articles) > MAX_ARTICLES_PER_RUN:
        print(f"⚠ 文章超过上限，仅评估前 {MAX_ARTICLES_PER_RUN} 条")

    print()
    scored = []
    deepseek_count = 0
    glm_count = 0
    local_count = 0

    for i, article in enumerate(articles_to_evaluate, 1):
        title_short = article.get("title", "")[:60]
        print(f"[{i}/{len(articles_to_evaluate)}] {title_short}...")

        scores = None

        # 优先使用 DeepSeek
        if DEEPSEEK_API_KEY:
            scores = evaluate_with_deepseek(article)
            if scores:
                deepseek_count += 1
                scores["eval_method"] = "deepseek"
                scores["eval_model"] = DEEPSEEK_MODEL

        # DeepSeek 失败，尝试 GLM
        if not scores and GLM_API_KEY:
            scores = evaluate_with_glm(article)
            if scores:
                glm_count += 1
                scores["eval_method"] = "glm"
                scores["eval_model"] = GLM_MODEL

        # 全部 API 不可用，本地降级
        if not scores:
            scores = evaluate_local(article)
            local_count += 1

        # 合并原文章信息和评分
        article_with_scores = {**article, "scores": scores}
        scored.append(article_with_scores)

        # 礼貌延迟（DeepSeek 无需严格限流，但避免请求过于密集）
        if i < len(articles_to_evaluate):
            time.sleep(0.2)

    print(f"\n📊 评估统计:")
    print(f"   DeepSeek 评估: {deepseek_count} 条")
    print(f"   GLM 备用评估:  {glm_count} 条")
    print(f"   本地评分:      {local_count} 条")

    # 按总分降序排列
    scored.sort(key=lambda a: a.get("scores", {}).get("total", 0), reverse=True)

    # 保存
    save_scored_articles(scored, SCORED_ARTICLES_FILE)

    # 将统计写入临时文件
    with open(os.path.join(DATA_DIR, "eval_stats.txt"), "w", encoding="utf-8") as f:
        f.write(f"total={len(scored)},deepseek={deepseek_count},glm={glm_count},local={local_count}")

    return len(scored)


if __name__ == "__main__":
    count = main()
    sys.exit(0 if count > 0 else 1)
