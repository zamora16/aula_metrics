# -*- coding: utf-8 -*-
"""
Cuestionarios oficiales AulaMetrics en el perfil de alumno:
lista de resultados en acordeón con desglose por sub-escalas y comparativa
de grupo/centro.
"""
from odoo import models, api
from ...utils import palette


class DashboardStudentSurveys(models.TransientModel):
    _inherit = 'aula_metrics.dashboard.student_profile'

    def _get_official_surveys_html(self, student_id):
        """
        Sección de cuestionarios oficiales: filas compactas ordenadas por fecha.
        Cada fila expande inline con el desglose por sub-escalas + comparativa.

        Returns:
            str: HTML de la sección, o '' si no hay resultados.
        """
        SurveyResult = self.env['aula_metrics.survey_result']
        results = SurveyResult.search([
            ('student_id', '=', student_id),
            ('is_aulametrics', '=', True),
        ], order='completed_at desc')

        if not results:
            return ''

        # Pre-calcular scale_maxes y meta por survey_id
        BaremoRange  = self.env['aula_metrics.survey_baremo_range']
        maxes_cache  = {}
        meta_cache   = {}
        seen_sids    = list(dict.fromkeys(r.survey_id.id for r in results))

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

        # Agrupar por cuestionario
        groups_data = {}
        for r in results:
            sid = r.survey_id.id
            if sid not in groups_data:
                groups_data[sid] = {'title': r.survey_id.title or '—', 'results': []}
            groups_data[sid]['results'].append(r)

        groups_html = []
        for sid in seen_sids:
            g           = groups_data[sid]
            scale_maxes = maxes_cache[sid]
            scale_meta  = meta_cache[sid]
            ctx         = self._get_survey_result_context(sid, student_id)

            rows_html = ''.join(
                self._build_survey_result_row(r, scale_maxes, ctx, scale_meta)
                for r in g['results']
            )
            groups_html.append(f"""
            <div class="mb-3">
                <div class="d-flex align-items-center gap-2 mb-2 px-1">
                    <i class="fa-solid fa-clipboard-list" style="color:var(--am-primary);font-size:13px;"></i>
                    <span style="font-size:12px;font-weight:600;color:var(--am-muted);letter-spacing:0.04em;text-transform:uppercase;">{g['title']}</span>
                    <span style="font-size:11px;flex:1;height:1px;background:var(--am-border);display:inline-block;vertical-align:middle;"></span>
                </div>
                <div class="official-survey-list">{rows_html}</div>
            </div>""")

        return '\n'.join(groups_html)

    def _build_survey_result_row(self, result, scale_maxes, context=None, scale_meta=None):
        """
        Fila acordeón para un resultado de cuestionario oficial.
        Cabecera: fecha · evaluación · puntuación global · badge de severidad.
        Cuerpo: barra horizontal por sub-escala con marcadores de grupo/centro.
        """
        rid         = result.id
        collapse_id = f'sr-detail-{rid}'

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
