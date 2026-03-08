# -*- coding: utf-8 -*-
"""
Cuestionarios oficiales AulaMetrics en el perfil de alumno:
lista de resultados en acordeón con desglose por sub-escalas y comparativa
de grupo/centro.
"""
from odoo import models, api
from ...utils import palette
import json as _json


class DashboardStudentSurveys(models.TransientModel):
    _inherit = 'aula_metrics.dashboard.student_profile'

    def _get_official_surveys_html(self, student_id):
        """
        Sección de cuestionarios oficiales organizada por evaluación (más reciente primero).
        Genera la timeline de tarjetas de evaluación con filas de cuestionario y el panel
        de evolución para el tab Evolución > Oficiales.

        Returns:
            dict con claves:
              timeline_html  (str)  – tarjetas de evaluación con filas (para Cuantitativo > Oficiales)
              evolution_html (str)  – gráficas de evolución (para Evolución > Oficiales)
              has_surveys    (bool) – True si hay al menos una tarjeta de evaluación
              student_id     (int)  – id del alumno
        """
        SurveyResult = self.env['aula_metrics.survey_result']
        results = SurveyResult.search([
            ('student_id', '=', student_id),
            ('is_aulametrics', '=', True),
        ], order='completed_at desc')

        _empty = {
            'timeline_html': '', 'evolution_html': '',
            'has_surveys': False, 'student_id': student_id,
        }
        if not results:
            return _empty

        # Pre-calcular scale_maxes y meta por survey_id
        BaremoRange = self.env['aula_metrics.survey_baremo_range']
        maxes_cache = {}
        meta_cache  = {}
        seen_sids   = list(dict.fromkeys(r.survey_id.id for r in results))

        for sid in seen_sids:
            baremos = BaremoRange.search([('survey_id', '=', sid)])
            m, meta = {}, {}
            for br in baremos:
                sn = br.scale_name or '__global__'
                if br.score_max > m.get(sn, 0):
                    m[sn] = br.score_max
                if sn not in meta:
                    meta[sn] = {
                        'label': br.scale_label or sn.replace('_', ' ').capitalize(),
                        'order': br.display_order if br.display_order is not None else 99,
                    }
            maxes_cache[sid] = m
            meta_cache[sid]  = meta

        # Agrupar por evaluación (orden: más reciente primero via completed_at)
        evals_data = {}
        for r in results:
            ev = r.evaluation_id
            if ev:
                key   = ev.id
                dname = ev.name
                ddate = r.completed_at
            else:
                key   = 0
                dname = 'Sin evaluación'
                ddate = r.completed_at

            if key not in evals_data:
                evals_data[key] = {'id': key, 'name': dname, 'date': ddate, 'results': []}
            evals_data[key]['results'].append(r)

        # Ordenar evaluaciones por fecha descendente
        ordered_evals = sorted(evals_data.values(), key=lambda e: e['date'] or '', reverse=True)

        # Evolución (para tab Evolución > Oficiales, solo si hay ≥2 evaluaciones)
        evolution_html = ''
        if len(ordered_evals) > 1:
            evolution_html = self._build_evolution_charts(ordered_evals, seen_sids, maxes_cache, meta_cache)

        # ── Timeline de evaluaciones ────────────────────────────────────
        drawer_hidden_divs = ''   # hidden divs with drawer content per result
        sections_html      = []

        for ev_data in ordered_evals:
            ev_name = ev_data['name']
            ev_date = ev_data['date'].strftime('%d/%m/%Y') if ev_data['date'] else ''
            ev_date_sp = (
                f' <span style="color:var(--am-muted);font-weight:400;font-size:11px;">· {ev_date}</span>'
                if ev_date else ''
            )

            surveys_in_eval = {}
            for r in ev_data['results']:
                sx = r.survey_id.id
                if sx not in surveys_in_eval:
                    surveys_in_eval[sx] = []
                surveys_in_eval[sx].append(r)

            rows_html = []
            for sx in seen_sids:
                if sx not in surveys_in_eval:
                    continue
                scale_maxes = maxes_cache[sx]
                scale_meta  = meta_cache[sx]
                ctx         = self._get_survey_result_context(sx, student_id)
                for r in surveys_in_eval[sx]:
                    row_html, drawer_html = self._build_survey_result_row(
                        r, scale_maxes, ctx, scale_meta, show_checkbox=True,
                    )
                    rows_html.append(row_html)
                    drawer_hidden_divs += drawer_html

            if not rows_html:
                continue

            ev_card_id = f'am-eval-card-{ev_data["id"]}'
            sections_html.append(f"""
        <div class="am-eval-card" id="{ev_card_id}">
            <div class="am-eval-card__header">
                <input type="checkbox" class="am-eval-check form-check-input"
                       id="am-eval-chk-{ev_data['id']}"
                       data-eval-card="{ev_card_id}"
                       onchange="amOnEvalCheck(this)">
                <label for="am-eval-chk-{ev_data['id']}" class="d-flex align-items-center gap-2 mb-0" style="cursor:pointer;flex:1;">
                    <i class="fa-solid fa-calendar-check" style="color:var(--am-primary);font-size:12px;"></i>
                    <span style="font-size:13px;font-weight:600;color:var(--am-text);">{ev_name}{ev_date_sp}</span>
                </label>
            </div>
            <div>{''.join(rows_html)}</div>
        </div>""")

        timeline_html = drawer_hidden_divs + '\n'.join(sections_html)

        return {
            'timeline_html':  timeline_html,
            'evolution_html': evolution_html,
            'has_surveys':    bool(sections_html),
            'student_id':     student_id,
        }

    def _build_evolution_charts(self, ordered_evals, seen_sids, maxes_cache, meta_cache):
        """
        Mini gráficas de línea (Chart.js) por cuestionario mostrando la evolución
        de puntuaciones por sub-escala a través de las evaluaciones.
        Requiere que Chart.js esté cargado en la página.
        """
        _LINE_COLORS = [
            '#3b82f6', '#10b981', '#f59e0b', '#ef4444',
            '#8b5cf6', '#06b6d4', '#f97316', '#ec4899',
        ]

        # Más antigua primero en la gráfica
        chronological = list(reversed(ordered_evals))

        # Recopilar datos por cuestionario
        per_survey = {}
        for ev_data in chronological:
            ev_name = ev_data['name']
            for r in ev_data['results']:
                sid = r.survey_id.id
                if sid not in per_survey:
                    per_survey[sid] = {
                        'title': r.survey_id.title or '',
                        'eval_names': [],
                        'scales': {},
                    }
                if ev_name not in per_survey[sid]['eval_names']:
                    per_survey[sid]['eval_names'].append(ev_name)

                scale_scores = r.get_scale_scores()
                for scale_name, data in scale_scores.items():
                    score = data.get('score', 0) if isinstance(data, dict) else float(data or 0)
                    if scale_name == 'total':
                        label = (meta_cache[sid].get('total') or {}).get('label') or 'Total'
                    else:
                        label = (meta_cache[sid].get(scale_name) or {}).get('label') or scale_name.replace('_', ' ').capitalize()
                    if scale_name not in per_survey[sid]['scales']:
                        per_survey[sid]['scales'][scale_name] = {'label': label, 'values': {}}
                    per_survey[sid]['scales'][scale_name]['values'][ev_name] = score

        # Construir canvas + script por cuestionario
        charts_html = []
        for sid, survey_data in per_survey.items():
            eval_labels = survey_data['eval_names']
            if len(eval_labels) < 2:
                continue

            scale_max = max(maxes_cache[sid].values(), default=10) if maxes_cache.get(sid) else 10
            if scale_max < 1:
                scale_max = 10

            datasets = []
            # Ordenar: sub-escalas primero (por meta order), total al final
            scale_order = sorted(
                survey_data['scales'].keys(),
                key=lambda sn: (1 if sn == 'total' else 0,
                                (meta_cache.get(sid) or {}).get(sn, {}).get('order', 99))
            )
            for idx, sn in enumerate(scale_order):
                sdata    = survey_data['scales'][sn]
                is_total = sn == 'total'
                color    = '#1e3a5f' if is_total else _LINE_COLORS[idx % len(_LINE_COLORS)]
                values_list = [sdata['values'].get(ev) for ev in eval_labels]
                datasets.append({
                    'label':            sdata['label'],
                    'data':             values_list,
                    'borderColor':      color,
                    'backgroundColor':  color,
                    'tension':          0.3,
                    'pointRadius':      5,
                    'pointHoverRadius': 7,
                    'borderWidth':      3 if is_total else 2,
                    'borderDash':       [] if is_total else [],
                    'fill':             False,
                    'spanGaps':         True,
                })

            canvas_id    = f'evo-chart-{sid}'
            datasets_json = _json.dumps(datasets)
            labels_json   = _json.dumps(eval_labels)

            charts_html.append(f"""
            <div class="mb-2">
                <div style="font-size:11px;font-weight:600;color:var(--am-text);margin-bottom:6px;padding:0 2px;">
                    {survey_data['title']}
                </div>
                <div style="position:relative;height:130px;">
                    <canvas id="{canvas_id}"></canvas>
                </div>
                <script>
                (function() {{
                    var ctx = document.getElementById('{canvas_id}');
                    if (!ctx || typeof Chart === 'undefined') return;
                    new Chart(ctx, {{
                        type: 'line',
                        data: {{
                            labels: {labels_json},
                            datasets: {datasets_json}
                        }},
                        options: {{
                            responsive: true,
                            maintainAspectRatio: false,
                            plugins: {{
                                legend: {{
                                    display: true, position: 'bottom',
                                    labels: {{ usePointStyle: true, padding: 10, font: {{ size: 10 }} }}
                                }},
                                tooltip: {{
                                    callbacks: {{
                                        label: function(ctx) {{
                                            return ctx.dataset.label + ': ' + (ctx.parsed.y !== null ? ctx.parsed.y.toFixed(0) : '—');
                                        }}
                                    }}
                                }}
                            }},
                            scales: {{
                                x: {{ grid: {{ display: false }}, ticks: {{ font: {{ size: 10 }} }} }},
                                y: {{
                                    beginAtZero: true,
                                    suggestedMax: {scale_max:.0f},
                                    grid: {{ color: 'rgba(0,0,0,0.05)' }},
                                    ticks: {{ font: {{ size: 10 }}, stepSize: 1 }}
                                }}
                            }},
                            animation: {{ duration: 400 }}
                        }}
                    }});
                }})();
                </script>
            </div>""")

        if not charts_html:
            return ''

        if len(charts_html) == 1:
            inner = charts_html[0]
        else:
            cols = ''.join(
                f'<div style="flex:1;min-width:220px;padding:0 8px;">{c}</div>'
                for c in charts_html
            )
            inner = f'<div style="display:flex;flex-wrap:wrap;margin:0 -8px;">{cols}</div>'

        return f"""
        <div class="mb-4 p-3" style="background:var(--am-surface);border:1px solid var(--am-border);border-radius:8px;">
            <div class="d-flex align-items-center gap-2 mb-3">
                <i class="fa-solid fa-chart-line" style="color:var(--am-primary);font-size:13px;"></i>
                <span style="font-size:12px;font-weight:600;color:var(--am-text);letter-spacing:0.03em;">Evolución entre evaluaciones</span>
            </div>
            {inner}
        </div>"""

    def _build_survey_result_row(self, result, scale_maxes, context=None, scale_meta=None,
                                  show_checkbox=True):
        """
        Genera la fila compacta de un resultado oficial para la nueva timeline y su
        panel de detalle (drawer).

        Returns:
            tuple (row_html, drawer_html)
            row_html    – fila inline: [checkbox] · dot · nombre · puntuación · badge · "Ver detalle"
            drawer_html – divs ocultos con contenido del drawer (#am-drawer-content-RID, título, footer)
        """
        rid      = result.id
        date_str = result.completed_at.strftime('%d/%m/%Y') if result.completed_at else '—'
        age_str  = f'{result.age_at_completion} a.' if result.age_at_completion else ''

        sev              = min(result.baremo_severity, 2)
        BaremoRange      = self.env['aula_metrics.survey_baremo_range']
        severity_mapping = BaremoRange.get_severity_mapping(result.survey_id.id)
        sev_info         = severity_mapping.get(sev, {})
        bar_color        = sev_info.get('color', '#6b7280')
        badge_style      = (
            f"background:{sev_info.get('bg_color','#f3f4f6')};"
            f"color:{sev_info.get('color','#374151')}"
        )
        global_label     = result.baremo_label or sev_info.get('label', f'Severity {sev}')

        survey_title = result.survey_id.title or '—'
        total_max    = scale_maxes.get('total')
        raw_max_str  = f'/{total_max:.0f}' if total_max else ''

        has_ctx = bool(context and (context.get('group_count') or context.get('center_count')))
        g_means = context['group_means']  if has_ctx else {}
        c_means = context['center_means'] if has_ctx else {}

        # ── Leyenda marcadores ─────────────────────────────────────────
        legend_parts = []
        if has_ctx and context.get('group_count'):
            n = context['group_count']
            legend_parts.append(
                f'<span style="display:inline-block;width:2px;height:12px;background:#94a3b8;'
                f'border-radius:1px;vertical-align:middle;"></span>&nbsp;Media grupo ({n})'
            )
        if has_ctx and context.get('center_count'):
            n = context['center_count']
            legend_parts.append(
                f'<span style="display:inline-block;width:2px;height:12px;background:{palette.UI_SUCCESS};'
                f'border-radius:1px;vertical-align:middle;"></span>&nbsp;Media centro ({n})'
            )
        legend_html = (
            '<div class="d-flex gap-3 mb-3" style="font-size:10px;color:var(--am-muted);">'
            + '&emsp;'.join(legend_parts) + '</div>'
        ) if legend_parts else ''

        # ── Barras por sub-escala (contenido del drawer) ───────────────
        scale_scores    = result.get_scale_scores()
        scale_bars_html = ''

        if scale_scores:
            _meta     = scale_meta or {}
            has_total = 'total' in scale_scores
            non_total = sorted(
                [s for s in scale_scores if s != 'total'],
                key=lambda s: _meta.get(s, {}).get('order', 99),
            )
            ordered_scales = non_total + (['total'] if has_total else [])

            bars = []
            for scale_name in ordered_scales:
                scale_data   = scale_scores[scale_name]
                score        = scale_data.get('score', 0) if isinstance(scale_data, dict) else float(scale_data)
                s_sev        = min(scale_data.get('severity', 0) if isinstance(scale_data, dict) else 0, 2)
                sev_info_s   = severity_mapping.get(s_sev, {})
                val_color    = sev_info_s.get('color', '#6b7280')
                scale_max    = max(scale_maxes.get(scale_name, 10), 1)
                display_name = (_meta.get(scale_name) or {}).get('label') or scale_name.replace('_', ' ').capitalize()
                is_total     = scale_name == 'total' and has_total and len(ordered_scales) > 1

                def pct(v, mx=scale_max):
                    return min(v / mx * 100, 100)

                s_pct    = pct(score)
                bar_html = (
                    f'<div title="{display_name}: {score:.0f}/{scale_max:.0f}" '
                    f'style="position:absolute;left:0;top:50%;transform:translateY(-50%);'
                    f'width:{s_pct:.1f}%;height:9px;background:{val_color};'
                    f'border-radius:0 2px 2px 0;z-index:2;"></div>'
                )

                g_mean = g_means.get(scale_name)
                c_mean = c_means.get(scale_name)
                g_mk   = ''
                c_mk   = ''
                if g_mean is not None:
                    gp   = pct(g_mean)
                    g_mk = (f'<div title="Media grupo: {g_mean:.1f}" '
                            f'style="position:absolute;left:{gp:.1f}%;top:0;'
                            f'height:100%;width:2px;background:#94a3b8;z-index:4;"></div>')
                if c_mean is not None:
                    cp   = pct(c_mean)
                    c_mk = (f'<div title="Media centro: {c_mean:.1f}" '
                            f'style="position:absolute;left:{cp:.1f}%;top:0;'
                            f'height:100%;width:2px;background:{palette.UI_SUCCESS};z-index:4;"></div>')

                top_border = ('border-top:1px solid var(--am-border);padding-top:8px;margin-top:4px;'
                              if is_total else '')
                bars.append(f"""
                <div class="d-flex align-items-center gap-2 mb-2" style="{top_border}">
                    <small style="width:145px;min-width:115px;flex-shrink:0;
                                  color:var(--am-muted);font-size:11px;">{display_name}</small>
                    <div style="flex:1;position:relative;height:22px;border-radius:3px;
                                overflow:hidden;background:var(--am-border);">
                        {bar_html}{g_mk}{c_mk}
                    </div>
                    <small style="width:44px;text-align:right;font-weight:700;font-size:11px;
                                  color:{val_color};flex-shrink:0;"
                           title="{display_name}">{score:.0f}<span style="font-weight:400;color:var(--am-muted);">/{scale_max:.0f}</span></small>
                </div>""")
            scale_bars_html = '\n'.join(bars)

        desc_html = ''
        if result.baremo_description:
            desc_html = f'<p style="font-size:13px;color:var(--am-muted);margin-bottom:14px;">{result.baremo_description}</p>'

        notes_html = ''
        if result.notes:
            notes_html = f"""
            <div class="mt-3 p-2" style="background:var(--am-light);border-radius:6px;
                         border-left:3px solid var(--am-primary);">
                <small style="color:var(--am-muted);">
                    <i class="fa-solid fa-note-sticky me-1"></i>
                    <strong>Observación:</strong> {result.notes}
                </small>
            </div>"""

        meta_parts = [p for p in [date_str, age_str] if p]
        meta_str   = ' · '.join(meta_parts)

        # ── Divs ocultos para el drawer ────────────────────────────────
        pdf_url = f'/report/pdf/aula_metrics.report_survey_result_document/{rid}'
        drawer_html = f"""
        <div id="am-drawer-content-{rid}" style="display:none;">
            <div style="font-size:11px;color:var(--am-muted);margin-bottom:12px;">{meta_str}</div>
            {desc_html}{legend_html}{scale_bars_html}{notes_html}
        </div>
        <div id="am-drawer-footer-{rid}" style="display:none;">
            <a href="{pdf_url}" target="_blank" class="btn btn-primary btn-sm">
                <i class="fa-solid fa-file-pdf me-1"></i>Descargar informe
            </a>
        </div>"""

        # ── Fila compacta (nueva timeline) ─────────────────────────────
        safe_title    = survey_title.replace('"', '&quot;')
        checkbox_html = (
            f'<input type="checkbox" class="am-row-check form-check-input"'
            f' data-rid="{rid}" data-title="{safe_title}"'
            f' onchange="amOnCheck(this)">'
            if show_checkbox else ''
        )

        row_html = f"""
        <div class="am-survey-row">
            {checkbox_html}
            <span class="am-row-dot" style="background:{bar_color};"></span>
            <span class="am-row-title" title="{safe_title}">{survey_title}</span>
            <span class="am-row-score">{result.raw_score:.0f}<span class="am-row-max">{raw_max_str}</span></span>
            <span class="badge am-row-badge" style="{badge_style};">{global_label}</span>
            <button type="button" class="am-ver-detalle" onclick="amOpenDrawer({rid})">
                Ver detalle <i class="fa-solid fa-arrow-right" style="font-size:9px;"></i>
            </button>
        </div>"""

        return row_html, drawer_html

        date_str  = result.completed_at.strftime('%d/%m/%Y') if result.completed_at else '—'
        age_str   = f'{result.age_at_completion} a.' if result.age_at_completion else ''
        eval_name = result.evaluation_id.name if result.evaluation_id else ''
        sev       = min(result.baremo_severity, 2)

        BaremoRange      = self.env['aula_metrics.survey_baremo_range']
        severity_mapping = BaremoRange.get_severity_mapping(result.survey_id.id)
        sev_info         = severity_mapping.get(sev, {})
        bar_color        = sev_info.get('color', '#ccc')
        badge_style      = f"background:{sev_info.get('bg_color','#fff')};color:{sev_info.get('color','#000')}"
        global_label     = result.baremo_label or sev_info.get('label', f'Severity {sev}')

        meta_parts = [p for p in [date_str, age_str, eval_name] if p]
        meta_str   = ' · '.join(meta_parts)

        has_ctx = bool(context and (context.get('group_count') or context.get('center_count')))
        g_means = context['group_means']  if has_ctx else {}
        c_means = context['center_means'] if has_ctx else {}

        # Leyenda marcadores
        legend_parts = []
        if has_ctx and context.get('group_count'):
            n = context['group_count']
            legend_parts.append(
                f'<span style="display:inline-block;width:2px;height:12px;background:#94a3b8;'
                f'border-radius:1px;vertical-align:middle;"></span>&nbsp;Media grupo ({n})'
            )
        if has_ctx and context.get('center_count'):
            n = context['center_count']
            legend_parts.append(
                f'<span style="display:inline-block;width:2px;height:12px;background:{palette.UI_SUCCESS};'
                f'border-radius:1px;vertical-align:middle;"></span>&nbsp;Media centro ({n})'
            )
        legend_html = (
            '<div class="d-flex gap-3 mb-3" style="font-size:10px;color:var(--am-muted);">'
            + '&emsp;'.join(legend_parts) + '</div>'
        ) if legend_parts else ''

        # Sub-escalas
        scale_scores    = result.get_scale_scores()
        scale_bars_html = ''

        if scale_scores:
            _meta     = scale_meta or {}
            has_total = 'total' in scale_scores
            non_total = sorted(
                [s for s in scale_scores if s != 'total'],
                key=lambda s: _meta.get(s, {}).get('order', 99),
            )
            ordered_scales = non_total + (['total'] if has_total else [])

            bars = []
            for scale_name in ordered_scales:
                scale_data   = scale_scores[scale_name]
                score        = scale_data.get('score', 0) if isinstance(scale_data, dict) else float(scale_data)
                s_sev        = min(scale_data.get('severity', 0) if isinstance(scale_data, dict) else 0, 2)
                sev_info_s   = severity_mapping.get(s_sev, {})
                val_color    = sev_info_s.get('color', '#ccc')
                scale_max    = max(scale_maxes.get(scale_name, 10), 1)
                display_name = (_meta.get(scale_name) or {}).get('label') or scale_name.replace('_', ' ').capitalize()
                is_total     = scale_name == 'total' and has_total and len(ordered_scales) > 1

                def pct(v, mx=scale_max):
                    return min(v / mx * 100, 100)

                s_pct    = pct(score)
                bar_html = (
                    f'<div title="{display_name}: {score:.0f}/{scale_max:.0f}" '
                    f'style="position:absolute;left:0;top:50%;transform:translateY(-50%);'
                    f'width:{s_pct:.1f}%;height:9px;background:{val_color};'
                    f'border-radius:0 2px 2px 0;z-index:2;"></div>'
                )

                g_mean = g_means.get(scale_name)
                c_mean = c_means.get(scale_name)
                g_mk   = ''
                c_mk   = ''
                if g_mean is not None:
                    gp   = pct(g_mean)
                    g_mk = (f'<div title="Media grupo: {g_mean:.1f}" '
                            f'style="position:absolute;left:{gp:.1f}%;top:0;'
                            f'height:100%;width:2px;background:#94a3b8;z-index:4;"></div>')
                if c_mean is not None:
                    cp   = pct(c_mean)
                    c_mk = (f'<div title="Media centro: {c_mean:.1f}" '
                            f'style="position:absolute;left:{cp:.1f}%;top:0;'
                            f'height:100%;width:2px;background:{palette.UI_SUCCESS};z-index:4;"></div>')

                top_border = ('border-top:1px solid var(--am-border);padding-top:8px;margin-top:4px;'
                              if is_total else '')
                bars.append(f"""
                <div class="d-flex align-items-center gap-2 mb-2" style="{top_border}">
                    <small style="width:145px;min-width:115px;flex-shrink:0;
                                  color:var(--am-muted);font-size:11px;">{display_name}</small>
                    <div style="flex:1;position:relative;height:22px;border-radius:3px;
                                overflow:hidden;background:var(--am-border);">
                        {bar_html}{g_mk}{c_mk}
                    </div>
                    <small style="width:44px;text-align:right;font-weight:700;font-size:11px;
                                  color:{val_color};flex-shrink:0;"
                           title="{display_name}">{score:.0f}<span style="font-weight:400;color:var(--am-muted);">/{scale_max:.0f}</span></small>
                </div>""")
            scale_bars_html = '\n'.join(bars)

        desc_html = ''
        if result.baremo_description:
            desc_html = f'<p style="font-size:13px;color:var(--am-muted);margin-bottom:14px;">{result.baremo_description}</p>'

        notes_html = ''
        if result.notes:
            notes_html = f"""
            <div class="mt-3 p-2" style="background:var(--am-light);border-radius:6px;
                         border-left:3px solid var(--am-primary);">
                <small style="color:var(--am-muted);">
                    <i class="fa-solid fa-note-sticky me-1"></i>
                    <strong>Observación:</strong> {result.notes}
                </small>
            </div>"""

        total_max = scale_maxes.get('total')
        raw_max_str = f'/{total_max:.0f}' if total_max else ''

        return f"""
        <div style="border:1px solid var(--am-border);border-radius:8px;margin-bottom:6px;overflow:hidden;">
            <div class="d-flex align-items-center" style="border-left:4px solid {bar_color};">
                <div class="d-flex align-items-center justify-content-between px-3 py-2"
                     role="button"
                     data-bs-toggle="collapse" data-bs-target="#{collapse_id}"
                     aria-expanded="false" aria-controls="{collapse_id}"
                     style="flex:1;min-width:0;cursor:pointer;user-select:none;transition:background 0.15s;"
                     onmouseover="this.style.background='var(--am-light)'"
                     onmouseout="this.style.background=''">
                    <div style="min-width:0;flex:1;">
                        <span style="font-size:14px;font-weight:500;color:var(--am-text);">{meta_str}</span>
                    </div>
                    <div class="d-flex align-items-center gap-3 ms-3 flex-shrink-0">
                        <span style="font-size:22px;font-weight:700;line-height:1;color:{bar_color};">{result.raw_score:.0f}<span style="font-weight:400;color:var(--am-muted);">{raw_max_str}</span></span>
                        <span class="badge" style="{badge_style};font-size:11px;padding:3px 10px;">{global_label}</span>
                        <i class="fa-solid fa-chevron-down" id="chevron-{rid}"
                           style="color:var(--am-muted);font-size:11px;transition:transform 0.25s;"></i>
                    </div>
                </div>
                <a href="/report/pdf/aula_metrics.report_survey_result_document/{rid}"
                   target="_blank" title="Generar informe PDF"
                   style="display:inline-flex;align-items:center;gap:4px;padding:3px 10px;
                          margin-right:10px;flex-shrink:0;border:1px solid var(--am-border);
                          border-radius:5px;font-size:10px;color:var(--am-muted);text-decoration:none;
                          background:var(--am-surface);line-height:1.4;white-space:nowrap;"
                   onmouseover="this.style.borderColor='var(--am-primary)';this.style.color='var(--am-primary)';"
                   onmouseout="this.style.borderColor='var(--am-border)';this.style.color='var(--am-muted)';"
                ><i class="fa-solid fa-file-pdf" style="font-size:10px;"></i>&nbsp;Informe</a>
            </div>
            <div class="collapse" id="{collapse_id}">
                <div style="padding:16px 20px;border-top:1px solid var(--am-border);background:var(--am-surface);">
                    {desc_html}{legend_html}{scale_bars_html}{notes_html}
                </div>
            </div>
        </div>
        <script>
        (function() {{
            var el  = document.getElementById('{collapse_id}');
            var chv = document.getElementById('chevron-{rid}');
            if (el && chv) {{
                el.addEventListener('show.bs.collapse', function() {{ chv.style.transform = 'rotate(180deg)'; }});
                el.addEventListener('hide.bs.collapse', function() {{ chv.style.transform = 'rotate(0deg)'; }});
            }}
        }})();
        </script>"""

    def _get_survey_result_context(self, survey_id, student_id):
        """Calcula medias por escala del grupo y del centro para comparativa."""
        SurveyResult = self.env['aula_metrics.survey_result']
        student  = self.env['res.partner'].browse(student_id)
        group_id = student.academic_group_id.id if student.academic_group_id else None

        all_others   = SurveyResult.search([
            ('survey_id', '=', survey_id),
            ('student_id', '!=', student_id),
        ])
        group_others = all_others.filtered(
            lambda r: group_id and r.student_id.academic_group_id.id == group_id
        )

        def avg_scales(records):
            sums, counts = {}, {}
            for r in records:
                for scale_name, data in r.get_scale_scores().items():
                    score = data.get('score', 0) if isinstance(data, dict) else float(data or 0)
                    sums[scale_name]   = sums.get(scale_name, 0) + score
                    counts[scale_name] = counts.get(scale_name, 0) + 1
            return {k: sums[k] / counts[k] for k in sums if counts.get(k)}

        return {
            'group_means':  avg_scales(group_others),
            'center_means': avg_scales(all_others),
            'group_count':  len(group_others),
            'center_count': len(all_others),
        }


