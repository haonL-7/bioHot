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

    // ---- Node filter chips (dynamic, with parent groups) ----
    function renderNodeFilters() {
        var counts = {};
        state.papers.forEach(function (p) {
            (p.nodes || []).forEach(function (n) {
                counts[n] = (counts[n] || 0) + 1;
            });
        });

        // Parent group → children mapping (must match NODE_GROUPS in crawler.py)
        var parentGroups = {
            'SCFAs': ['Butyrate', 'Propionate', 'Acetate', 'Branched SCFAs'],
            'Vitamin B Family': ['Vitamin B12', 'Folate/B9', 'Riboflavin/B2', 'Biotin/B7', 'B-Vitamins (B1/B3/B5/B6)'],
            'Fat-Soluble Vitamins': ['Vitamin A/Retinoic Acid', 'Vitamin D'],
            'Gut Strains': ['Phascolarctobacterium', 'Lactobacillus', 'Bifidobacterium', 'Bacteroides', 'Clostridium', 'Prevotella', 'Akkermansia', 'Faecalibacterium'],
        };
        var parentNames = Object.keys(parentGroups);

        // Build HTML: parent groups first, then children indented, then orphans
        var html = '';
        var rendered = {}; // track which nodes we've already rendered

        parentNames.forEach(function (parent) {
            if (!counts[parent]) return; // skip empty groups
            html += '<span class="node-chip parent-chip" data-node="' + parent + '" data-group="true">' + parent + ' (' + counts[parent] + ')</span>';
            rendered[parent] = true;
            // Render children
            (parentGroups[parent] || []).forEach(function (child) {
                if (counts[child] && !rendered[child]) {
                    html += '<span class="node-chip child-chip" data-node="' + child + '" data-parent="' + parent + '">' + child + ' (' + counts[child] + ')</span>';
                    rendered[child] = true;
                }
            });
        });

        // Standalone nodes (not in any parent group): metabolites without a parent
        var standaloneOrder = ['Bile Acids', 'Tryptophan Metabolites', 'Polyamines', 'Lactate', 'Succinate', 'GABA/Glutamate'];
        standaloneOrder.forEach(function (n) {
            if (counts[n] && !rendered[n]) {
                html += '<span class="node-chip" data-node="' + n + '">' + n + ' (' + counts[n] + ')</span>';
                rendered[n] = true;
            }
        });
        // Catch any remaining nodes
        Object.keys(counts).sort().forEach(function (n) {
            if (counts[n] && !rendered[n]) {
                html += '<span class="node-chip" data-node="' + n + '">' + n + ' (' + counts[n] + ')</span>';
                rendered[n] = true;
            }
        });

        var container = document.getElementById('nodeFilters');
        if (container) container.innerHTML = html;

        // Click handler: parent chips expand/shrink to show/hide children
        container.querySelectorAll('.node-chip').forEach(function (chip) {
            chip.addEventListener('click', function () {
                var node = chip.getAttribute('data-node');
                var isGroup = chip.getAttribute('data-group') === 'true';

                if (isGroup) {
                    // Toggle child visibility
                    var children = parentGroups[node] || [];
                    var isExpanded = chip.classList.contains('expanded');
                    if (isExpanded) {
                        // Collapse: hide children, set filter to parent only
                        chip.classList.remove('expanded');
                        container.querySelectorAll('.child-chip[data-parent="' + node + '"]').forEach(function (c) {
                            c.style.display = 'none';
                        });
                    } else {
                        // Expand: show children, keep parent filter
                        chip.classList.add('expanded');
                        container.querySelectorAll('.child-chip[data-parent="' + node + '"]').forEach(function (c) {
                            c.style.display = '';
                        });
                    }
                }

                // Toggle active filter
                state.nodeFilter = state.nodeFilter === node ? null : node;
                container.querySelectorAll('.node-chip').forEach(function (c) {
                    c.classList.toggle('active', c.getAttribute('data-node') === state.nodeFilter);
                });
                applyAllFilters();
            });
        });

        // Initially collapse child chips
        container.querySelectorAll('.child-chip').forEach(function (c) {
            c.style.display = 'none';
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

        // Node filter — parent groups match all children
        if (state.nodeFilter) {
            var parentGroups = {
                'SCFAs': ['Butyrate', 'Propionate', 'Acetate', 'Branched SCFAs'],
                'Vitamin B Family': ['Vitamin B12', 'Folate/B9', 'Riboflavin/B2', 'Biotin/B7', 'B-Vitamins (B1/B3/B5/B6)'],
                'Fat-Soluble Vitamins': ['Vitamin A/Retinoic Acid', 'Vitamin D'],
                'Gut Strains': ['Phascolarctobacterium', 'Lactobacillus', 'Bifidobacterium', 'Bacteroides', 'Clostridium', 'Prevotella', 'Akkermansia', 'Faecalibacterium'],
            };
            var matchNodes = parentGroups[state.nodeFilter] || [state.nodeFilter];
            items = items.filter(function (p) {
                return (p.nodes || []).some(function (n) {
                    return matchNodes.indexOf(n) >= 0;
                });
            });
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

            // Title — clicking opens evaluation detail modal
            var titleLink = card.querySelector('.paper-title a');
            if (titleLink) {
                titleLink.textContent = paper.title || '';
                titleLink.setAttribute('href', '#');
                titleLink.className = 'paper-title-link';
                titleLink.setAttribute('data-paper-id', paper.id || '');
                titleLink.addEventListener('click', function (e) {
                    e.preventDefault();
                    openEvaluationModal(paper.id);
                });
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

            // Multi-backup links (only render valid URLs)
            var linksEl = card.querySelector('.paper-links');
            if (linksEl) {
                var links = paper.links || [];
                if (links.length === 0 && paper.url && paper.url.trim()) {
                    links = [{type: 'primary', label: 'Source', url: paper.url}];
                }
                var validLinks = links.filter(function (l) { return l.url && l.url.trim(); });
                if (validLinks.length > 0) {
                    validLinks.forEach(function (link) {
                        var a = document.createElement('a');
                        a.href = link.url;
                        a.target = '_blank';
                        a.rel = 'noopener noreferrer';
                        a.className = 'paper-link paper-link-' + (link.type || 'primary');
                        a.textContent = link.label || 'Link';
                        linksEl.appendChild(a);
                    });
                    // Broken link report button
                    var reportBtn = document.createElement('button');
                    reportBtn.className = 'report-broken-btn';
                    reportBtn.setAttribute('data-paper-id', paper.id || '');
                    reportBtn.title = 'Report broken link';
                    reportBtn.textContent = 'Report';
                    reportBtn.addEventListener('click', function (e) {
                        e.preventDefault();
                        e.stopPropagation();
                        reportBrokenLink(paper.id, paper.title);
                    });
                    linksEl.appendChild(reportBtn);
                } else {
                    linksEl.style.display = 'none';
                }
            }

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

    // ---- Evaluation Detail Modal ----
    function openEvaluationModal(paperId) {
        if (!paperId) return;
        // Find paper: try state.papers first, then embedded __PAPERS__ fallback
        var paper = null;
        var search = state.papers.length > 0 ? state.papers : (window.__PAPERS__ || []);
        for (var i = 0; i < search.length; i++) {
            if (search[i].id === paperId) { paper = search[i]; break; }
        }
        if (!paper) return;

        var modal = document.getElementById('evalModal');
        var content = document.getElementById('modalContent');
        if (!modal || !content) return;

        var lv = paper.evidenceLevel || 'L1';
        var isKB = (paper.type || paper.source) === 'knowledge_base';

        // Build badges
        var badgesHtml = '';
        if (paper.researchPriority) {
            badgesHtml += '<span class="priority-badge priority-' + paper.researchPriority.toLowerCase() + '">' + paper.researchPriority + '</span>';
        }
        if (isKB) {
            badgesHtml += '<span class="kb-badge">Curated</span>';
        }

        // Evidence levels comparison
        var evParts = [];
        if (paper.porcineEvidenceLevel) evParts.push('Porcine: ' + paper.porcineEvidenceLevel);
        if (paper.murineEvidenceLevel) evParts.push('Murine: ' + paper.murineEvidenceLevel);
        var evLine = evParts.length > 0 ? evParts.join(' | ') : (paper.modelSystem || '');

        // 4-D Matrix
        var dims = [
            {id: 'effectiveness', label: 'Forward (Microbe→Host)', val: paper.effectiveness || 0},
            {id: 'safety', label: 'Reverse (Host→Microbiome)', val: paper.safety || 0},
            {id: 'coupling', label: 'Bidirectional Coupling', val: paper.coupling || 0},
            {id: 'depth', label: 'Measurement Depth', val: paper.measurementDepth || 0}
        ];
        var matrixHtml = '';
        dims.forEach(function (d) {
            var pct = d.val / 5 * 100;
            matrixHtml += '<div class="matrix-item" data-dim="' + d.id + '">' +
                '<span class="matrix-label">' + d.label + '</span>' +
                '<span class="matrix-bar"><span class="matrix-fill" style="width:' + pct + '%"></span></span>' +
                '<span class="matrix-val">' + d.val + '/5</span></div>';
        });

        // Forward/Reverse justifications
        var fwdJust = paper.forwardJustification || '';
        var revJust = paper.reverseJustification || '';

        // Nodes
        var nodesHtml = '';
        (paper.nodes || []).forEach(function (n) {
            if (n.indexOf('SCFAs') >= 0 || n.indexOf('Vitamin') >= 0 || n.indexOf('Gut Strains') >= 0) return; // skip parent groups in modal
            nodesHtml += '<span class="node-tag">' + n + '</span>';
        });

        // External links
        var allLinks = paper.links || [];
        if (allLinks.length === 0 && paper.url && paper.url.trim()) {
            allLinks = [{type: 'primary', label: 'Source', url: paper.url}];
        }
        var extLinksHtml = '';
        var validLinks = allLinks.filter(function (l) { return l.url && l.url.trim(); });
        if (validLinks.length > 0) {
            extLinksHtml = '<div class="modal-links"><h3>Original Paper Links</h3>';
            validLinks.forEach(function (l) {
                extLinksHtml += '<a href="' + l.url + '" target="_blank" rel="noopener noreferrer" class="paper-link paper-link-' + (l.type || 'primary') + '">' + (l.label || 'Link') + '</a> ';
            });
            extLinksHtml += '</div>';
        } else {
            extLinksHtml = '<p class="modal-no-link">No external link available (curated knowledge base entry)</p>';
        }

        content.innerHTML =
            '<div class="modal-header">' +
                '<span class="paper-journal">' + (paper.journal || '') + '</span>' +
                '<div class="paper-badges" style="display:inline;margin-left:8px;">' + badgesHtml + '</div>' +
                '<span class="level-badge level-' + lv.toLowerCase() + '">' + lv + '</span>' +
            '</div>' +
            '<h1 class="modal-title">' + (paper.title || '') + '</h1>' +
            '<p class="modal-evidence">' + evLine + '</p>' +
            '<div class="modal-section"><h3>Evidence Justification</h3><p>' + (paper.evidenceJustification || 'Not provided.') + '</p></div>' +
            (fwdJust ? '<div class="modal-section"><h3>Forward Pathway (Microbe→Host)</h3><p>' + fwdJust + '</p></div>' : '') +
            (revJust ? '<div class="modal-section"><h3>Reverse Pathway (Host→Microbiome)</h3><p>' + revJust + '</p></div>' : '') +
            '<div class="modal-section"><h3>Four-Dimensional Matrix</h3><div class="paper-matrix" style="grid-template-columns: repeat(2,1fr);">' + matrixHtml + '</div></div>' +
            '<div class="modal-section"><h3>Model System</h3><p>' + (paper.modelSystem || 'Not specified.') + '</p></div>' +
            '<div class="modal-section"><h3>Key Limitation</h3><p>' + (paper.keyLimitation || 'Not specified.') + '</p></div>' +
            '<div class="modal-section"><h3>Summary</h3><p>' + (paper.summary || '') + '</p></div>' +
            '<div class="modal-nodes">' + nodesHtml + '</div>' +
            extLinksHtml +
            '<p class="modal-meta">ID: ' + paperId + ' | Source: ' + (paper.source || 'unknown') + ' | Date: ' + (paper.pubDate || '') + '</p>';

        modal.style.display = 'flex';
        document.body.style.overflow = 'hidden';
    }

    function closeModal() {
        var modal = document.getElementById('evalModal');
        if (modal) modal.style.display = 'none';
        document.body.style.overflow = '';
    }

    // Modal event listeners
    var modalClose = document.getElementById('modalClose');
    if (modalClose) {
        modalClose.addEventListener('click', closeModal);
    }
    var modalOverlay = document.getElementById('evalModal');
    if (modalOverlay) {
        modalOverlay.addEventListener('click', function (e) {
            if (e.target === modalOverlay) closeModal();
        });
    }
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') closeModal();
    });

    // Click handlers for pre-rendered paper title links
    document.getElementById('feed').addEventListener('click', function (e) {
        var link = e.target.closest('.paper-title-link');
        if (link) {
            e.preventDefault();
            var paperId = link.getAttribute('data-paper-id');
            if (paperId) openEvaluationModal(paperId);
        }
    });

    // ---- Link health check (CORS-safe: uses img beacon) ----
    var brokenLinks = {}; // id -> {count, lastReported}

    function checkLinkHealth() {
        var links = document.querySelectorAll('.paper-link');
        links.forEach(function (link) {
            // Skip already-checked links
            if (link.dataset.checked === 'true') return;
            link.dataset.checked = 'true';

            var url = link.getAttribute('href');
            if (!url || url === '#') return;

            // Use Image beacon to check link (avoids CORS issues with fetch)
            var img = new Image();
            var timeout = setTimeout(function () {
                // Timeout = likely unreachable
                link.classList.add('link-unreachable');
                link.title = 'Link may be unavailable';
            }, 5000);

            img.onload = function () {
                clearTimeout(timeout);
                link.classList.add('link-ok');
            };
            img.onerror = function () {
                clearTimeout(timeout);
                // Error doesn't always mean broken — could be non-image URL
                // Mark as "uncertain" rather than broken
                link.classList.add('link-uncertain');
            };
            img.src = url;
        });
    }

    function reportBrokenLink(id, title) {
        if (!id) return;
        var now = new Date().toISOString();
        if (!brokenLinks[id]) {
            brokenLinks[id] = { count: 0, firstReported: now, title: title };
        }
        brokenLinks[id].count += 1;
        brokenLinks[id].lastReported = now;

        // Store in localStorage for persistence
        try {
            localStorage.setItem('brokenLinks', JSON.stringify(brokenLinks));
        } catch (e) { /* ignore */ }

        // Visual feedback
        var btn = document.querySelector('.report-broken-btn[data-paper-id=\"' + id + '\"]');
        if (btn) {
            btn.textContent = 'Reported';
            btn.classList.add('reported');
            setTimeout(function () { btn.textContent = 'Report'; btn.classList.remove('reported'); }, 2000);
        }

        console.log('Broken link reported:', id, title ? title.substring(0, 50) : '', 'Count:', brokenLinks[id].count);
    }

    function loadBrokenLinkReports() {
        try {
            var stored = localStorage.getItem('brokenLinks');
            if (stored) brokenLinks = JSON.parse(stored);
        } catch (e) { /* ignore */ }
    }

    // ---- Init ----
    loadBrokenLinkReports();
    loadData();

    // Run link health check after a short delay (let the page render first)
    setTimeout(function () {
        checkLinkHealth();
    }, 2000);
})();
