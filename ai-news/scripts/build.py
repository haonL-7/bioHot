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
    Flatten nested evaluation structure -> frontend-friendly flat fields
    """
    papers = []
    for art in scored_articles:
        ev = art.get("evaluation", art.get("scores", {}))
        papers.append({
            "id": art.get("id", ""),
            "title": art.get("title", ""),
            "url": art.get("url", ""),
            "abstract": art.get("abstract", "")[:500],
            "journal": art.get("journal", art.get("source", "")),
            "doi": art.get("doi", ""),
            "pmid": art.get("pmid", ""),
            "firstAuthor": art.get("first_author", ""),
            "pubDate": art.get("pub_date", ""),
            "source": art.get("source", ""),
            # Evidence framework
            "evidenceLevel": ev.get("evidence_level", "L1"),
            "evidenceJustification": ev.get("evidence_justification", ""),
            "effectiveness": ev.get("effectiveness", 0),
            "safety": ev.get("safety", 0),
            "coupling": ev.get("coupling", 0),
            "measurementDepth": ev.get("measurement_depth", 0),
            "totalScore": ev.get("total_score", 0),
            "journalQuality": ev.get("journal_quality", "unknown"),
            "modelSystem": ev.get("model_system", ""),
            "porcineRelevant": ev.get("porcine_relevant", False),
            "keyLimitation": ev.get("key_limitation", ""),
            "nodes": ev.get("nodes", art.get("nodes", [])),
            "summary": ev.get("summary", ""),
            "evalMethod": ev.get("eval_method", "local"),
            "evalModel": ev.get("eval_model", ""),
        })

    level_order = {"L4": 5, "L3": 4, "L2b": 3, "L2a": 2, "L1": 1}
    papers.sort(key=lambda p: (
        -level_order.get(p["evidenceLevel"], 1),
        -p["totalScore"],
    ))
    return papers


def build_stats(papers: list[dict], eval_stats: dict) -> dict:
    """Generate stats from paper list"""
    now = datetime.now()
    node_counter = {}
    journal_counter = {}
    level_counter = {}
    total_eff = total_saf = total_cou = total_dep = 0

    for p in papers:
        for node in p.get("nodes", []):
            node_counter[node] = node_counter.get(node, 0) + 1
        jn = p.get("journal", "Unknown")
        journal_counter[jn] = journal_counter.get(jn, 0) + 1
        lv = p.get("evidenceLevel", "L1")
        level_counter[lv] = level_counter.get(lv, 0) + 1
        total_eff += p.get("effectiveness", 0)
        total_saf += p.get("safety", 0)
        total_cou += p.get("coupling", 0)
        total_dep += p.get("measurementDepth", 0)

    n = max(len(papers), 1)
    return {
        "updated_at": now.isoformat(),
        "updated_at_human": now.strftime("%Y-%m-%d %H:%M"),
        "total_papers": len(papers),
        "avg_effectiveness": round(total_eff / n, 1),
        "avg_safety": round(total_saf / n, 1),
        "avg_coupling": round(total_cou / n, 1),
        "avg_measurement_depth": round(total_dep / n, 1),
        "evidence_levels": level_counter,
        "node_distribution": node_counter,
        "journal_distribution": journal_counter,
        "eval_methods": eval_stats,
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
        "papers": news_list,
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
    print(f"   Papers: {stats['total_papers']}")
    print(f"   Avg Effectiveness: {stats['avg_effectiveness']}")
    print(f"   Avg Safety: {stats['avg_safety']}")
    print(f"   Avg Coupling: {stats['avg_coupling']}")
    print(f"   Avg Meas. Depth: {stats['avg_measurement_depth']}")
    print(f"   Evidence levels: {stats['evidence_levels']}")
    print(f"   Updated: {stats['updated_at_human']}")
    print(f"\n   Top nodes: {dict(sorted(stats['node_distribution'].items(), key=lambda x: -x[1])[:5])}")
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
