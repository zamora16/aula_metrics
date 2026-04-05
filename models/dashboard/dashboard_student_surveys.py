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
        ], order='completed_at desc', limit=100)

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
                ctx         = self._get_survey_result_context(sx, student_id, evaluation_id=ev_data['id'] or None)
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
        Gráficas de evolución por cuestionario — una tarjeta por cuestionario (ancho completo).
        Incluye:
          - Gráfica de línea con todas las sub-escalas y total
          - Tabla resumen con último valor, Δ% vs evaluación anterior, media grupo y centro
        """
        _LINE_COLORS = [
            '#3b82f6', '#10b981', '#f59e0b', '#ef4444',
            '#8b5cf6', '#06b6d4', '#f97316', '#ec4899',
        ]

        # Más antigua primero en la gráfica
        chronological = list(reversed(ordered_evals))

        # ── Recopilar datos por cuestionario ───────────────────────────
        per_survey = {}
        for ev_data in chronological:
            ev_name = ev_data['name']
            for r in ev_data['results']:
                sid = r.survey_id.id
                if sid not in per_survey:
                    per_survey[sid] = {
                        'title':      r.survey_id.title or '',
                        'eval_names': [],
                        'scales':     {},
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

        # ── Medias grupo/centro por escala (todos los resultados de otros alumnos) ─
        _ctx_cache = {}
        for sid in seen_sids:
            ctx = self._get_survey_result_context(sid,
                # student_id: grab from first result found for this survey
                next(
                    r.student_id.id
                    for ev in chronological for r in ev['results']
                    if r.survey_id.id == sid
                )
            )
            _ctx_cache[sid] = ctx

        # ── Construir una tarjeta por cuestionario ─────────────────────
        charts_html = []
        for sid in seen_sids:
            survey_data = per_survey.get(sid)
            if not survey_data:
                continue
            eval_labels = survey_data['eval_names']
            if len(eval_labels) < 2:
                continue

            scale_max = max(maxes_cache[sid].values(), default=10) if maxes_cache.get(sid) else 10
            if scale_max < 1:
                scale_max = 10

            ctx         = _ctx_cache.get(sid, {})
            group_means = ctx.get('group_means', {})
            center_means = ctx.get('center_means', {})
            group_count  = ctx.get('group_count', 0)
            center_count = ctx.get('center_count', 0)

            # Ordenar escalas: sub-escalas primero (por orden), total al final
            scale_order = sorted(
                survey_data['scales'].keys(),
                key=lambda sn: (1 if sn == 'total' else 0,
                                (meta_cache.get(sid) or {}).get(sn, {}).get('order', 99))
            )

            # ── Datasets para Chart.js ─────────────────────────────────
            datasets = []
            for idx, sn in enumerate(scale_order):
                sdata    = survey_data['scales'][sn]
                is_total = sn == 'total'
                color    = palette.UI_PRIMARY if is_total else _LINE_COLORS[idx % len(_LINE_COLORS)]
                values_list = [sdata['values'].get(ev) for ev in eval_labels]
                datasets.append({
                    'label':            sdata['label'],
                    'data':             values_list,
                    'borderColor':      color,
                    'backgroundColor':  color + '18',
                    'tension':          0.35,
                    'pointRadius':      5,
                    'pointHoverRadius': 8,
                    'borderWidth':      3 if is_total else 2,
                    'fill':             is_total,
                    'spanGaps':         True,
                    'order':            0 if is_total else 1,
                })

            # Añadir datasets de referencia (líneas punteadas grupo / centro)
            ref_datasets = []
            for sn in scale_order:
                sdata    = survey_data['scales'][sn]
                is_total = sn == 'total'
                if not is_total:
                    continue  # solo mostrar referencia para el total; evita saturar el gráfico
                gm = group_means.get(sn)
                cm = center_means.get(sn)
                if gm is not None and group_count > 0:
                    ref_datasets.append({
                        'label':           f'Media grupo ({group_count})',
                        'data':            [gm] * len(eval_labels),
                        'borderColor':     '#94a3b8',
                        'backgroundColor': 'transparent',
                        'borderWidth':     1,
                        'borderDash':      [5, 4],
                        'pointRadius':     0,
                        'fill':            False,
                        'spanGaps':        True,
                        'order':           2,
                    })
                if cm is not None and center_count > 0:
                    ref_datasets.append({
                        'label':           f'Media centro ({center_count})',
                        'data':            [cm] * len(eval_labels),
                        'borderColor':     palette.UI_CHALKBOARD_GREEN,
                        'backgroundColor': 'transparent',
                        'borderWidth':     1,
                        'borderDash':      [3, 3],
                        'pointRadius':     0,
                        'fill':            False,
                        'spanGaps':        True,
                        'order':           3,
                    })

            all_datasets = datasets + ref_datasets

            canvas_id     = f'evo-chart-{sid}'
            datasets_json = _json.dumps(all_datasets)
            labels_json   = _json.dumps(eval_labels)

            # ── Tabla resumen de escalas ───────────────────────────────
            # Columnas: Escala | val_1 … val_n | Δ% | Media grupo | Media centro
            # Δ% = cambio del último al primer valor conocido
            summary_rows = ''
            for sn in scale_order:
                sdata    = survey_data['scales'][sn]
                is_total = sn == 'total'
                label    = sdata['label']
                # valores en orden cronológico (algunos pueden ser None)
                vals = [sdata['values'].get(ev) for ev in eval_labels]
                known = [(i, v) for i, v in enumerate(vals) if v is not None]

                last_val  = known[-1][1] if known else None
                first_val = known[0][1]  if known else None

                # Δ% overall (primer → último conocido)
                delta_html = '<td class="am-td">—</td>'
                if first_val is not None and last_val is not None and first_val != 0:
                    pct_change = (last_val - first_val) / first_val * 100
                    arrow  = '↑' if pct_change > 0 else ('↓' if pct_change < 0 else '→')
                    color  = palette.UI_SUCCESS_DARK if pct_change > 0 else (palette.UI_DANGER_DARK if pct_change < 0 else palette.UI_MUTED)
                    bg     = palette.BADGE_OK_BG if pct_change > 0 else (palette.ALERT_HIGH_BG if pct_change < 0 else palette.UI_LIGHT)
                    delta_html = (
                        f'<td class="am-td">'
                        f'<span class="am-mono" style="display:inline-block;background:{bg};color:{color};'
                        f'border-radius:12px;padding:2px 8px;'
                        f'font-size:11px;font-weight:700;white-space:nowrap;">'
                        f'{arrow} {abs(pct_change):.0f}%</span></td>'
                    )

                # Valores por evaluación
                val_cells = ''
                for v in vals:
                    if v is None:
                        val_cells += '<td class="am-td" style="color:var(--am-muted);">—</td>'
                    else:
                        s_max = max(maxes_cache[sid].get(sn, scale_max), 1)
                        val_cells += (
                            f'<td class="am-td am-mono" style="font-size:13px;font-weight:700;">'
                            f'{v:.0f}'
                            f'<span style="font-size:10px;font-weight:400;color:var(--am-muted);">/{s_max:.0f}</span>'
                            f'</td>'
                        )

                # Comparativa grupo/centro — solo renderizar si la columna existe en cabecera
                gm = group_means.get(sn)
                cm = center_means.get(sn)
                gm_cell = ''
                if group_count > 0:
                    gm_cell = (
                        f'<td class="am-td am-mono am-group-col" style="font-size:12px;">{gm:.1f}</td>'
                        if gm is not None
                        else '<td class="am-td" style="color:var(--am-muted);">—</td>'
                    )
                cm_cell = ''
                if center_count > 0:
                    cm_cell = (
                        f'<td class="am-td am-mono am-center-col" style="font-size:12px;">{cm:.1f}</td>'
                        if cm is not None
                        else '<td class="am-td" style="color:var(--am-muted);">—</td>'
                    )

                row_style = (
                    'border-top:2px solid var(--am-border);font-weight:700;background:var(--am-light);'
                    if is_total else ''
                )
                summary_rows += (
                    f'<tr style="{row_style}">'
                    f'<td class="am-td-label" style="font-weight:{"700" if is_total else "500"};">'
                    f'{label}</td>'
                    f'{val_cells}{delta_html}{gm_cell}{cm_cell}'
                    f'</tr>'
                )

            # Cabecera de tabla con nombres de evaluación
            eval_th = ''.join(
                f'<th class="am-th-cell">{ev}</th>'
                for ev in eval_labels
            )
            gn_th = (
                '<th class="am-th-cell am-group-col">Grupo (media)</th>'
            ) if group_count > 0 else ''
            cn_th = (
                '<th class="am-th-cell am-center-col">Centro (media)</th>'
            ) if center_count > 0 else ''

            summary_table = f"""
            <div style="overflow-x:auto;margin-top:16px;">
                <table style="width:100%;border-collapse:collapse;background:var(--am-surface);
                              border:1px solid var(--am-border);border-radius:8px;overflow:hidden;">
                    <thead>
                        <tr style="background:var(--am-light);">
                            <th class="am-th-label">Escala</th>
                            {eval_th}
                            <th class="am-th-cell">Evolución</th>
                            {gn_th}{cn_th}
                        </tr>
                    </thead>
                    <tbody>{summary_rows}</tbody>
                </table>
            </div>"""

            charts_html.append(f"""
        <div style="background:var(--am-surface);border:1px solid var(--am-border);
                    border-radius:10px;margin-bottom:24px;overflow:hidden;">
            <div style="padding:16px 20px;border-bottom:1px solid var(--am-border);
                        display:flex;align-items:center;gap:8px;">
                <i class="fa-solid fa-chart-line" style="color:var(--am-primary);font-size:13px;"></i>
                <span style="font-size:14px;font-weight:700;color:var(--am-text);">{survey_data['title']}</span>
                <span style="margin-left:auto;font-size:11px;color:var(--am-muted);">{len(eval_labels)} evaluaciones</span>
            </div>
            <div style="padding:20px;">
                <div style="position:relative;height:220px;">
                    <canvas id="{canvas_id}"></canvas>
                </div>
                {summary_table}
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
                        interaction: {{ mode: 'index', intersect: false }},
                        plugins: {{
                            legend: {{
                                display: true, position: 'bottom',
                                labels: {{ usePointStyle: true, padding: 14, font: {{ size: 11 }} }}
                            }},
                            tooltip: {{
                                callbacks: {{
                                    label: function(c) {{
                                        var v = c.parsed.y;
                                        return c.dataset.label + ': ' + (v !== null ? v.toFixed(1) : '—');
                                    }}
                                }}
                            }}
                        }},
                        scales: {{
                            x: {{
                                grid: {{ display: false }},
                                ticks: {{ font: {{ size: 11 }}, color: '{palette.UI_MUTED}' }}
                            }},
                            y: {{
                                beginAtZero: true,
                                suggestedMax: {scale_max:.0f},
                                grid: {{ color: 'rgba(0,0,0,0.04)' }},
                                ticks: {{ font: {{ size: 11 }}, color: '{palette.UI_MUTED}' }}
                            }}
                        }},
                        animation: {{ duration: 500 }}
                    }}
                }});
            }})();
            </script>
        </div>""")

        if not charts_html:
            return ''

        return '\n'.join(charts_html)

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

        # ── Gráfico Chart.js horizontal por sub-escala ─────────────────
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

            _sev_fill = {0: '#34d399', 1: '#fbbf24', 2: '#f87171'}

            # Construir datos para Chart.js
            labels       = []
            scores       = []
            bar_colors   = []
            g_mean_pts   = []   # scatter dataset — un punto por barra
            c_mean_pts   = []
            scale_maxes_ordered = []

            for scale_name in ordered_scales:
                scale_data   = scale_scores[scale_name]
                score        = scale_data.get('score', 0) if isinstance(scale_data, dict) else float(scale_data)
                s_sev        = min(scale_data.get('severity', 0) if isinstance(scale_data, dict) else 0, 2)
                fill_color   = _sev_fill.get(s_sev, '#34d399')
                scale_max    = max(scale_maxes.get(scale_name, 10), 1)
                display_name = (_meta.get(scale_name) or {}).get('label') or scale_name.replace('_', ' ').capitalize()

                labels.append(display_name)
                scores.append(round(score, 2))
                bar_colors.append(fill_color)
                scale_maxes_ordered.append(scale_max)

                g_mean = g_means.get(scale_name)
                c_mean = c_means.get(scale_name)
                # Para scatter: x = valor de la media, y = label del eje categórico
                g_mean_pts.append(round(g_mean, 2) if g_mean is not None else None)
                c_mean_pts.append(round(c_mean, 2) if c_mean is not None else None)

            canvas_id  = f'am-drawer-chart-{rid}'
            chart_h    = max(120, len(labels) * 44)  # altura mínima 120px
            scale_max_global = max(scale_maxes_ordered) if scale_maxes_ordered else 10

            # Datasets: barras del alumno + marcadores de media (line/showLine:false)
            # NOTA: scatter + indexAxis:'y' no funciona en Chart.js 4.x sobre eje
            # categórico. Usamos type:'line' con showLine:false como workaround.
            has_g = any(v is not None for v in g_mean_pts)
            has_c = any(v is not None for v in c_mean_pts)

            datasets = [
                {
                    'type': 'bar',
                    'label': 'Alumno',
                    'data': scores,
                    'backgroundColor': bar_colors,
                    'borderRadius': 5,
                    'borderSkipped': False,
                    'barThickness': 18,
                    'order': 2,
                }
            ]
            if has_g:
                datasets.append({
                    'type': 'line',
                    'label': 'Media grupo',
                    'data': g_mean_pts,   # indexed igual que labels
                    'showLine': False,
                    'backgroundColor': '#94a3b8',
                    'borderColor': '#94a3b8',
                    'pointStyle': 'rectRot',
                    'pointRadius': 7,
                    'pointHoverRadius': 9,
                    'borderWidth': 0,
                    'order': 1,
                    'spanGaps': True,
                })
            if has_c:
                datasets.append({
                    'type': 'line',
                    'label': 'Media centro',
                    'data': c_mean_pts,   # indexed igual que labels
                    'showLine': False,
                    'backgroundColor': palette.UI_PRIMARY,
                    'borderColor': palette.UI_PRIMARY,
                    'pointStyle': 'rectRot',
                    'pointRadius': 7,
                    'pointHoverRadius': 9,
                    'borderWidth': 0,
                    'order': 0,
                    'spanGaps': True,
                })

            chart_cfg = {
                'type': 'bar',
                'data': {
                    'labels': labels,
                    'datasets': datasets,
                },
                'options': {
                    'indexAxis': 'y',
                    'responsive': True,
                    'maintainAspectRatio': False,
                    'animation': {'duration': 500, 'easing': 'easeOutQuart'},
                    'layout': {'padding': {'right': 8}},
                    'scales': {
                        'x': {
                            'min': 0,
                            'max': scale_max_global,
                            'grid': {'color': palette.UI_GRID_LINE},
                            'ticks': {
                                'color': palette.UI_MUTED,
                                'font': {'size': 10, 'family': palette.CHART_FONT},
                            },
                            'border': {'dash': [3, 3]},
                        },
                        'y': {
                            'grid': {'display': False},
                            'ticks': {
                                'color': palette.UI_TEXT,
                                'font': {'size': 11, 'family': palette.CHART_FONT, 'weight': '600'},
                            },
                        },
                    },
                    'plugins': {
                        'legend': {
                            'display': (has_g or has_c),
                            'position': 'top',
                            'align': 'end',
                            'labels': {
                                'boxWidth': 10,
                                'boxHeight': 10,
                                'padding': 12,
                                'usePointStyle': True,
                                'font': {'size': 11, 'family': palette.CHART_FONT},
                                'color': palette.UI_MUTED,
                            },
                        },
                        'tooltip': {
                            'backgroundColor': palette.UI_TOOLTIP_BG,
                            'padding': 10,
                            'cornerRadius': 6,
                            'titleFont': {'size': 12, 'weight': '600', 'family': palette.CHART_FONT},
                            'bodyFont': {'size': 11, 'family': palette.CHART_FONT},
                        },
                    },
                },
            }

            cfg_json = _json.dumps(chart_cfg)

            # Config almacenada en <script type="application/json"> (nunca ejecuta)
            # amOpenDrawer la lee y pasa el canvas visible a Chart.js
            scale_bars_html = f"""
<span class="am-drawer-section-label">Desglose por subescalas</span>
<div style="position:relative;height:{chart_h}px;margin-bottom:8px;">
    <canvas class="am-chart-canvas" style="display:block;width:100%;height:100%;"></canvas>
</div>
<script type="application/json" class="am-chart-cfg">{cfg_json}</script>"""

        desc_html = ''
        if result.baremo_description:
            desc_html = (
                f'<div class="am-drawer-interp">'
                f'<span class="am-drawer-interp__label">Interpretación clínica</span>'
                f'<p class="am-drawer-interp__text">{result.baremo_description}</p>'
                f'</div>'
            )

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
            <div class="am-drawer__date">{meta_str}</div>
            {desc_html}{scale_bars_html}{notes_html}
        </div>
        <div id="am-drawer-footer-{rid}" style="display:none;">
            <a href="{pdf_url}" target="_blank" class="btn-primary">
                <i class="fa-solid fa-file-pdf"></i>Descargar informe
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

    def _get_survey_result_context(self, survey_id, student_id, evaluation_id=None):
        """Calcula medias por escala del grupo y del centro para comparativa.

        Usa el academic_group_id congelado en cada SurveyResult (no el grupo actual
        del alumno) para que las comparativas históricas sean correctas aunque el
        alumno haya cambiado de grupo al año siguiente.

        Si se proporciona evaluation_id, la comparativa se acota a esa evaluación
        (mismo cohorte exacto), lo que es lo correcto para la vista de timeline.
        Sin evaluation_id se compara contra todos los resultados históricos del
        centro (útil para la gráfica de evolución multi-año).
        """
        SurveyResult = self.env['aula_metrics.survey_result']

        base_domain = [
            ('survey_id', '=', survey_id),
            ('student_id', '!=', student_id),
        ]
        if evaluation_id:
            base_domain.append(('evaluation_id', '=', evaluation_id))

        all_others = SurveyResult.search(base_domain)

        # Obtener el grupo histórico del alumno: usar el academic_group_id congelado
        # en su propio SurveyResult para esta evaluación/cuestionario.
        ref_domain = [('survey_id', '=', survey_id), ('student_id', '=', student_id)]
        if evaluation_id:
            ref_domain.append(('evaluation_id', '=', evaluation_id))
        ref_result = SurveyResult.search(ref_domain, order='completed_at desc', limit=1)

        if ref_result and ref_result.academic_group_id:
            frozen_group_id = ref_result.academic_group_id.id
        else:
            # Fallback para registros anteriores a la congelación
            student = self.env['res.partner'].browse(student_id)
            frozen_group_id = student.academic_group_id.id if student.academic_group_id else None

        # Filtrar peers usando el academic_group_id congelado en cada resultado
        group_others = all_others.filtered(
            lambda r: frozen_group_id and r.academic_group_id.id == frozen_group_id
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


