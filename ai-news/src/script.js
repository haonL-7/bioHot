/**
 * Co-Metabolism Evidence Monitor — Frontend
 * Evidence framework: 4-level tier + 4-dimensional matrix
 */

(function () {
    'use strict';

    const state = {
        papers: [],
        filtered: [],
        stats: null,
        searchQuery: '',
        evidenceFilter: 'all',
        nodeFilter: null,
        sortBy: 'evidence',
    };

    const dom = {
        feed: document.getElementById('feed'),
        feedLoading: document.getElementById('feedLoading'),
        feedEmpty: document.getElementById('feedEmpty'),
        searchInput: document.getElementById('searchInput'),
        updateTime: document.getElementById('updateTime'),
        statTotal: document.getElementById('statTotal'),
        statL4: document.getElementById('statL4'),
        statL3: document.getElementById('statL3'),
        statNodes: document.getElementById('statNodes'),
        nodeFilters: document.getElementById('nodeFilters'),
    };

    // ---- Data loading ----

    async function loadData() {
        try {
            const resp = await fetch('data/news.json');
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            const data = await resp.json();
            state.papers = data.papers || [];
            state.stats = data.stats || {};
            state.filtered = [...state.papers];
            renderStats();
            renderNodeFilters();
            applyAllFilters();
            dom.feedLoading.style.display = 'none';
        } catch (err) {
            dom.feedLoading.textContent = 'Data unavailable. Please run the workflow first.';
            console.error(err);
        }
    }

    // ---- Stats ----

    function renderStats() {
        const papers = state.papers;
        dom.statTotal.textContent = papers.length || '--';

        const l4 = papers.filter(p => (p.evidenceLevel || p.evidence_level) === 'L4').length;
        dom.statL4.textContent = l4 || '--';

        const l3plus = papers.filter(p =>
            ['L4', 'L3'].includes(p.evidenceLevel || p.evidence_level)
        ).length;
        dom.statL3.textContent = l3plus || '--';

        const allNodes = new Set();
        papers.forEach(p => (p.nodes || []).forEach(n => allNodes.add(n)));
        dom.statNodes.textContent = allNodes.size || '--';

        if (state.stats && state.stats.updated_at_human) {
            dom.updateTime.textContent = 'Last updated: ' + state.stats.updated_at_human + ' (UTC)';
        }
    }

    // ---- Node filter chips ----

    function renderNodeFilters() {
        const counts = {};
        state.papers.forEach(p => {
            (p.nodes || []).forEach(n => {
                counts[n] = (counts[n] || 0) + 1;
            });
        });

        const nodes = ['Butyrate/SCFAs', 'Bile Acids', 'Tryptophan Metabolites', 'Polyamines', 'Vitamin B12'];
        dom.nodeFilters.innerHTML = nodes
            .filter(n => counts[n])
            .map(n => `<span class="node-chip" data-node="${escapeHtml(n)}">${escapeHtml(n)}&nbsp;(${counts[n]})</span>`)
            .join('');

        dom.nodeFilters.querySelectorAll('.node-chip').forEach(chip => {
            chip.addEventListener('click', () => {
                const node = chip.dataset.node;
                state.nodeFilter = state.nodeFilter === node ? null : node;
                updateNodeChips();
                applyAllFilters();
            });
        });
    }

    function updateNodeChips() {
        dom.nodeFilters.querySelectorAll('.node-chip').forEach(chip => {
            chip.classList.toggle('active', chip.dataset.node === state.nodeFilter);
        });
    }

    // ---- Filtering ----

    function applyAllFilters() {
        let items = [...state.papers];

        // Search
        if (state.searchQuery) {
            const q = state.searchQuery.toLowerCase();
            items = items.filter(p =>
                (p.title || '').toLowerCase().includes(q) ||
                (p.abstract || '').toLowerCase().includes(q) ||
                (p.journal || '').toLowerCase().includes(q) ||
                (p.firstAuthor || p.first_author || '').toLowerCase().includes(q) ||
                (p.nodes || []).some(n => n.toLowerCase().includes(q))
            );
        }

        // Evidence level filter
        if (state.evidenceFilter !== 'all') {
            items = items.filter(p =>
                (p.evidenceLevel || p.evidence_level) === state.evidenceFilter
            );
        }

        // Node filter
        if (state.nodeFilter) {
            items = items.filter(p =>
                (p.nodes || []).includes(state.nodeFilter)
            );
        }

        // Sort
        const levelOrder = { L4: 5, L3: 4, L2b: 3, L2a: 2, L1: 1 };
        if (state.sortBy === 'date') {
            items.sort((a, b) => (b.pubDate || b.pub_date || '').localeCompare(a.pubDate || a.pub_date || ''));
        } else if (state.sortBy === 'score') {
            items.sort((a, b) => (b.totalScore || b.total_score || 0) - (a.totalScore || a.total_score || 0));
        } else {
            items.sort((a, b) => {
                const la = levelOrder[a.evidenceLevel || a.evidence_level] || 0;
                const lb = levelOrder[b.evidenceLevel || b.evidence_level] || 0;
                if (la !== lb) return lb - la;
                return (b.totalScore || b.total_score || 0) - (a.totalScore || a.total_score || 0);
            });
        }

        state.filtered = items;
        renderFeed(items);
    }

    // ---- Rendering ----

    function renderFeed(items) {
        // Remove existing cards
        dom.feed.querySelectorAll('.paper-card').forEach(c => c.remove());

        if (items.length === 0) {
            dom.feedEmpty.style.display = 'block';
        } else {
            dom.feedEmpty.style.display = 'none';
        }

        const template = document.getElementById('paperCard');
        const fragment = document.createDocumentFragment();

        items.forEach(paper => {
            const card = template.content.cloneNode(true);

            // Header
            card.querySelector('.paper-journal').textContent = paper.journal || paper.source || '';
            card.querySelector('.paper-date').textContent = formatDate(paper.pubDate || paper.pub_date);

            // Evidence level badge
            const level = paper.evidenceLevel || paper.evidence_level || 'L1';
            const badge = card.querySelector('.level-badge');
            badge.textContent = level;
            badge.className = 'level-badge level-' + level.toLowerCase();

            // Title
            const titleLink = card.querySelector('.paper-title a');
            titleLink.textContent = paper.title || '(No title)';
            titleLink.href = paper.url || '#';
            if (!paper.url) titleLink.removeAttribute('href');

            // Authors
            card.querySelector('.paper-authors').textContent = paper.firstAuthor || paper.first_author || '';

            // Abstract
            card.querySelector('.paper-abstract').textContent = paper.abstract || '';

            // Nodes
            const nodesContainer = card.querySelector('.paper-nodes');
            (paper.nodes || []).forEach(node => {
                const tag = document.createElement('span');
                tag.className = 'node-tag';
                tag.textContent = node;
                nodesContainer.appendChild(tag);
            });

            // Matrix bars
            const matrixItems = card.querySelectorAll('.matrix-item');
            const eff = paper.effectiveness || 0;
            const saf = paper.safety || 0;
            const cou = paper.coupling || 0;
            const dep = paper.measurementDepth || paper.measurement_depth || 0;
            const dims = [eff, saf, cou, dep];

            matrixItems.forEach((item, i) => {
                const val = dims[i] || 0;
                item.querySelector('.matrix-fill').style.width = (val / 5 * 100) + '%';
                item.querySelector('.matrix-val').textContent = val + '/5';
            });

            // Summary
            const summary = paper.summary || '';
            card.querySelector('.paper-summary').textContent = summary;

            // Limitation
            const limitation = paper.keyLimitation || paper.key_limitation || '';
            card.querySelector('.paper-limitation').textContent = limitation ? 'Limitation: ' + limitation : '';

            fragment.appendChild(card);
        });

        dom.feed.appendChild(fragment);
    }

    // ---- Helpers ----

    function formatDate(dateStr) {
        if (!dateStr) return '';
        try {
            const d = new Date(dateStr);
            const m = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
            return `${d.getDate()} ${m[d.getMonth()]} ${d.getFullYear()}`;
        } catch {
            return dateStr;
        }
    }

    function escapeHtml(str) {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    // ---- Events ----

    let searchTimer;
    dom.searchInput.addEventListener('input', () => {
        clearTimeout(searchTimer);
        searchTimer = setTimeout(() => {
            state.searchQuery = dom.searchInput.value.trim();
            applyAllFilters();
        }, 250);
    });

    document.querySelectorAll('.filter-group').forEach(group => {
        group.querySelectorAll('.filter-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const parent = btn.parentElement;
                parent.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');

                if (btn.dataset.level !== undefined) {
                    state.evidenceFilter = btn.dataset.level;
                } else if (btn.dataset.sort) {
                    state.sortBy = btn.dataset.sort;
                }
                applyAllFilters();
            });
        });
    });

    // ---- Init ----

    loadData();
})();
