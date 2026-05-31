#!/usr/bin/env python3
"""
构建脚本：编排爬虫 → AI 评估 → 生成前端数据
在 GitHub Actions 中按顺序执行，产出 gh-pages 部署所需文件
"""

import json
import os
import sys
import shutil
from datetime import datetime

# ==================== 配置 ====================

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
BUILD_DIR = os.path.join(PROJECT_ROOT, "_site")

RAW_ARTICLES_FILE = os.path.join(DATA_DIR, "raw_articles.json")
SCORED_ARTICLES_FILE = os.path.join(DATA_DIR, "scored_articles.json")
NEWS_JSON_FILE = os.path.join(DATA_DIR, "news.json")
STATS_FILE = os.path.join(DATA_DIR, "stats.json")


# ==================== 构建逻辑 ====================

def load_json(filepath: str) -> dict | list:
    """安全加载 JSON 文件"""
    if not os.path.exists(filepath):
        print(f"⚠ 文件不存在: {filepath}")
        return {}
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def build_news_data(scored_articles: list[dict]) -> list[dict]:
    """
    将评分后的文章转换为前端可直接使用的格式
    精简字段，减少前端加载的 JSON 体积
    """
    news_list = []
    for art in scored_articles:
        scores = art.get("scores", {})
        news_item = {
            "id": art.get("id", ""),
            "title": art.get("title", ""),
            "url": art.get("url", ""),
            "summary": art.get("summary", "")[:300],  # 最多 300 字摘要
            "source": art.get("source_name", ""),
            "date": art.get("published", ""),
            "lang": art.get("lang", "zh"),
            "category": art.get("category", ""),
            # 评分
            "authority": scores.get("authority", 5),
            "novelty": scores.get("novelty", 5),
            "value": scores.get("value", 5),
            "total": scores.get("total", 5),
            "tags": scores.get("tags", []),
            "reason": scores.get("reason", ""),
            "evalMethod": scores.get("eval_method", "local"),
        }
        news_list.append(news_item)

    # 按总分降序排列
    news_list.sort(key=lambda n: n["total"], reverse=True)
    return news_list


def build_stats(news_list: list[dict], eval_stats: dict) -> dict:
    """生成统计信息"""
    now = datetime.now()
    tags_counter = {}
    source_counter = {}
    total_auth = 0
    total_novelty = 0
    total_value = 0

    for item in news_list:
        # 标签统计
        for tag in item.get("tags", []):
            tags_counter[tag] = tags_counter.get(tag, 0) + 1
        # 来源统计
        src = item.get("source", "未知")
        source_counter[src] = source_counter.get(src, 0) + 1
        # 累计分数
        total_auth += item.get("authority", 5)
        total_novelty += item.get("novelty", 5)
        total_value += item.get("value", 5)

    n = max(len(news_list), 1)

    return {
        "updated_at": now.isoformat(),
        "updated_at_human": now.strftime("%Y-%m-%d %H:%M"),
        "total_articles": len(news_list),
        "avg_authority": round(total_auth / n, 1),
        "avg_novelty": round(total_novelty / n, 1),
        "avg_value": round(total_value / n, 1),
        "top_tags": sorted(tags_counter.items(), key=lambda x: -x[1])[:10],
        "source_distribution": source_counter,
        "eval_methods": {
            "deepseek": eval_stats.get("deepseek", 0),
            "glm": eval_stats.get("glm", 0),
            "local": eval_stats.get("local", 0),
        },
    }


def create_build_dir():
    """创建构建输出目录"""
    if os.path.exists(BUILD_DIR):
        shutil.rmtree(BUILD_DIR)
    os.makedirs(BUILD_DIR, exist_ok=True)


def copy_frontend_files():
    """复制前端文件到构建目录，并确保 news.json 在正确位置"""
    # 复制 src 目录下所有文件
    src_path = SRC_DIR

    for filename in os.listdir(src_path):
        src_file = os.path.join(src_path, filename)
        dst_file = os.path.join(BUILD_DIR, filename)
        if os.path.isfile(src_file):
            shutil.copy2(src_file, dst_file)

    print(f"✓ 已复制前端文件到 {BUILD_DIR}")


def write_news_json(news_list: list[dict], stats: dict):
    """将新闻数据和统计写入构建目录"""
    payload = {
        "stats": stats,
        "news": news_list,
    }

    # 写入构建目录（供 gh-pages 部署）
    build_data_dir = os.path.join(BUILD_DIR, "data")
    os.makedirs(build_data_dir, exist_ok=True)
    news_json_path = os.path.join(build_data_dir, "news.json")
    with open(news_json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    # 同时写入 data 目录（备用）
    with open(NEWS_JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    file_size = os.path.getsize(news_json_path)
    print(f"✓ 已生成 news.json ({file_size / 1024:.1f} KB)")

    # 写入统计文件
    stats_path = os.path.join(DATA_DIR, "stats.json")
    with open(stats_path, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)


def create_nojekyll():
    """创建 .nojekyll 文件（告诉 GitHub Pages 不要用 Jekyll 处理）"""
    nojekyll_path = os.path.join(BUILD_DIR, ".nojekyll")
    with open(nojekyll_path, "w") as f:
        f.write("")
    print("✓ 已创建 .nojekyll")


def print_summary(news_list: list[dict], stats: dict):
    """打印构建摘要"""
    print("\n" + "=" * 60)
    print("📊 构建摘要")
    print("=" * 60)
    print(f"   文章总数: {stats['total_articles']}")
    print(f"   平均权威度: {stats['avg_authority']}")
    print(f"   平均新颖度: {stats['avg_novelty']}")
    print(f"   平均价值度: {stats['avg_value']}")
    print(f"   更新时间: {stats['updated_at_human']}")
    print(f"\n   TOP 5 文章:")
    for i, item in enumerate(news_list[:5], 1):
        title = item.get("title", "")[:50]
        total = item.get("total", 0)
        print(f"   {i}. [{total}分] {title}...")
    print(f"\n   热门标签: {', '.join([t[0] for t in stats['top_tags'][:5]])}")
    print("=" * 60)


# ==================== 主入口 ====================

def main():
    print("=" * 60)
    print("🏗️  构建脚本启动")
    print(f"   时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # 步骤 1: 加载评分后的文章
    print("\n📖 步骤 1/4: 加载评分文章...")
    scored_articles = load_json(SCORED_ARTICLES_FILE)
    if not scored_articles or not isinstance(scored_articles, list):
        # 回退到原始文章（如果评估未运行）
        print("⚠ 未找到评分文章，尝试加载原始文章...")
        raw = load_json(RAW_ARTICLES_FILE)
        if raw and isinstance(raw, list):
            scored_articles = raw
            print(f"✓ 回退到原始文章: {len(raw)} 条")
        else:
            print("✗ 无可用数据！请先运行 crawler.py 和 ai_evaluator.py")
            # 生成空数据，让网站至少能显示
            scored_articles = []
    else:
        print(f"✓ 加载评分文章: {len(scored_articles)} 条")

    # 步骤 2: 转换为前端格式
    print("\n🔧 步骤 2/4: 转换数据格式...")
    news_list = build_news_data(scored_articles)
    print(f"✓ 转换完成: {len(news_list)} 条")

    # 加载评估统计
    eval_stats = {}
    stats_file = os.path.join(DATA_DIR, "eval_stats.txt")
    if os.path.exists(stats_file):
        with open(stats_file, "r", encoding="utf-8") as f:
            for pair in f.read().strip().split(","):
                if "=" in pair:
                    k, v = pair.split("=", 1)
                    try:
                        eval_stats[k] = int(v)
                    except ValueError:
                        eval_stats[k] = v

    # 步骤 3: 生成统计 & 构建目录
    print("\n📦 步骤 3/4: 构建静态文件...")
    stats = build_stats(news_list, eval_stats)
    create_build_dir()
    copy_frontend_files()
    write_news_json(news_list, stats)
    create_nojekyll()
    print(f"✓ 构建目录准备就绪: {BUILD_DIR}")

    # 步骤 4: 摘要
    print("\n✅ 步骤 4/4: 构建完成!")
    print_summary(news_list, stats)

    return 0


if __name__ == "__main__":
    sys.exit(main())
