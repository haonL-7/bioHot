/**
 * AI 每日热点 — 前端逻辑
 * 功能：加载 JSON 数据、渲染卡片、搜索、排序、标签筛选
 * 所有操作均为本地执行，0 后端消耗
 */

(function () {
    'use strict';

    // ==================== 全局状态 ====================
    const state = {
        news: [],           // 全部文章
        filtered: [],       // 过滤后的文章
        stats: null,        // 统计信息
        searchQuery: '',    // 搜索关键词
        sortBy: 'total',    // 排序方式: total | date | value
        activeTag: null,    // 当前选中的标签筛选（null=全部）
    };

    // ==================== DOM 元素 ====================
    const $ = (sel) => document.querySelector(sel);
    const $$ = (sel) => document.querySelectorAll(sel);

    const dom = {
        feed: $('#feed'),
        feedLoading: $('#feedLoading'),
        feedEmpty: $('#feedEmpty'),
        searchInput: $('#searchInput'),
        searchClear: $('#searchClear'),
        sortBtns: $$('.sort-btn'),
        tagFilters: $('#tagFilters'),
        updateTime: $('#updateTime'),
        statTotal: $('#statTotal'),
        statAuth: $('#statAuth'),
        statNovel: $('#statNovel'),
        statValue: $('#statValue'),
    };

    // ==================== 数据加载 ====================

    async function loadData() {
        try {
            const resp = await fetch('data/news.json');
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            const data = await resp.json();

            state.news = data.news || [];
            state.stats = data.stats || {};
            state.filtered = [...state.news];

            renderStats();
            renderTagFilters();
            sortAndRender();

            // 隐藏加载状态
            dom.feedLoading.style.display = 'none';
        } catch (err) {
            console.error('加载数据失败:', err);
            dom.feedLoading.innerHTML = `
                <p style="font-size:48px;margin-bottom:12px;">📡</p>
                <p>数据加载失败</p>
                <p style="font-size:13px;color:#8b949e;margin-top:4px;">
                    请确保 data/news.json 文件存在。<br>
                    如果是首次使用，请先运行 GitHub Actions 生成数据。
                </p>
            `;
        }
    }

    // ==================== 统计栏 ====================

    function renderStats() {
        const s = state.stats;
        dom.statTotal.textContent = s.total_articles || state.news.length || '--';
        dom.statAuth.textContent = s.avg_authority || '--';
        dom.statNovel.textContent = s.avg_novelty || '--';
        dom.statValue.textContent = s.avg_value || '--';

        if (s.updated_at_human) {
            dom.updateTime.textContent = `数据更新于 ${s.updated_at_human}（北京时间）`;
        } else {
            dom.updateTime.textContent = '等待首次数据生成...';
        }
    }

    // ==================== 标签筛选 ====================

    function renderTagFilters() {
        // 收集所有标签并统计频次
        const tagCount = {};
        state.news.forEach(item => {
            (item.tags || []).forEach(tag => {
                tagCount[tag] = (tagCount[tag] || 0) + 1;
            });
        });

        // 取 TOP 15 标签
        const topTags = Object.entries(tagCount)
            .sort((a, b) => b[1] - a[1])
            .slice(0, 15);

        dom.tagFilters.innerHTML = topTags
            .map(([tag, count]) =>
                `<button class="tag-chip" data-tag="${escapeHtml(tag)}">${escapeHtml(tag)} <small>(${count})</small></button>`
            )
            .join('');

        // 绑定事件
        dom.tagFilters.querySelectorAll('.tag-chip').forEach(chip => {
            chip.addEventListener('click', () => {
                const tag = chip.dataset.tag;
                if (state.activeTag === tag) {
                    state.activeTag = null;
                } else {
                    state.activeTag = tag;
                }
                updateTagChips();
                applyFilters();
            });
        });
    }

    function updateTagChips() {
        dom.tagFilters.querySelectorAll('.tag-chip').forEach(chip => {
            chip.classList.toggle('active', chip.dataset.tag === state.activeTag);
        });
    }

    // ==================== 搜索 & 过滤 ====================

    function applyFilters() {
        let items = [...state.news];

        // 关键词搜索
        if (state.searchQuery) {
            const q = state.searchQuery.toLowerCase();
            items = items.filter(item => {
                return (
                    (item.title || '').toLowerCase().includes(q) ||
                    (item.summary || '').toLowerCase().includes(q) ||
                    (item.source || '').toLowerCase().includes(q) ||
                    (item.tags || []).some(t => t.toLowerCase().includes(q))
                );
            });
        }

        // 标签筛选
        if (state.activeTag) {
            items = items.filter(item =>
                (item.tags || []).includes(state.activeTag)
            );
        }

        state.filtered = items;
        sortAndRender();
    }

    function sortAndRender() {
        const items = [...state.filtered];

        // 排序
        switch (state.sortBy) {
            case 'date':
                items.sort((a, b) => (b.date || '').localeCompare(a.date || ''));
                break;
            case 'value':
                items.sort((a, b) => (b.value || 0) - (a.value || 0));
                break;
            case 'total':
            default:
                items.sort((a, b) => (b.total || 0) - (a.total || 0));
                break;
        }

        renderFeed(items);
    }

    // ==================== 文章列表渲染 ====================

    function renderFeed(items) {
        // 清除现有卡片
        const existingCards = dom.feed.querySelectorAll('.news-card');
        existingCards.forEach(c => c.remove());

        if (items.length === 0) {
            dom.feedEmpty.style.display = 'block';
        } else {
            dom.feedEmpty.style.display = 'none';
        }

        const template = $('#cardTemplate');
        const fragment = document.createDocumentFragment();

        items.forEach(item => {
            const card = template.content.cloneNode(true);

            // 来源 & 日期
            card.querySelector('.source-name').textContent = item.source || '未知来源';
            card.querySelector('.source-date').textContent = formatDate(item.date);

            // 分数
            const scoreEl = card.querySelector('.score-num');
            const total = item.total || 5;
            scoreEl.textContent = total;
            if (total >= 8) scoreEl.classList.add('high');
            else if (total >= 6) scoreEl.classList.add('mid');
            else scoreEl.classList.add('low');

            // 标题
            const titleLink = card.querySelector('.card-title a');
            titleLink.textContent = item.title || '(无标题)';
            titleLink.href = item.url || '#';
            if (!item.url) titleLink.removeAttribute('href');

            // 摘要
            card.querySelector('.card-summary').textContent = item.summary || '';

            // 标签
            const tagsContainer = card.querySelector('.card-tags');
            (item.tags || []).forEach(tag => {
                const tagEl = document.createElement('span');
                tagEl.className = 'tag';
                tagEl.textContent = tag;
                tagsContainer.appendChild(tagEl);
            });

            // 推荐理由
            card.querySelector('.card-reason').textContent = item.reason ? `💬 ${item.reason}` : '';

            // 三维评分
            const metrics = card.querySelectorAll('.card-metrics .metric');
            metrics[0].querySelector('strong').textContent = item.authority || '--';
            metrics[1].querySelector('strong').textContent = item.novelty || '--';
            metrics[2].querySelector('strong').textContent = item.value || '--';

            fragment.appendChild(card);
        });

        dom.feed.appendChild(fragment);
    }

    // ==================== 工具函数 ====================

    function formatDate(dateStr) {
        if (!dateStr) return '';
        try {
            const d = new Date(dateStr);
            const now = new Date();
            const diffMs = now - d;
            const diffH = Math.floor(diffMs / 3600000);
            const diffD = Math.floor(diffMs / 86400000);

            if (diffH < 1) return '刚刚';
            if (diffH < 24) return `${diffH} 小时前`;
            if (diffD < 7) return `${diffD} 天前`;

            const month = d.getMonth() + 1;
            const day = d.getDate();
            return `${month}月${day}日`;
        } catch {
            return dateStr;
        }
    }

    function escapeHtml(str) {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    // ==================== 事件绑定 ====================

    // 搜索输入
    let searchTimeout;
    dom.searchInput.addEventListener('input', () => {
        const val = dom.searchInput.value.trim();
        dom.searchClear.classList.toggle('visible', val.length > 0);

        clearTimeout(searchTimeout);
        searchTimeout = setTimeout(() => {
            state.searchQuery = val;
            applyFilters();
        }, 250);
    });

    // 清除搜索
    dom.searchClear.addEventListener('click', () => {
        dom.searchInput.value = '';
        dom.searchClear.classList.remove('visible');
        state.searchQuery = '';
        applyFilters();
    });

    // 排序按钮
    dom.sortBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            dom.sortBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            state.sortBy = btn.dataset.sort;
            sortAndRender();
        });
    });

    // ==================== 初始化 ====================

    loadData();
})();
