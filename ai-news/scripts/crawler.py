#!/usr/bin/env python3
"""
AI 资讯爬虫脚本
功能：从多个 RSS 源自动爬取 AI 相关资讯，去重后保存为 JSON
"""

import json
import os
import sys
import hashlib
import time
from datetime import datetime, timedelta
from typing import Optional

import requests
import feedparser
from bs4 import BeautifulSoup
from dateutil import parser as date_parser

# ==================== 配置 ====================

# 数据输出目录
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
RAW_ARTICLES_FILE = os.path.join(DATA_DIR, "raw_articles.json")

# RSS 源列表（中文资讯 + 国际资讯）
RSS_SOURCES = [
    # ── 中文 AI 资讯 ──
    {
        "name": "机器之心",
        "url": "https://rsshub.app/jiqizhixin/latest",
        "lang": "zh",
        "category": "ai_news",
        "authority": 8,
    },
    {
        "name": "量子位",
        "url": "https://rsshub.app/qbitai",
        "lang": "zh",
        "category": "ai_news",
        "authority": 7,
    },
    {
        "name": "36氪快讯",
        "url": "https://rsshub.app/36kr/newsflashes",
        "lang": "zh",
        "category": "tech_news",
        "authority": 6,
    },
    {
        "name": "品玩",
        "url": "https://rsshub.app/pingwest/status",
        "lang": "zh",
        "category": "tech_news",
        "authority": 5,
    },
    {
        "name": "少数派",
        "url": "https://rsshub.app/sspai/matrix",
        "lang": "zh",
        "category": "tech_news",
        "authority": 5,
    },
    {
        "name": "InfoQ 中文",
        "url": "https://rsshub.app/infoq/news",
        "lang": "zh",
        "category": "dev_news",
        "authority": 6,
    },
    # ── 国际 AI 资讯 ──
    {
        "name": "Hacker News",
        "url": "https://hnrss.org/frontpage?points=50",
        "lang": "en",
        "category": "dev_news",
        "authority": 5,
    },
    {
        "name": "Reddit MachineLearning",
        "url": "https://www.reddit.com/r/MachineLearning/hot.rss?limit=25",
        "lang": "en",
        "category": "research",
        "authority": 4,
    },
    {
        "name": "ArXiv CS.AI",
        "url": "https://rss.arxiv.org/rss/cs.AI",
        "lang": "en",
        "category": "research",
        "authority": 9,
    },
    {
        "name": "MIT Technology Review AI",
        "url": "https://www.technologyreview.com/feed/",
        "lang": "en",
        "category": "ai_news",
        "authority": 8,
    },
]

# 请求头（模拟浏览器）
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/rss+xml, application/xml, text/xml, application/atom+xml, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

# 请求超时
TIMEOUT = 30

# 去重时间窗口（天）：只保留最近 N 天的文章
DEDUP_WINDOW_DAYS = 3


# ==================== 工具函数 ====================

def make_article_id(title: str, url: str) -> str:
    """为文章生成唯一 ID（SHA256）"""
    raw = f"{title}|{url}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:12]


def clean_html(html_text: str) -> str:
    """清理 HTML 标签，提取纯文本"""
    soup = BeautifulSoup(html_text, "html.parser")
    text = soup.get_text(separator=" ", strip=True)
    # 合并多余空白
    text = " ".join(text.split())
    return text


def parse_date(date_str: Optional[str]) -> str:
    """解析日期字符串，统一返回 ISO 格式"""
    if not date_str:
        return datetime.now().isoformat()
    try:
        dt = date_parser.parse(date_str)
        return dt.isoformat()
    except Exception:
        return datetime.now().isoformat()


def is_ai_related(title: str, summary: str) -> bool:
    """
    简单关键词过滤：判断文章是否与 AI 相关
    用于过滤 RSS 源中的非 AI 内容（如 36氪 的泛科技新闻）
    """
    ai_keywords = [
        "AI", "ai", "人工智能", "机器学习", "深度学习", "大模型", "LLM", "GPT",
        "OpenAI", "Google", "DeepMind", "Anthropic", "Claude", "Gemini",
        "Llama", "神经网络", "transformer", "transformer", "智能",
        "自然语言", "计算机视觉", "强化学习", "生成式", "AGI",
        "Agent", "RAG", "推理", "训练", "参数", "开源模型",
        "Stable Diffusion", "Midjourney", "Sora", "多模态",
        "Copilot", "ChatGPT", "具身智能", "机器人",
        "芯片", "GPU", "NVIDIA", "算力", "H100",
        "token", "微调", "对齐", "RLHF", "预训练",
        "Vector", "Embedding", "向量", "检索增强",
    ]
    text = f"{title} {summary}"
    return any(kw.lower() in text.lower() for kw in ai_keywords)


# ==================== 爬虫核心 ====================

def fetch_feed(source: dict) -> list[dict]:
    """
    从单个 RSS 源抓取文章列表
    返回文章 dict 列表，失败返回空列表
    """
    articles = []
    try:
        resp = requests.get(
            source["url"],
            headers=HEADERS,
            timeout=TIMEOUT,
            allow_redirects=True,
        )
        resp.raise_for_status()

        # feedparser 可以解析 RSS 2.0, Atom, RSS 1.0 等多种格式
        feed = feedparser.parse(resp.content)

        if feed.bozo and not feed.entries:
            print(f"  ⚠ {source['name']}: 解析失败 - {feed.bozo_exception}")
            return []

        for entry in feed.entries[:30]:  # 每个源最多取 30 条
            title = (entry.get("title") or "").strip()
            link = (entry.get("link") or entry.get("id") or "").strip()
            summary_raw = entry.get("summary") or entry.get("description") or ""
            summary = clean_html(summary_raw)
            published = entry.get("published") or entry.get("updated") or ""

            if not title or not link:
                continue

            # 过滤非 AI 相关内容
            if not is_ai_related(title, summary):
                continue

            article = {
                "id": make_article_id(title, link),
                "title": title,
                "url": link,
                "summary": summary[:500],  # 截取前 500 字
                "source_name": source["name"],
                "source_authority": source["authority"],
                "category": source["category"],
                "lang": source["lang"],
                "published": parse_date(published),
                "crawled_at": datetime.now().isoformat(),
            }
            articles.append(article)

        print(f"  ✓ {source['name']}: {len(articles)} 条")
        return articles

    except requests.RequestException as e:
        print(f"  ✗ {source['name']}: 请求失败 - {e}")
        return []
    except Exception as e:
        print(f"  ✗ {source['name']}: 未知错误 - {e}")
        return []


def deduplicate_articles(all_articles: list[dict]) -> list[dict]:
    """按 ID 去重，保留最早出现的那条"""
    seen = {}
    for art in sorted(all_articles, key=lambda a: a.get("published", "")):
        aid = art["id"]
        if aid not in seen:
            seen[aid] = art
    return list(seen.values())


def filter_by_date(articles: list[dict], days: int = DEDUP_WINDOW_DAYS) -> list[dict]:
    """只保留最近 N 天的文章"""
    cutoff = datetime.now() - timedelta(days=days)
    filtered = []
    for art in articles:
        try:
            pub_date = date_parser.parse(art["published"])
            if pub_date.replace(tzinfo=None) >= cutoff:
                filtered.append(art)
        except Exception:
            # 解析失败的保留
            filtered.append(art)
    return filtered


def save_articles(articles: list[dict], filepath: str):
    """保存文章到 JSON 文件"""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(articles, f, ensure_ascii=False, indent=2)
    print(f"\n💾 已保存 {len(articles)} 条文章到 {filepath}")


# ==================== 主入口 ====================

def main():
    print("=" * 60)
    print("📡 AI 资讯爬虫启动")
    print(f"   时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   数据源: {len(RSS_SOURCES)} 个")
    print("=" * 60)
    print()

    all_articles = []

    for source in RSS_SOURCES:
        print(f"🔍 [{source['name']}] {source['url']}")
        articles = fetch_feed(source)
        all_articles.extend(articles)
        # 礼貌延迟，避免请求过于密集
        time.sleep(0.5)

    print(f"\n📊 总计爬取: {len(all_articles)} 条（去重前）")

    # 去重
    unique = deduplicate_articles(all_articles)
    print(f"📊 去重后: {len(unique)} 条")

    # 时间过滤
    recent = filter_by_date(unique)
    print(f"📊 时间过滤后 (最近{DEDUP_WINDOW_DAYS}天): {len(recent)} 条")

    # 按发布时间倒序排列
    recent.sort(
        key=lambda a: date_parser.parse(a.get("published", "")),
        reverse=True,
    )

    # 输出统计
    source_counts = {}
    for art in recent:
        src = art["source_name"]
        source_counts[src] = source_counts.get(src, 0) + 1

    print("\n📊 各来源统计:")
    for src, count in sorted(source_counts.items(), key=lambda x: -x[1]):
        print(f"   {src}: {count} 条")

    # 保存
    save_articles(recent, RAW_ARTICLES_FILE)

    # 返回文章数量供后续脚本使用
    return len(recent)


if __name__ == "__main__":
    count = main()
    # 将数量写入临时文件，供 GitHub Actions 步骤间传递
    with open(os.path.join(DATA_DIR, "crawl_count.txt"), "w") as f:
        f.write(str(count))
    sys.exit(0)
