/**
 * am_dashboard.js — Lógica de UI estática para AulaMetrics Dashboard.
 *
 * Extraído de dashboard_main_templates.xml (bloque CDATA) y de los bloques
 * de wordcloud de qualitative_dashboard_templates.xml.
 *
 * Expone funciones globales que los templates XML usan directamente:
 *   - togglePill, selectAllEvals, selectNoneEvals
 *   - navigateTo
 *   - loadSegmentationContent, loadQualitativeContent
 *   - window.amWordcloud.init(elementId, data, colors)
 *
 * No tiene dependencias externas salvo D3 (cargado por qualitative templates).
 */

/* ──────────────────────────────────────────────────────────────────────────
   FILTER PILLS (quantitative section)
   ────────────────────────────────────────────────────────────────────────── */

function togglePill(pill) {
    const isActive = pill.classList.toggle('active');
    pill.setAttribute('aria-checked', isActive ? 'true' : 'false');
}

function selectAllEvals() {
    document.querySelectorAll('.eval-pill').forEach(pill => {
        pill.classList.add('active');
        pill.setAttribute('aria-checked', 'true');
    });
}

function selectNoneEvals() {
    document.querySelectorAll('.eval-pill').forEach(pill => {
        pill.classList.remove('active');
        pill.setAttribute('aria-checked', 'false');
    });
}

/* ──────────────────────────────────────────────────────────────────────────
   FILTER PILLS — single-select / radio behaviour
   Used by qualitative and segmentation filters.
   ────────────────────────────────────────────────────────────────────────── */

function selectSinglePill(pill, value) {
    const container = pill.closest('.filter-pills-container');
    container.querySelectorAll('.filter-pill').forEach(p => {
        p.classList.remove('active');
        p.setAttribute('aria-pressed', 'false');
    });
    pill.classList.add('active');
    pill.setAttribute('aria-pressed', 'true');
    const hidden = pill.closest('form').querySelector('input[name="evaluation_id"]');
    if (hidden) hidden.value = value;
}

function resetSinglePill(form) {
    form.querySelectorAll('.eval-pill').forEach(p => {
        p.classList.remove('active');
        p.setAttribute('aria-pressed', 'false');
    });
    const hidden = form.querySelector('input[name="evaluation_id"]');
    if (hidden) hidden.value = '';
}

function selectAllPillsInForm(form) {
    form.querySelectorAll('.eval-pill').forEach(p => {
        p.classList.add('active');
        p.setAttribute('aria-checked', 'true');
    });
}


/* ──────────────────────────────────────────────────────────────────────────
   SCRIPT RE-EXECUTION HELPER
   Re-runs <script> tags injected via innerHTML (required for dynamic HTML).
   ────────────────────────────────────────────────────────────────────────── */

function _reexecScripts(container) {
    container.querySelectorAll('script').forEach(oldScript => {
        const newScript = document.createElement('script');
        if (oldScript.src) {
            newScript.src = oldScript.src;
        } else {
            newScript.textContent = oldScript.textContent;
        }
        oldScript.parentNode.replaceChild(newScript, oldScript);
    });
}


/* ──────────────────────────────────────────────────────────────────────────
   LAZY CONTENT LOADERS
   ────────────────────────────────────────────────────────────────────────── */

function loadSegmentationContent() {
    window.segmentationLoaded = true;
    const contentDiv = document.getElementById('segmentationContent');
    contentDiv.innerHTML = '<div role="status" aria-live="polite" style="text-align:center;padding:60px 20px;color:var(--am-muted);"><i class="fa-solid fa-spinner fa-spin fa-2x" aria-hidden="true" style="color:var(--am-primary);"></i><p style="margin-top:16px;">Cargando distribuci\u00f3n...</p></div>';
    fetch('/aulametrics/segmentation/dashboard?embedded=true')
        .then(response => response.text())
        .then(html => {
            contentDiv.innerHTML = html;
            _reexecScripts(contentDiv);
        })
        .catch(error => {
            contentDiv.innerHTML = '<div style="text-align:center;padding:60px 20px;"><i class="fa-solid fa-exclamation-triangle" aria-hidden="true" style="font-size:48px;color:var(--am-danger);"></i><p style="margin-top:20px;color:var(--am-muted);">Error al cargar la distribuci\u00f3n del alumnado</p><button onclick="window.segmentationLoaded=false;loadSegmentationContent();" style="margin-top:12px;padding:8px 20px;background:var(--am-primary);color:#fff;border:none;border-radius:8px;cursor:pointer;font-size:14px;">Reintentar</button></div>';
            console.error('Error cargando distribuci\u00f3n:', error);
        });
}

function loadQualitativeContent() {
    window.qualitativeLoaded = true;
    const contentDiv = document.getElementById('qualitativeContent');
    contentDiv.innerHTML = '<div role="status" aria-live="polite" style="text-align:center;padding:60px 20px;color:var(--am-muted);"><i class="fa-solid fa-spinner fa-spin fa-2x" aria-hidden="true" style="color:var(--am-primary);"></i><p style="margin-top:16px;">Cargando datos cualitativos...</p></div>';
    fetch('/aulametrics/qualitative/dashboard?embedded=true')
        .then(response => response.text())
        .then(html => {
            contentDiv.innerHTML = html;
            _reexecScripts(contentDiv);
        })
        .catch(error => {
            contentDiv.innerHTML = '<div style="text-align:center;padding:60px 20px;"><i class="fa-solid fa-exclamation-triangle" aria-hidden="true" style="font-size:48px;color:var(--am-danger);"></i><p style="margin-top:20px;color:var(--am-muted);">Error al cargar datos cualitativos</p><button onclick="window.qualitativeLoaded=false;loadQualitativeContent();" style="margin-top:12px;padding:8px 20px;background:var(--am-primary);color:#fff;border:none;border-radius:8px;cursor:pointer;font-size:14px;">Reintentar</button></div>';
            console.error('Error cargando datos cualitativos:', error);
        });
}


/* ──────────────────────────────────────────────────────────────────────────
   SECTION NAVIGATION
   ────────────────────────────────────────────────────────────────────────── */

function navigateTo(section, skipPush) {
    document.querySelectorAll('.sidebar-item').forEach(item => {
        item.classList.remove('active');
        item.removeAttribute('aria-current');
    });
    const activeItem = document.querySelector('[data-section="' + section + '"]');
    if (activeItem) {
        activeItem.classList.add('active');
        activeItem.setAttribute('aria-current', 'page');
    }
    document.querySelectorAll('.content-section').forEach(sec => sec.classList.remove('active'));
    const sectionEl = document.getElementById('section-' + section);
    if (sectionEl) sectionEl.classList.add('active');
    const titles = {
        'home': 'Inicio',
        'quantitative': 'Datos Cuantitativos',
        'qualitative': 'Datos Cualitativos',
        'segmentation': 'Distribuci\u00f3n del Alumnado'
    };
    const titleEl = document.getElementById('sectionTitle');
    if (titleEl) titleEl.textContent = titles[section] || section;
    if (!skipPush) history.pushState({ section: section }, '', '?section=' + section);
    if (section === 'qualitative' && !window.qualitativeLoaded) loadQualitativeContent();
    if (section === 'segmentation' && !window.segmentationLoaded) loadSegmentationContent();

    // Resize all Chart.js charts in the newly visible section so they fill their
    // containers correctly (charts initialised while section was display:none have 0 width).
    if (sectionEl && typeof Chart !== 'undefined' && Chart.getChart) {
        requestAnimationFrame(function() {
            sectionEl.querySelectorAll('canvas').forEach(function(c) {
                const ch = Chart.getChart(c.id);
                if (ch) { ch.resize(); ch.update(); }
            });
        });
    }
}

window.addEventListener('popstate', function(e) {
    const section = (e.state && e.state.section)
        || new URLSearchParams(window.location.search).get('section')
        || 'home';
    if (['home', 'quantitative', 'qualitative', 'segmentation'].includes(section)) {
        navigateTo(section, true);
    }
});


/* ──────────────────────────────────────────────────────────────────────────
   HUB FILTERS SUBMIT (quantitative AJAX reload)
   ────────────────────────────────────────────────────────────────────────── */

document.addEventListener('DOMContentLoaded', function() {
    // Initial section routing
    const initSection = new URLSearchParams(window.location.search).get('section');
    if (initSection && ['home', 'quantitative', 'qualitative', 'segmentation'].includes(initSection)) {
        navigateTo(initSection);
    }

    // Hub filters (quantitative)
    const hubFilters = document.getElementById('hub-filters');
    if (hubFilters) {
        hubFilters.addEventListener('submit', function(e) {
            e.preventDefault();
            const submitBtn = e.target.querySelector('button[type="submit"]');
            const originalBtnContent = submitBtn.innerHTML;
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin me-1"></i>Cargando...';

            const evalValues = Array.from(document.querySelectorAll('.eval-pill.active')).map(p => p.dataset.value);
            const params = new URLSearchParams();
            if (evalValues.length > 0) params.append('evaluation_ids', evalValues.join(','));
            params.append('section', 'quantitative');
            const url = '/aulametrics/dashboard?' + params.toString();

            const kpiContainer = document.querySelector('#section-quantitative .kpi-container');
            const chartsContainer = document.querySelector('#section-quantitative .charts-container');
            if (kpiContainer) { kpiContainer.style.opacity = '0.5'; kpiContainer.style.transition = 'opacity 0.3s'; }
            if (chartsContainer) { chartsContainer.style.opacity = '0.5'; chartsContainer.style.transition = 'opacity 0.3s'; }

            fetch(url)
                .then(response => response.text())
                .then(html => {
                    const tempDiv = document.createElement('div');
                    tempDiv.innerHTML = html;
                    const newKpis = tempDiv.querySelector('.kpi-container');
                    if (newKpis && kpiContainer) {
                        kpiContainer.innerHTML = newKpis.innerHTML;
                        kpiContainer.style.opacity = '0';
                        requestAnimationFrame(() => { requestAnimationFrame(() => { kpiContainer.style.opacity = '1'; }); });
                    }
                    const newCharts = tempDiv.querySelector('.charts-container');
                    if (newCharts && chartsContainer) {
                        chartsContainer.innerHTML = newCharts.innerHTML;
                        chartsContainer.style.opacity = '0';
                        _reexecScripts(chartsContainer);
                        requestAnimationFrame(() => { requestAnimationFrame(() => { chartsContainer.style.opacity = '1'; }); });
                    }
                    submitBtn.disabled = false;
                    submitBtn.innerHTML = originalBtnContent;
                    if (kpiContainer) kpiContainer.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                    history.pushState({}, '', url);
                })
                .catch(error => {
                    console.error('Error al aplicar filtros:', error);
                    submitBtn.disabled = false;
                    submitBtn.innerHTML = originalBtnContent;
                    if (kpiContainer) {
                        kpiContainer.style.opacity = '1';
                        kpiContainer.innerHTML = '<div style="text-align:center;padding:40px;"><i class="fa-solid fa-exclamation-triangle" aria-hidden="true" style="font-size:32px;color:var(--am-danger);"></i><p style="margin-top:12px;color:var(--am-muted);">Error al cargar datos.</p><button onclick="document.getElementById(\'hub-filters\').dispatchEvent(new Event(\'submit\', {bubbles:true,cancelable:true}))" style="margin-top:12px;padding:8px 20px;background:var(--am-primary);color:#fff;border:none;border-radius:8px;cursor:pointer;font-size:14px;">Reintentar</button></div>';
                    }
                    if (chartsContainer) chartsContainer.style.opacity = '1';
                });
        });
    }

    // Delegated: qualitative + segmentation filter forms
    document.addEventListener('submit', function(e) {
        const form = e.target;

        // ── Qualitative filters ──
        if (form.id === 'qualitativeFiltersForm') {
            e.preventDefault();
            const evalValues = Array.from(form.querySelectorAll('.eval-pill.active')).map(p => p.dataset.value);
            const params = new URLSearchParams();
            if (evalValues.length > 0) params.append('evaluation_ids', evalValues.join(','));
            params.append('embedded', 'true');
            fetch('/aulametrics/qualitative/dashboard?' + params.toString())
                .then(response => response.text())
                .then(html => {
                    const contentDiv = document.getElementById('qualitativeContent');
                    if (!contentDiv) return;
                    contentDiv.innerHTML = html;
                    _reexecScripts(contentDiv);
                })
                .catch(error => console.error('Error al filtrar datos cualitativos:', error));
            return;
        }

        // ── Segmentation filters ──
        if (form.id === 'segmentationFiltersForm') {
            e.preventDefault();
            const evalValues = Array.from(form.querySelectorAll('.eval-pill.active')).map(p => p.dataset.value);
            const params = new URLSearchParams();
            if (evalValues.length > 0) params.append('evaluation_ids', evalValues.join(','));
            params.append('embedded', 'true');
            const contentDiv = document.getElementById('segmentationContent');
            if (contentDiv) contentDiv.style.opacity = '0.5';
            fetch('/aulametrics/segmentation/dashboard?' + params.toString())
                .then(response => response.text())
                .then(html => {
                    if (!contentDiv) return;
                    contentDiv.innerHTML = html;
                    contentDiv.style.opacity = '1';
                    _reexecScripts(contentDiv);
                })
                .catch(error => {
                    if (contentDiv) contentDiv.style.opacity = '1';
                    console.error('Error al filtrar distribución:', error);
                });
        }
    });
});


/* ──────────────────────────────────────────────────────────────────────────
   WORDCLOUD FACTORY
   Extracted from qualitative_dashboard_templates.xml.
   Called from small inline scripts in templates that inject the data vars.

   Usage (in template <script>):
     window.amWordcloud.init('wordcloud', wordcloudData, paletteColors, 350);
   ────────────────────────────────────────────────────────────────────────── */

window.amWordcloud = {
    /**
     * Renders a d3-cloud wordcloud into the element with the given id.
     * @param {string}   elementId    - id of the container div
     * @param {Array}    data         - array of [word, freq] pairs
     * @param {string[]} colors       - palette color array
     * @param {number}   [fixedHeight] - fixed height in px; if omitted, computed dynamically
     */
    init: function(elementId, data, colors, fixedHeight) {
        var el = document.getElementById(elementId);
        if (!el) return;
        el.innerHTML = '';  // clear any previous render (prevents double-init stacking SVGs)
        if (!data || data.length === 0) {
            el.innerHTML = '<div style="text-align:center;padding:24px;font-size:13px;color:#94a3b8;">No hay suficientes palabras para generar la nube</div>';
            return;
        }

        // Use a generous internal canvas so D3 has room to place all words without clipping.
        // After rendering we'll compute the actual occupied bbox and fit the SVG to it.
        var layoutW = Math.max(el.offsetWidth || 0, 960);
        var layoutH = fixedHeight || Math.min(520, Math.max(220, data.length * 13));

        var words = data.map(function(d) {
            return { text: d[0], size: Math.sqrt(d[1]) * 10 + 11, freq: d[1] };
        });

        // Shared floating tooltip (created once, reused by all wordclouds)
        var tip = document.getElementById('am-wc-tip');
        if (!tip) {
            tip = document.createElement('div');
            tip.id = 'am-wc-tip';
            tip.style.cssText = [
                'position:fixed',
                'pointer-events:none',
                'background:#1e293b',
                'color:#fff',
                'font-family:Plus Jakarta Sans,sans-serif',
                'font-size:12px',
                'font-weight:600',
                'padding:5px 11px',
                'border-radius:6px',
                'box-shadow:0 4px 12px rgba(0,0,0,0.25)',
                'opacity:0',
                'transition:opacity 0.12s ease',
                'z-index:9999',
                'white-space:nowrap',
            ].join(';');
            document.body.appendChild(tip);
        }

        // Padding = half the largest word's font size so rotated words never bleed out.
        var maxSize = words.reduce(function(m, w) { return Math.max(m, w.size); }, 0);
        var wcPad = Math.ceil(maxSize / 2) + 8;

        var layout = d3.layout.cloud()
            .size([layoutW, layoutH])
            .words(words)
            .padding(6)
            .rotate(function() { return ~~(Math.random() * 2) * 90; })
            .font('Plus Jakarta Sans')
            .fontSize(function(d) { return d.size; })
            .on('end', function(placedWords) {
                var svg = d3.select('#' + elementId).append('svg')
                    .style('display', 'block')
                    .style('overflow', 'hidden');  // clip anything that escapes the viewBox

                var group = svg.append('g')
                    .attr('transform', 'translate(' + layoutW / 2 + ',' + layoutH / 2 + ')');

                group.selectAll('text')
                    .data(placedWords)
                    .enter().append('text')
                    .style('font-size', function(d) { return d.size + 'px'; })
                    .style('font-family', 'Plus Jakarta Sans')
                    .style('font-weight', '700')
                    .style('fill', function(d, i) { return colors[i % colors.length]; })
                    .style('cursor', 'default')
                    .attr('text-anchor', 'middle')
                    .attr('transform', function(d) {
                        return 'translate(' + [d.x, d.y] + ')rotate(' + d.rotate + ')';
                    })
                    .text(function(d) { return d.text; })
                    .on('mouseover', function(event, d) {
                        tip.textContent = d.freq + (d.freq === 1 ? ' aparición' : ' apariciones');
                        tip.style.opacity = '1';
                    })
                    .on('mousemove', function(event) {
                        tip.style.left = (event.clientX + 14) + 'px';
                        tip.style.top  = (event.clientY - 34) + 'px';
                    })
                    .on('mouseout', function() {
                        tip.style.opacity = '0';
                    });

                // Fit viewBox to actual rendered content.
                // getBBox is in group-local space (origin = canvas centre).
                // Add wcPad so half-size rotated words are never cut off.
                try {
                    var bbox = group.node().getBBox();
                    if (bbox.width > 0 && bbox.height > 0) {
                        var tx = layoutW / 2, ty = layoutH / 2;
                        var vx = tx + bbox.x - wcPad;
                        var vy = ty + bbox.y - wcPad;
                        var vw = bbox.width  + wcPad * 2;
                        var vh = bbox.height + wcPad * 2;
                        svg.attr('viewBox', [vx, vy, vw, vh].join(' '))
                           .attr('width', '100%')
                           .attr('height', vh + 'px');
                        el.style.height = vh + 'px';
                        return;
                    }
                } catch (e) { /* fall through */ }

                // Fallback
                svg.attr('width', '100%').attr('height', layoutH + 'px');
                el.style.height = layoutH + 'px';
            });
        layout.start();
    }
};
