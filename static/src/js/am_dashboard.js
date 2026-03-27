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
            setTimeout(() => {
                if (!window._aulametrics_wordcloud_inited) {
                    if (typeof initWordcloudCounselor !== 'undefined') {
                        window._aulametrics_wordcloud_inited = true; initWordcloudCounselor();
                    } else if (typeof initWordcloudTutor !== 'undefined') {
                        window._aulametrics_wordcloud_inited = true; initWordcloudTutor();
                    }
                }
            }, 500);
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
            const params = new URLSearchParams();
            for (const [key, value] of new FormData(form).entries()) {
                if (value) params.append(key, value);
            }
            params.append('embedded', 'true');
            fetch('/aulametrics/qualitative/dashboard?' + params.toString())
                .then(response => response.text())
                .then(html => {
                    const contentDiv = document.getElementById('qualitativeContent');
                    if (!contentDiv) return;
                    contentDiv.innerHTML = html;
                    _reexecScripts(contentDiv);
                    setTimeout(() => {
                        if (!window._aulametrics_wordcloud_inited) {
                            if (typeof initWordcloudCounselor !== 'undefined') {
                                window._aulametrics_wordcloud_inited = true; initWordcloudCounselor();
                            } else if (typeof initWordcloudTutor !== 'undefined') {
                                window._aulametrics_wordcloud_inited = true; initWordcloudTutor();
                            }
                        }
                    }, 300);
                })
                .catch(error => console.error('Error al filtrar datos cualitativos:', error));
            return;
        }

        // ── Segmentation filters ──
        if (form.id === 'segmentationFiltersForm') {
            e.preventDefault();
            const params = new URLSearchParams();
            for (const [key, value] of new FormData(form).entries()) {
                if (value) params.append(key, value);
            }
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
                    console.error('Error al filtrar distribuci\u00f3n:', error);
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
        if (!data || data.length === 0) {
            el.innerHTML = '<div style="text-align:center;padding:24px;font-size:13px;color:#94a3b8;">No hay suficientes palabras para generar la nube</div>';
            return;
        }
        var h = fixedHeight || Math.min(280, Math.max(140, data.length * 9));
        el.style.height = h + 'px';

        var words = data.map(function(d) {
            return { text: d[0], size: Math.sqrt(d[1]) * 10 + 11 };
        });

        var layout = d3.layout.cloud()
            .size([el.offsetWidth || 800, h])
            .words(words)
            .padding(6)
            .rotate(function() { return ~~(Math.random() * 2) * 90; })
            .font('Plus Jakarta Sans')
            .fontSize(function(d) { return d.size; })
            .on('end', function(placedWords) {
                d3.select('#' + elementId).append('svg')
                    .attr('width', layout.size()[0])
                    .attr('height', layout.size()[1])
                    .append('g')
                    .attr('transform', 'translate(' + layout.size()[0] / 2 + ',' + layout.size()[1] / 2 + ')')
                    .selectAll('text')
                    .data(placedWords)
                    .enter().append('text')
                    .style('font-size', function(d) { return d.size + 'px'; })
                    .style('font-family', 'Plus Jakarta Sans')
                    .style('font-weight', '700')
                    .style('fill', function(d, i) { return colors[i % colors.length]; })
                    .attr('text-anchor', 'middle')
                    .attr('transform', function(d) {
                        return 'translate(' + [d.x, d.y] + ')rotate(' + d.rotate + ')';
                    })
                    .text(function(d) { return d.text; });
            });
        layout.start();
    }
};
