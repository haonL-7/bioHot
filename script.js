/**
 * Co-Metabolism Evidence Monitor
 */
(function () {
    'use strict';

    var state = {
        papers: [],
        filtered: [],
        searchQuery: '',
        evidenceFilter: 'all',
        typeFilter: 'all',
        nodeFilter: null,
        sortBy: 'evidence',
    };

    // ---- Data loading ----
    function loadData() {
        fetch('data/news.json')
            .then(function (resp) {
                if (!resp.ok) throw new Error('HTTP ' + resp.status);
                return resp.json();
            })
            .then(function (data) {
                state.papers = data.papers || [];
                state.filtered = state.papers.slice();
                renderStats();
                renderNodeFilters();
                applyAllFilters();
                var loading = document.getElementById('feedLoading');
                if (loading) loading.style.display = 'none';
            })
            .catch(function (err) {
                var loading = document.getElementById('feedLoading');
                if (loading) loading.textContent = 'Data unavailable.';
                console.error(err);
            });
    }

    // ---- Stats ----
    function renderStats() {
        var papers = state.papers;
        document.getElementById('statTotal').textContent = papers.length || '--';

        var l4 = 0, l3plus = 0;
        var allNodes = {};
        papers.forEach(function (p) {
            var lv = p.evidenceLevel || '';
            if (lv === 'L4') l4++;
            if (lv === 'L4' || lv === 'L3') l3plus++;
            (p.nodes || []).forEach(function (n) { allNodes[n] = true; });
        });
        document.getElementById('statL4').textContent = l4 || '--';
        document.getElementById('statL3').textContent = l3plus || '--';
        document.getElementById('statNodes').textContent = Object.keys(allNodes).length || '--';
    }

    // ---- Node filter chips ----
    function renderNodeFilters() {
        var counts = {};
        state.papers.forEach(function (p) {
            (p.nodes || []).forEach(function (n) {
                counts[n] = (counts[n] || 0) + 1;
            });
        });

        var nodeOrder = ['Butyrate/SCFAs', 'Bile Acids', 'Tryptophan Metabolites', 'Polyamines', 'Vitamin B12'];
        var html = '';
        nodeOrder.forEach(function (n) {
            if (counts[n]) {
                html += '<span class="node-chip" data-node="' + n + '">' + n + ' (' + counts[n] + ')</span>';
            }
        });
        var container = document.getElementById('nodeFilters');
        if (container) container.innerHTML = html;

        container.querySelectorAll('.node-chip').forEach(function (chip) {
            chip.addEventListener('click', function () {
                var node = chip.getAttribute('data-node');
                state.nodeFilter = state.nodeFilter === node ? null : node;
                container.querySelectorAll('.node-chip').forEach(function (c) {
                    c.classList.toggle('active', c.getAttribute('data-node') === state.nodeFilter);
                });
                applyAllFilters();
            });
        });
    }

    // ---- Filtering ----
    function applyAllFilters() {
        var items = state.papers.slice();

        // Search
        if (state.searchQuery) {
            var q = state.searchQuery.toLowerCase();
            items = items.filter(function (p) {
                return (p.title || '').toLowerCase().indexOf(q) >= 0 ||
                    (p.abstract || '').toLowerCase().indexOf(q) >= 0 ||
                    (p.journal || '').toLowerCase().indexOf(q) >= 0 ||
                    (p.firstAuthor || '').toLowerCase().indexOf(q) >= 0 ||
                    (p.nodes || []).some(function (n) { return n.toLowerCase().indexOf(q) >= 0; });
            });
        }

        // Evidence filter
        if (state.evidenceFilter !== 'all') {
            items = items.filter(function (p) { return p.evidenceLevel === state.evidenceFilter; });
        }

        // Type filter
        if (state.typeFilter === 'knowledge_base') {
            items = items.filter(function (p) { return (p.type || p.source) === 'knowledge_base'; });
        } else if (state.typeFilter === 'daily') {
            items = items.filter(function (p) { return (p.type || p.source) !== 'knowledge_base'; });
        }

        // Node filter
        if (state.nodeFilter) {
            items = items.filter(function (p) { return (p.nodes || []).indexOf(state.nodeFilter) >= 0; });
        }

        // Sort
        var levelOrder = { L4: 5, L3: 4, L2b: 3, L2a: 2, L1: 1 };
        if (state.sortBy === 'date') {
            items.sort(function (a, b) { return (b.pubDate || '').localeCompare(a.pubDate || ''); });
        } else if (state.sortBy === 'score') {
            items.sort(function (a, b) { return (b.totalScore || 0) - (a.totalScore || 0); });
        } else {
            items.sort(function (a, b) {
                var la = levelOrder[a.evidenceLevel] || 0;
                var lb = levelOrder[b.evidenceLevel] || 0;
                if (la !== lb) return lb - la;
                return (b.totalScore || 0) - (a.totalScore || 0);
            });
        }

        state.filtered = items;
        renderFeed(items);
    }

    // ---- Rendering ----
    function renderFeed(items) {
        var feed = document.getElementById('feed');
        // Remove existing cards
        var existing = feed.querySelectorAll('.paper-card');
        for (var i = 0; i < existing.length; i++) {
            existing[i].parentNode.removeChild(existing[i]);
        }

        var empty = document.getElementById('feedEmpty');
        if (empty) empty.style.display = items.length === 0 ? 'block' : 'none';

        if (items.length === 0) return;

        var template = document.getElementById('paperCard');
        if (!template) return;

        items.forEach(function (paper) {
            var card = template.content.cloneNode(true);

            var isKB = (paper.type || paper.source) === 'knowledge_base';
            var article = card.querySelector('article');
            if (article) {
                if (isKB) article.className += ' kb-entry';
            }

            // Journal
            var jnEl = card.querySelector('.paper-journal');
            if (jnEl) {
                jnEl.textContent = paper.journal || paper.source || '';
            }

            // Badges
            var badgesEl = card.querySelector('.paper-badges');
            if (badgesEl) {
                if (paper.researchPriority) {
                    var prio = document.createElement('span');
                    prio.className = 'priority-badge priority-' + paper.researchPriority.toLowerCase();
                    prio.textContent = paper.researchPriority;
                    badgesEl.appendChild(prio);
                }
                if (isKB) {
                    var kbBadge = document.createElement('span');
                    kbBadge.className = 'kb-badge';
                    kbBadge.textContent = 'Curated';
                    badgesEl.appendChild(kbBadge);
                }
            }

            // Date
            var dateEl = card.querySelector('.paper-date');
            if (dateEl) dateEl.textContent = paper.pubDate || '';

            // Evidence level badge
            var badge = card.querySelector('.level-badge');
            if (badge) {
                var level = paper.evidenceLevel || 'L1';
                badge.textContent = level;
                badge.className = 'level-badge level-' + level.toLowerCase();
            }

            // Title
            var titleLink = card.querySelector('.paper-title a');
            if (titleLink) {
                titleLink.textContent = paper.title || '';
                if (paper.url) {
                    titleLink.setAttribute('href', paper.url);
                } else {
                    titleLink.removeAttribute('href');
                }
            }

            // Evidence levels line
            var levelsEl = card.querySelector('.paper-evidence-levels');
            if (levelsEl) {
                var parts = [];
                if (paper.porcineEvidenceLevel) parts.push('Porcine: ' + paper.porcineEvidenceLevel);
                if (paper.murineEvidenceLevel) parts.push('Murine: ' + paper.murineEvidenceLevel);
                if (parts.length > 0) {
                    levelsEl.textContent = parts.join(' | ');
                } else if (paper.modelSystem) {
                    levelsEl.textContent = paper.modelSystem;
                }
            }

            // Abstract
            var absEl = card.querySelector('.paper-abstract');
            if (absEl) absEl.textContent = paper.abstract || '';

            // Nodes
            var nodesEl = card.querySelector('.paper-nodes');
            if (nodesEl) {
                (paper.nodes || []).forEach(function (node) {
                    var tag = document.createElement('span');
                    tag.className = 'node-tag';
                    tag.textContent = node;
                    nodesEl.appendChild(tag);
                });
            }

            // Matrix bars
            var matrixItems = card.querySelectorAll('.matrix-item');
            var dims = [paper.effectiveness || 0, paper.safety || 0, paper.coupling || 0, paper.measurementDepth || 0];
            for (var i = 0; i < matrixItems.length; i++) {
                var val = dims[i] || 0;
                var fillEl = matrixItems[i].querySelector('.matrix-fill');
                var valEl = matrixItems[i].querySelector('.matrix-val');
                if (fillEl) fillEl.style.width = (val / 5 * 100) + '%';
                if (valEl) valEl.textContent = val + '/5';
            }

            // Summary
            var sumEl = card.querySelector('.paper-summary');
            if (sumEl) sumEl.textContent = paper.summary || '';

            // Limitation
            var limEl = card.querySelector('.paper-limitation');
            if (limEl) limEl.textContent = paper.keyLimitation ? 'Limitation: ' + paper.keyLimitation : '';

            feed.appendChild(card);
        });
    }

    // ---- Events ----
    var searchTimer;
    var searchInput = document.getElementById('searchInput');
    if (searchInput) {
        searchInput.addEventListener('input', function () {
            clearTimeout(searchTimer);
            searchTimer = setTimeout(function () {
                state.searchQuery = searchInput.value.trim();
                applyAllFilters();
            }, 250);
        });
    }

    document.querySelectorAll('.filter-group').forEach(function (group) {
        group.querySelectorAll('.filter-btn').forEach(function (btn) {
            btn.addEventListener('click', function () {
                group.querySelectorAll('.filter-btn').forEach(function (b) { b.classList.remove('active'); });
                btn.classList.add('active');

                if (btn.getAttribute('data-level') !== null) {
                    state.evidenceFilter = btn.getAttribute('data-level');
                } else if (btn.getAttribute('data-sort')) {
                    state.sortBy = btn.getAttribute('data-sort');
                } else if (btn.getAttribute('data-type')) {
                    state.typeFilter = btn.getAttribute('data-type');
                }
                applyAllFilters();
            });
        });
    });

    // ---- Init ----
    loadData();
})();
