# -*- coding: utf-8 -*-
"""
Informe de Evaluación — Capa de presentación HTML.

Vistas por rol:
  Admin / Counselor → selector de vista: Por grupo | Por nivel | Centro
  Management        → selector de vista: Por nivel | Centro  (sin grupos)
  Tutor             → Sus grupos vs media del centro (sin otras vistas)

Principio: el rol determina qué vistas están disponibles; los datos subyacentes
(by_level, groups, center_mean) son idénticos, solo varía lo que se renderiza.
"""
import json
import logging
from datetime import date as _date

from odoo import models, api
from markupsafe import Markup
from ...utils import dashboard_styles, dashboard_helpers
from ...utils.constants import ROLE_MANAGEMENT, ROLE_TUTOR, ROLE_ADMIN, ROLE_COUNSELOR

_logger = logging.getLogger(__name__)

_CHART_JS_CDN = (
    '<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js">'
    '</script>'
)

# Colores para series sin baremo asignado
_GROUP_COLORS = [
    '#4f8ef7', '#f7934f', '#4fc88e', '#f74f6b', '#b44ff7',
    '#4fd4f7', '#f7e24f', '#f74fc8', '#4ff7b4', '#7b4ff7',
]

# Script que redimensiona los charts de Chart.js cuando Bootstrap muestra una
# pestaña oculta (el canvas tenía tamaño cero cuando se inicializó).
_TAB_RESIZE_SCRIPT = """
<script>
document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('[data-bs-toggle="pill"],[data-bs-toggle="tab"]')
        .forEach(function (el) {
            el.addEventListener('shown.bs.tab', function (e) {
                var target = document.querySelector(e.target.getAttribute('data-bs-target'));
                if (target && window.Chart) {
                    target.querySelectorAll('canvas').forEach(function (canvas) {
                        var chart = Chart.getChart(canvas);
                        if (chart) { chart.resize(); chart.update(); }
                    });
                }
            });
        });
});
</script>"""


class DashboardEvaluationReportSections(models.TransientModel):
    _inherit = 'aula_metrics.dashboard.evaluation_report'

    # ──────────────────────────────────────────────────────────────────────
    # Ensamblador principal
    # ──────────────────────────────────────────────────────────────────────

    @api.model
    def _build_report_context(self, evaluation, role_info,
                               participation_data, surveys_data):
        role       = role_info.get('role')
        state_meta = {
            'active':    {'label': 'Activa',     'css': 'success'},
            'scheduled': {'label': 'Programada', 'css': 'warning'},
            'closed':    {'label': 'Cerrada',    'css': 'secondary'},
            'draft':     {'label': 'Borrador',   'css': 'light'},
            'cancelled': {'label': 'Cancelada',  'css': 'danger'},
        }
        smeta      = state_meta.get(evaluation.state, {'label': evaluation.state, 'css': 'secondary'})
        date_range = dashboard_helpers.format_date_range(evaluation.date_start, evaluation.date_end)
        today_str  = _date.today().strftime('%d/%m/%Y')

        kpis_html          = self._build_kpis_html(participation_data, surveys_data, evaluation)
        participation_html = self._build_participation_html(participation_data, role_info)
        surveys_html       = self._build_surveys_html(surveys_data, role_info)

        content_html = Markup(
            self._build_content_html(
                evaluation, smeta, date_range, today_str,
                kpis_html, participation_html, surveys_html,
            )
        )

        return {
            'page_title':           f'Informe — {evaluation.name}',
            'css_styles':           Markup(dashboard_styles.get_common_styles() + self._report_styles()),
            'head_extra':           Markup(_CHART_JS_CDN),
            'role_info':            role_info,
            'active_section':       'evaluations',
            'topbar_title':         evaluation.name,
            'topbar_subtitle':      Markup(
                f'<i class="fa-solid fa-chart-bar me-2"></i>'
                f'Informe de Evaluación · {date_range}'
            ),
            'topbar_extra_actions': Markup(
                f'<a href="/aulametrics/evaluacion/{evaluation.id}/informe_pdf" '
                f'   class="btn-filter-action btn-filter-primary" target="_blank">'
                f'<i class="fa-solid fa-file-pdf"></i>Exportar PDF</a>'
                f'<a href="/aulametrics/dashboard" class="btn-filter-action">'
                f'<i class="fa-solid fa-arrow-left"></i>Volver</a>'
            ),
            'content_html':         content_html,
            'scripts_html':         Markup(_TAB_RESIZE_SCRIPT),
        }

    # ──────────────────────────────────────────────────────────────────────
    # Esqueleto de la página
    # ──────────────────────────────────────────────────────────────────────

    @api.model
    def _build_content_html(self, evaluation, smeta, date_range, today_str,
                             kpis_html, participation_html, surveys_html):
        state_badge = f'<span class="badge bg-{smeta["css"]}">{smeta["label"]}</span>'
        return f"""
<div class="evaluation-report-page">
  <div class="d-flex align-items-center gap-3 mb-4 pb-3" style="border-bottom:1px solid var(--am-border,#e5e7eb);">
    {state_badge}
    <span class="text-muted small">Generado: {today_str}</span>
  </div>
  {kpis_html}
  {participation_html}
  {surveys_html}
</div>"""

    # ──────────────────────────────────────────────────────────────────────
    # KPIs globales
    # ──────────────────────────────────────────────────────────────────────

    @api.model
    def _build_kpis_html(self, participation_data, surveys_data, evaluation):
        totals    = participation_data['totals']
        n_surveys = len(surveys_data)
        n_groups  = len(participation_data['by_group'])
        rate      = totals['rate']
        rate_color = (
            'var(--am-success)' if rate >= 80
            else ('var(--am-warning)' if rate >= 50 else 'var(--am-danger)')
        )

        kpis = [
            {
                'icon': 'fa-users',
                'value': str(totals['total']),
                'label': 'Alumnos',
                'sub': f'Participación {rate}%',
                'icon_color': 'var(--am-primary)',
            },
            {
                'icon': 'fa-circle-check',
                'value': f'{totals["completed"]} / {totals["total"]}',
                'label': 'Completados',
                'sub': f'Tasa: {rate}%',
                'icon_color': rate_color,
            },
            {
                'icon': 'fa-layer-group',
                'value': str(n_groups),
                'label': 'Grupos',
                'sub': f'{len(set(evaluation.academic_group_ids.mapped("course_level") or []))} niveles educativos',
                'icon_color': 'var(--am-accent)',
            },
            {
                'icon': 'fa-file-alt',
                'value': str(n_surveys),
                'label': 'Cuestionarios',
                'sub': (
                    f'{sum(1 for s in surveys_data if s["is_aulametrics"])} oficiales'
                    + (
                        f' / {sum(1 for s in surveys_data if not s["is_aulametrics"])} centro'
                        if any(not s["is_aulametrics"] for s in surveys_data) else ''
                    )
                ),
                'icon_color': 'var(--am-muted)',
            },
        ]
        cards = ''.join(
            f'<div class="kpi-card">'
            f'<div class="kpi-label">'
            f'<i class="fa-solid {k["icon"]} me-1" style="color:{k["icon_color"]};"></i>'
            f'{k["label"]}</div>'
            f'<div class="kpi-value">{k["value"]}</div>'
            f'<div class="kpi-description">{k["sub"]}</div>'
            f'</div>'
            for k in kpis
        )
        return f'<div class="kpi-container mb-4">{cards}</div>'

    # ──────────────────────────────────────────────────────────────────────
    # Participación
    # ──────────────────────────────────────────────────────────────────────

    @api.model
    def _build_participation_html(self, participation_data, role_info):
        is_management = role_info.get('role') == ROLE_MANAGEMENT
        rows_data     = participation_data['by_level'] if is_management else participation_data['by_group']
        totals        = participation_data['totals']
        if not rows_data:
            return ''

        col_header = 'Nivel educativo' if is_management else 'Grupo'
        col_key    = 'label' if is_management else 'group_name'

        def _row(row, bold=False):
            rate    = row['rate']
            cls     = 'success' if rate >= 80 else ('warning' if rate >= 50 else 'danger')
            bar     = (f'<div class="progress" style="height:6px;">'
                       f'<div class="progress-bar bg-{cls}" style="width:{rate}%"></div></div>')
            fw      = ' fw-bold' if bold else ''
            return (f'<tr class="{"table-light" if bold else ""}">'
                    f'<td class="fw-medium{fw}">{row.get(col_key, "Total")}</td>'
                    f'<td class="text-center">{row["total"]}</td>'
                    f'<td class="text-center">{row["completed"]}</td>'
                    f'<td style="min-width:120px;">'
                    f'<div class="d-flex align-items-center gap-2">'
                    f'<span class="text-{cls} fw-semibold">{rate}%</span>'
                    f'<div class="flex-grow-1">{bar}</div></div></td></tr>')

        rows_html = ''.join(_row(r) for r in rows_data)
        rows_html += _row(totals | {col_key: 'Total'}, bold=True)

        return f"""
<div class="report-section card mb-4">
  <div class="card-header d-flex align-items-center gap-2">
    <i class="fa-solid fa-circle-check text-success"></i>
    <span class="fw-semibold">Participación</span>
  </div>
  <div class="card-body p-0">
    <table class="table table-hover mb-0 report-table">
      <thead><tr>
        <th>{col_header}</th><th class="text-center">Total</th>
        <th class="text-center">Completados</th><th>Tasa</th>
      </tr></thead>
      <tbody>{rows_html}</tbody>
    </table>
  </div>
</div>"""

    # ──────────────────────────────────────────────────────────────────────
    # Cuestionarios — dispatcher
    # ──────────────────────────────────────────────────────────────────────

    @api.model
    def _build_surveys_html(self, surveys_data, role_info):
        if not surveys_data:
            return ('<div class="alert alert-info mb-4">'
                    '<i class="fa fa-info-circle me-2"></i>'
                    'No hay resultados disponibles para este rol y evaluación.</div>')
        return '\n'.join(
            self._build_text_survey_html(sd, role_info)
            if sd.get('is_text_survey')
            else (
                self._build_official_survey_html(sd, role_info)
                if sd['is_aulametrics']
                else self._build_adhoc_survey_html(sd, role_info)
            )
            for sd in surveys_data
        )

    # ──────────────────────────────────────────────────────────────────────
    # Cuestionario oficial — tarjeta con escalas y selector de vista
    # ──────────────────────────────────────────────────────────────────────

    @api.model
    def _build_official_survey_html(self, survey_data, role_info):
        sid           = survey_data['survey_id']
        survey_name   = survey_data['survey_name']
        scales        = survey_data['scales']
        severity_meta = survey_data['severity_meta']
        n_results     = survey_data['n_results']

        if not scales:
            return f'<div class="alert alert-warning mb-4">Sin datos para {survey_name}.</div>'

        multi_scale = len(scales) > 1
        if multi_scale:
            tab_nav   = self._scale_tab_nav(sid, scales)
            tab_panes = ''.join(
                self._scale_tab_pane(sid, scale, severity_meta, role_info, active=(i == 0))
                for i, scale in enumerate(scales)
            )
            body = (f'<ul class="nav nav-tabs card-header-tabs mb-3" role="tablist">{tab_nav}</ul>'
                    f'<div class="tab-content">{tab_panes}</div>')
        else:
            body = self._scale_pane_content(sid, scales[0], severity_meta, role_info)

        return f"""
<div class="report-section card mb-4 border-primary-subtle">
  <div class="card-header d-flex align-items-center justify-content-between">
    <div class="d-flex align-items-center gap-2">
      <span class="badge bg-primary">Oficial</span>
      <span class="fw-semibold">{survey_name}</span>
    </div>
    <span class="text-muted small">{n_results} resultado(s)</span>
  </div>
  <div class="card-body">{body}</div>
</div>"""

    @api.model
    def _scale_tab_nav(self, survey_id, scales):
        return ''.join(
            f'<li class="nav-item" role="presentation">'
            f'<button class="nav-link {"active" if i == 0 else ""}" '
            f'data-bs-toggle="tab" data-bs-target="#scale-{survey_id}-{sc["scale_name"]}" '
            f'type="button" role="tab">{sc["scale_label"]}</button></li>'
            for i, sc in enumerate(scales)
        )

    @api.model
    def _scale_tab_pane(self, survey_id, scale, severity_meta, role_info, active=False):
        pane_id    = f'scale-{survey_id}-{scale["scale_name"]}'
        active_cls = 'show active' if active else ''
        content    = self._scale_pane_content(survey_id, scale, severity_meta, role_info)
        return (f'<div class="tab-pane fade {active_cls}" id="{pane_id}" role="tabpanel">'
                f'{content}</div>')

    @api.model
    def _scale_pane_content(self, survey_id, scale, severity_meta, role_info):
        """Despacha al builder de vista correcto según el rol."""
        role = role_info.get('role')
        if role == ROLE_TUTOR:
            return self._build_tutor_scale_view(survey_id, scale, severity_meta)
        if role == ROLE_MANAGEMENT:
            return self._build_management_scale_view(survey_id, scale, severity_meta)
        # Admin / Counselor: tres vistas
        return self._build_full_scale_view(survey_id, scale, severity_meta)

    # ── Vista admin/counselor: grupos | niveles | centro ──────────────────

    @api.model
    def _build_full_scale_view(self, survey_id, scale, severity_meta):
        """Selector de tres vistas: Por grupo / Por nivel / Centro."""
        sn   = scale['scale_name']
        base = f'{survey_id}-{sn}'

        pills = (
            f'<ul class="nav nav-pills mb-3 view-pills" role="tablist">'
            f'<li class="nav-item"><button class="nav-link active" data-bs-toggle="pill" '
            f'data-bs-target="#vg-{base}" type="button">Por grupo</button></li>'
            f'<li class="nav-item"><button class="nav-link" data-bs-toggle="pill" '
            f'data-bs-target="#vl-{base}" type="button">Por nivel</button></li>'
            f'<li class="nav-item"><button class="nav-link" data-bs-toggle="pill" '
            f'data-bs-target="#vc-{base}" type="button">Centro</button></li>'
            f'</ul>'
        )
        groups_panel = self._render_scale_results_panel(
            f'g-{base}', scale['groups'], scale, severity_meta,
            name_key='group_name',
        )
        levels_panel = self._render_scale_results_panel(
            f'l-{base}', scale['by_level'], scale, severity_meta,
            name_key='label',
        )
        center_panel = self._render_center_panel(scale, severity_meta)

        panes = (
            f'<div class="tab-content">'
            f'<div class="tab-pane show active" id="vg-{base}">{groups_panel}</div>'
            f'<div class="tab-pane" id="vl-{base}">{levels_panel}</div>'
            f'<div class="tab-pane" id="vc-{base}">{center_panel}</div>'
            f'</div>'
        )
        return pills + panes

    # ── Vista management: niveles | centro ────────────────────────────────

    @api.model
    def _build_management_scale_view(self, survey_id, scale, severity_meta):
        sn   = scale['scale_name']
        base = f'{survey_id}-{sn}'

        pills = (
            f'<ul class="nav nav-pills mb-3 view-pills" role="tablist">'
            f'<li class="nav-item"><button class="nav-link active" data-bs-toggle="pill" '
            f'data-bs-target="#vl-{base}" type="button">Por nivel</button></li>'
            f'<li class="nav-item"><button class="nav-link" data-bs-toggle="pill" '
            f'data-bs-target="#vc-{base}" type="button">Centro</button></li>'
            f'</ul>'
        )
        levels_panel = self._render_scale_results_panel(
            f'l-{base}', scale['by_level'], scale, severity_meta,
            name_key='label',
        )
        center_panel = self._render_center_panel(scale, severity_meta)

        panes = (
            f'<div class="tab-content">'
            f'<div class="tab-pane show active" id="vl-{base}">{levels_panel}</div>'
            f'<div class="tab-pane" id="vc-{base}">{center_panel}</div>'
            f'</div>'
        )
        return pills + panes

    # ── Vista tutor: sus grupos vs media del centro ───────────────────────

    @api.model
    def _build_tutor_scale_view(self, survey_id, scale, severity_meta):
        """
        Muestra barras agrupadas: grupo(s) del tutor + nivel educativo + centro.
        """
        groups        = scale['groups']
        center_mean   = scale.get('center_mean')
        center_n      = scale.get('center_n')
        center_bar    = scale.get('center_baremo')
        center_sev    = scale.get('center_sev_dist') or {}
        tutor_levels  = scale.get('tutor_level_ref') or {}
        sn            = scale['scale_name']
        canvas_id     = f'amrep-tutor-{survey_id}-{sn}'

        if not groups:
            return '<p class="text-muted small">Sin datos de grupos para tu rol.</p>'

        # ── Gráfico de barras agrupadas ───────────────────────────────────
        bar_items = []
        for g in groups:
            bar_items.append({
                'name':  g['group_name'],
                'value': g['mean_score'],
                'color': g.get('baremo_color') or _GROUP_COLORS[0],
            })
        for ldata in tutor_levels.values():
            bar_items.append({
                'name':  ldata['label'],
                'value': ldata['mean_score'],
                'color': ldata.get('baremo_color') or '#6c757d',
            })
        if center_mean is not None:
            bar_items.append({
                'name':  'Centro',
                'value': center_mean,
                'color': center_bar['color'] if center_bar else '#6c757d',
            })

        labels = [it['name'] for it in bar_items]
        values = [it['value'] for it in bar_items]
        colors = [it['color'] for it in bar_items]
        cfg = {
            'type': 'bar',
            'data': {'labels': labels, 'datasets': [{
                'data': values, 'backgroundColor': colors,
                'borderColor': colors, 'borderWidth': 1, 'borderRadius': 4,
            }]},
            'options': {
                'responsive': True, 'maintainAspectRatio': True,
                'plugins': {'legend': {'display': False}},
                'scales': {
                    'y': {
                        'min': float(scale['score_min']),
                        'suggestedMax': float(scale['score_max']),
                        'title': {'display': True, 'text': 'Puntuación media'},
                    },
                    'x': {'ticks': {'maxRotation': 45}},
                },
            },
        }
        chart_html = f'<div class="chart-wrapper-sm">{self._canvas_with_script(canvas_id, cfg)}</div>'

        # ── Tabla ─────────────────────────────────────────────────────────
        bm = scale.get('baremo_meta') or {}
        sev_headers = ''.join(
            f'<th class="text-center small">{label}</th>'
            for label in bm.keys()
        ) if bm else ''

        def _sev_cells(sev_dist, n):
            if not bm:
                return ''
            n = n or 1
            return ''.join(
                f'<td class="text-center small" style="color:{meta.get("color","#6c757d")};">'
                f'{round(sev_dist.get(label, 0) / n * 100)}%</td>'
                for label, meta in bm.items()
            )

        rows = ''
        for g in groups:
            badge = (
                f'<span class="badge" style="background:{g["baremo_color"]};">'
                f'{g["baremo_label"]}</span>'
                if g.get('baremo_label') else '—'
            )
            rows += (
                f'<tr><td class="fw-medium">{g["group_name"]}</td>'
                f'<td class="text-center">{g["n"]}</td>'
                f'<td class="text-center fw-semibold">{g["mean_score"]}</td>'
                f'<td>{badge}</td>{_sev_cells(g.get("sev_dist", {}), g["n"])}</tr>'
            )

        for ldata in tutor_levels.values():
            lb_badge = (
                f'<span class="badge" style="background:{ldata.get("baremo_color","#6c757d")};">'
                f'{ldata["baremo_label"]}</span>'
                if ldata.get('baremo_label') else '—'
            )
            rows += (
                f'<tr style="background:rgba(26,92,82,.06);">'
                f'<td class="fw-semibold" style="color:var(--am-primary,#1A5C52);">'
                f'<i class="fa-solid fa-graduation-cap me-1 small"></i>'
                f'{ldata["label"]}</td>'
                f'<td class="text-center">{ldata.get("n", "—")}</td>'
                f'<td class="text-center fw-semibold">{ldata["mean_score"]}</td>'
                f'<td>{lb_badge}</td>'
                f'{_sev_cells(ldata.get("sev_dist", {}), ldata.get("n", 0))}</tr>'
            )

        if center_mean is not None:
            cb_badge = (
                f'<span class="badge" style="background:{center_bar["color"]};">'
                f'{center_bar["label"]}</span>'
                if center_bar else '—'
            )
            rows += (
                f'<tr style="background:var(--am-subtle,#f8fafc);">'
                f'<td class="fw-semibold text-muted">'
                f'<i class="fa-solid fa-school me-1 small"></i>Centro</td>'
                f'<td class="text-center">{center_n if center_n is not None else "—"}</td>'
                f'<td class="text-center fw-semibold">{center_mean}</td>'
                f'<td>{cb_badge}</td>'
                f'{_sev_cells(center_sev, center_n or 0)}</tr>'
            )

        table = f"""
<div class="table-responsive mt-3">
  <table class="table table-sm table-hover report-table mb-0">
    <thead><tr>
      <th>Grupo / Referencia</th><th class="text-center">N</th>
      <th class="text-center">Media</th><th>Baremo</th>{sev_headers}
    </tr></thead>
    <tbody>{rows}</tbody>
  </table>
</div>"""

        return f'<div class="row g-3"><div class="col-lg-8">{chart_html}</div></div>{table}'

    # ── Paneles genéricos de resultados (grupos o niveles) ────────────────

    @api.model
    def _render_scale_results_panel(self, uid, items, scale, severity_meta, name_key):
        """
        Renderiza un panel con gráfico apilado por baremo + tabla.
        Funciona tanto para 'groups' (name_key='group_name') como 'by_level' (name_key='label').
        El pie chart de distribución solo tiene sentido a nivel de centro, no aquí.
        """
        if not items:
            return '<p class="text-muted small py-2">Sin datos suficientes.</p>'

        canvas_id  = f'amrep-bar-{uid}'
        baremo_meta = scale.get('baremo_meta') or {}
        has_sev_data = baremo_meta and any(
            any(it.get('sev_dist', {}).values()) for it in items
        )
        if has_sev_data:
            chart = self._stacked_bar_html(canvas_id, items, name_key, baremo_meta)
        else:
            chart = self._canvas_with_script(
                canvas_id,
                self._plain_bar_cfg(items, name_key, scale['score_min'], scale['score_max']),
            )
        table = self._scale_result_table(items, scale, baremo_meta, name_key)
        return f'<div class="mb-3">{chart}</div>{table}'

    @api.model
    def _render_center_panel(self, scale, severity_meta):
        """Resumen del centro: media global + baremo + distribución de severidad como pie chart."""
        center_mean = scale.get('center_mean')
        center_bar  = scale.get('center_baremo')
        sev_dist    = scale.get('center_sev_dist', {})
        baremo_meta = scale.get('baremo_meta') or {}

        if center_mean is None:
            return '<p class="text-muted small py-2">Sin datos de centro.</p>'

        badge = (f'<span class="badge fs-6 ms-2" style="background:{center_bar["color"]};">'
                 f'{center_bar["label"]}</span>'
                 if center_bar else '')

        pie_col = ''
        if baremo_meta and sev_dist and any(sev_dist.values()):
            canvas_id = f'amrep-center-pie-{abs(hash(scale.get("scale_name","") + ",".join(baremo_meta.keys())))%100000}'
            labels  = list(baremo_meta.keys())
            colors  = [m.get('color', '#6c757d') for m in baremo_meta.values()]
            data    = [sev_dist.get(label, 0) for label in labels]
            cfg = {
                'type': 'doughnut',
                'data': {'labels': labels, 'datasets': [{'data': data,
                          'backgroundColor': colors, 'borderWidth': 2}]},
                'options': {
                    'responsive': True, 'maintainAspectRatio': True,
                    'aspectRatio': 1.5,
                    'cutout': '60%',
                    'plugins': {
                        'legend': {'position': 'bottom',
                                   'labels': {'boxWidth': 12, 'font': {'size': 11}}},
                    },
                },
            }
            cfg_json = json.dumps(cfg)
            script = (
                f'<script>document.addEventListener("DOMContentLoaded",function(){{'
                f'var ctx=document.getElementById("{canvas_id}");'
                f'if(ctx){{new Chart(ctx,{cfg_json});}}}});</script>'
            )
            pie_col = (
                f'<div class="center-pie-col">'
                f'<div class="donut-title text-muted small mb-1">Distribución del centro</div>'
                f'<div class="chart-wrapper-sm">'
                f'<canvas id="{canvas_id}" height="200"></canvas></div>'
                f'{script}</div>'
            )

        return f"""
<div class="center-view-wrapper">
  <div class="center-kpi-block">
    <div class="center-kpi-score">{center_mean}</div>
    <div class="mt-2">{badge}</div>
    <div class="text-muted small mt-1">Media del centro</div>
  </div>
  {pie_col}
</div>"""

    # ──────────────────────────────────────────────────────────────────────
    # Generadores de gráficos (Chart.js)
    # ──────────────────────────────────────────────────────────────────────

    @api.model
    def _stacked_bar_html(self, canvas_id, items, name_key, baremo_meta):
        """
        Stacked bar chart: X = group/level names, Y = nº de alumnos,
        un dataset por baremo (ordered by score_min via baremo_meta insertion order).
        baremo_meta: {label_str: {color}} — string-keyed.
        """
        labels   = [it.get(name_key, '') for it in items]
        datasets = []
        for label, meta in baremo_meta.items():
            data = [it.get('sev_dist', {}).get(label, 0) for it in items]
            datasets.append({
                'label':           label,
                'data':            data,
                'backgroundColor': meta.get('color', '#6c757d'),
                'borderColor':     'white',
                'borderWidth':     1,
            })
        cfg = {
            'type': 'bar',
            'data': {'labels': labels, 'datasets': datasets},
            'options': {
                'responsive': True, 'maintainAspectRatio': True,
                'plugins': {
                    'legend': {
                        'display': True, 'position': 'bottom',
                        'labels': {'boxWidth': 12, 'font': {'size': 11}},
                    },
                },
                'scales': {
                    'x': {'stacked': True, 'ticks': {'maxRotation': 45}},
                    'y': {'stacked': True, 'title': {'display': True, 'text': 'Nº de alumnos'}},
                },
            },
        }
        return self._canvas_with_script(canvas_id, cfg)

    @staticmethod
    def _plain_bar_cfg(items, name_key, y_min, y_max):
        """Config de barras simples (media) para cuestionarios sin baremos."""
        labels = [it.get(name_key, '') for it in items]
        values = [it.get('mean_score', it.get('avg', 0)) for it in items]
        colors = [
            it.get('baremo_color') or _GROUP_COLORS[i % len(_GROUP_COLORS)]
            for i, it in enumerate(items)
        ]
        return {
            'type': 'bar',
            'data': {'labels': labels, 'datasets': [{
                'data': values, 'backgroundColor': colors,
                'borderColor': colors, 'borderWidth': 1, 'borderRadius': 4,
            }]},
            'options': {
                'responsive': True, 'maintainAspectRatio': True,
                'plugins': {'legend': {'display': False}},
                'scales': {
                    'y': {'min': float(y_min), 'suggestedMax': float(y_max),
                          'title': {'display': True, 'text': 'Puntuación media'}},
                    'x': {'ticks': {'maxRotation': 45}},
                },
            },
        }

    @api.model
    def _bar_chart_html(self, canvas_id, items, name_key, y_min, y_max):
        """Gráfico de barras genérico. items: lista de dicts con name_key y mean_score."""
        labels = [it.get(name_key, '') for it in items]
        values = [it.get('mean_score', it.get('avg', 0)) for it in items]
        colors = [
            it.get('baremo_color') or _GROUP_COLORS[i % len(_GROUP_COLORS)]
            for i, it in enumerate(items)
        ]
        cfg = {
            'type': 'bar',
            'data': {'labels': labels, 'datasets': [{
                'data': values, 'backgroundColor': colors,
                'borderColor': colors, 'borderWidth': 1, 'borderRadius': 4,
            }]},
            'options': {
                'responsive': True, 'maintainAspectRatio': True,
                'plugins': {'legend': {'display': False}},
                'scales': {
                    'y': {'min': float(y_min), 'suggestedMax': float(y_max),
                          'title': {'display': True, 'text': 'Puntuación media'}},
                    'x': {'ticks': {'maxRotation': 45}},
                },
            },
        }
        return self._canvas_with_script(canvas_id, cfg)

    @api.model
    def _bar_chart_with_references(self, canvas_id, items, name_key, y_min, y_max, ref_lines=None):
        """
        Barras por grupo/nivel + una o más líneas de referencia punteadas.
        ref_lines: list[{value, label, color, dash}]
        """
        labels = [it.get(name_key, '') for it in items]
        values = [it.get('mean_score', it.get('avg', 0)) for it in items]
        colors = [
            it.get('baremo_color') or _GROUP_COLORS[i % len(_GROUP_COLORS)]
            for i, it in enumerate(items)
        ]
        datasets = [{
            'type': 'bar', 'label': 'Tu grupo',
            'data': values, 'backgroundColor': colors,
            'borderColor': colors, 'borderWidth': 1, 'borderRadius': 4,
            'order': 1,
        }]
        has_refs = bool(ref_lines)
        for rl in (ref_lines or []):
            datasets.append({
                'type': 'line', 'label': rl['label'],
                'data': [rl['value']] * len(labels),
                'borderColor': rl.get('color', '#6c757d'),
                'backgroundColor': 'transparent',
                'borderDash': rl.get('dash', [6, 4]),
                'borderWidth': 2, 'pointRadius': 4, 'pointHoverRadius': 5,
                'tension': 0, 'fill': False, 'order': 0,
            })
        cfg = {
            'type': 'bar',
            'data': {'labels': labels, 'datasets': datasets},
            'options': {
                'responsive': True, 'maintainAspectRatio': True,
                'plugins': {
                    'legend': {
                        'display': has_refs,
                        'position': 'bottom',
                        'labels': {'boxWidth': 12, 'font': {'size': 11}},
                    },
                },
                'scales': {
                    'y': {'min': float(y_min), 'suggestedMax': float(y_max),
                          'title': {'display': True, 'text': 'Puntuación media'}},
                    'x': {'ticks': {'maxRotation': 45}},
                },
            },
        }
        return f'<div class="chart-wrapper-sm">{self._canvas_with_script(canvas_id, cfg)}</div>'

    @api.model
    def _bar_chart_with_reference(self, canvas_id, items, name_key, y_min, y_max, center_value):
        """Compatibilidad: delega a _bar_chart_with_references con una sola línea."""
        ref_lines = []
        if center_value is not None:
            ref_lines.append({
                'value': center_value, 'label': 'Media del centro',
                'color': '#6c757d',    'dash': [6, 4],
            })
        return self._bar_chart_with_references(
            canvas_id, items, name_key, y_min, y_max, ref_lines=ref_lines,
        )

    @api.model
    def _severity_donut_html(self, canvas_id, items, severity_meta):
        """
        Donut con distribución de severidad agregada de todos los items.
        Labels y colores data-driven desde severity_meta.
        """
        if not severity_meta:
            return ''
        # Suma de sev_dist de todos los items
        total_dist = {}
        for it in items:
            for sev, cnt in it.get('sev_dist', {}).items():
                total_dist[sev] = total_dist.get(sev, 0) + cnt
        if not any(total_dist.values()):
            return ''

        sorted_sevs = sorted(severity_meta.items())
        labels  = [m['label'] for _, m in sorted_sevs]
        colors  = [m.get('color', '#6c757d') for _, m in sorted_sevs]
        data    = [total_dist.get(sev, 0) for sev, _ in sorted_sevs]

        cfg = {
            'type': 'doughnut',
            'data': {'labels': labels, 'datasets': [{'data': data,
                      'backgroundColor': colors, 'borderWidth': 2}]},
            'options': {
                'responsive': True, 'maintainAspectRatio': True,
                'aspectRatio': 1.8,
                'cutout': '60%',
                'plugins': {'legend': {'position': 'bottom',
                                       'labels': {'boxWidth': 12, 'font': {'size': 11}}}},
            },
        }
        script = self._canvas_with_script(canvas_id, cfg, height=200)
        return (f'<div class="chart-wrapper-donut">'
                f'<div class="donut-title text-muted small mb-1 text-center">'
                f'Distribución por nivel</div>'
                f'{script}</div>')

    @staticmethod
    def _canvas_with_script(canvas_id, cfg, height=220):
        cfg_json = json.dumps(cfg)
        script   = (f'<script>document.addEventListener("DOMContentLoaded",function(){{'
                    f'var ctx=document.getElementById("{canvas_id}");'
                    f'if(ctx){{new Chart(ctx,{cfg_json});}}}});</script>')
        return (f'<div class="chart-wrapper-sm">'
                f'<canvas id="{canvas_id}" height="{height}"></canvas></div>'
                f'{script}')

    # ──────────────────────────────────────────────────────────────────────
    # Tabla de resultados de escala
    # ──────────────────────────────────────────────────────────────────────

    @api.model
    def _scale_result_table(self, items, scale, baremo_meta, name_key):
        col_label   = 'Nivel' if name_key == 'label' else 'Grupo'
        sev_headers = ''.join(
            f'<th class="text-center small">{label}</th>'
            for label in baremo_meta.keys()
        ) if baremo_meta else ''

        rows = ''
        for it in items:
            badge = (f'<span class="badge" style="background:{it["baremo_color"]};">'
                     f'{it["baremo_label"]}</span>'
                     if it.get('baremo_label') else '—')
            sev_cells = ''
            if baremo_meta:
                n = it['n'] or 1
                for label, meta in baremo_meta.items():
                    cnt = it.get('sev_dist', {}).get(label, 0)
                    sev_cells += (f'<td class="text-center small" '
                                  f'style="color:{meta.get("color","#6c757d")};">'
                                  f'{round(cnt/n*100)}%</td>')
            mn_val  = it.get('min',  it.get('score_min',  '—'))
            mx_val  = it.get('max',  it.get('score_max',  '—'))
            rows += (f'<tr><td class="fw-medium">{it[name_key]}</td>'
                     f'<td class="text-center">{it["n"]}</td>'
                     f'<td class="text-center fw-semibold">{it["mean_score"]}</td>'
                     f'<td class="text-center text-muted small">{mn_val}</td>'
                     f'<td class="text-center text-muted small">{mx_val}</td>'
                     f'<td>{badge}</td>{sev_cells}</tr>')

        return f"""
<div class="table-responsive">
  <table class="table table-sm table-hover report-table mb-0">
    <thead><tr>
      <th>{col_label}</th><th class="text-center">N</th>
      <th class="text-center">Media</th>
      <th class="text-center">Mín</th><th class="text-center">Máx</th>
      <th>Baremo</th>{sev_headers}
    </tr></thead>
    <tbody>{rows}</tbody>
  </table>
</div>"""

    # ──────────────────────────────────────────────────────────────────────
    # Cuestionario de texto abierto — lista de respuestas por rol
    # ──────────────────────────────────────────────────────────────────────

    @api.model
    def _build_text_survey_html(self, survey_data, role_info):
        survey_name = survey_data['survey_name']
        n_responses = survey_data.get('n_responses', 0)
        top_words   = survey_data.get('top_words', [])
        center_freq = survey_data.get('center_freq', {})
        level_freq  = survey_data.get('level_freq', {})
        group_freq  = survey_data.get('group_freq', {})
        levels      = survey_data.get('levels', [])   # [(code, label), ...]
        groups      = survey_data.get('groups', [])   # [group_name, ...]
        show_groups = survey_data.get('show_groups', False)

        if not top_words:
            return (f'<div class="report-section card mb-4 border-secondary-subtle">'
                    f'<div class="card-header"><span class="badge bg-secondary me-2">Centro</span>'
                    f'<span class="fw-semibold">{survey_name}</span></div>'
                    f'<div class="card-body text-muted small">Sin respuestas registradas.</div></div>')

        # Build column descriptors
        columns = [{'key': '__center__', 'label': 'Centro', 'freq': center_freq}]
        for code, label in levels:
            columns.append({'key': code, 'label': label, 'freq': level_freq.get(code, {})})
        if show_groups:
            for gname in groups:
                columns.append({'key': gname, 'label': gname, 'freq': group_freq.get(gname, {})})

        # Per-column max for heat-map intensity
        col_maxes = {
            col['key']: max((col['freq'].get(w, 0) for w in top_words), default=1) or 1
            for col in columns
        }

        th_word = '<th class="text-freq-word-col">Palabra</th>'
        th_cols = ''.join(
            f'<th class="text-center small px-2">{col["label"]}</th>'
            for col in columns
        )

        rows_html = ''
        for word in top_words:
            cells = f'<td class="text-freq-word-col fw-medium">{word}</td>'
            for col in columns:
                cnt = col['freq'].get(word, 0)
                mx  = col_maxes[col['key']]
                if cnt > 0:
                    intensity = round(0.07 + 0.43 * cnt / mx, 2)
                    style     = f'background:rgba(26,92,82,{intensity});'
                    cells    += (f'<td class="text-center small" style="{style}">{cnt}</td>')
                else:
                    cells += '<td class="text-center small text-muted" style="color:#CEC7BE">—</td>'
            rows_html += f'<tr>{cells}</tr>'

        table_html = f"""<div class="table-responsive">
  <table class="table table-sm table-hover report-table text-freq-table mb-0">
    <thead><tr>{th_word}{th_cols}</tr></thead>
    <tbody>{rows_html}</tbody>
  </table>
</div>"""

        return f"""
<div class="report-section card mb-4 border-secondary-subtle">
  <div class="card-header d-flex align-items-center gap-2">
    <span class="badge bg-secondary">Centro</span>
    <span class="fw-semibold">{survey_name}</span>
    <span class="badge bg-light text-secondary ms-auto">{n_responses} respuesta(s)</span>
  </div>
  <div class="card-body p-3">
    <p class="text-muted small mb-2">Palabras más frecuentes en las respuestas:</p>
    {table_html}
  </div>
</div>"""

    # ──────────────────────────────────────────────────────────────────────
    # Cuestionario ad-hoc — tarjeta simple
    # ──────────────────────────────────────────────────────────────────────

    @api.model
    def _build_adhoc_survey_html(self, survey_data, role_info):
        sid         = survey_data['survey_id']
        survey_name = survey_data['survey_name']
        metrics     = survey_data['metrics']
        role        = role_info.get('role')

        if not metrics:
            return f'<div class="alert alert-warning mb-4">Sin datos para {survey_name}.</div>'

        sections_html = ''.join(
            self._adhoc_metric_html(sid, metric, role)
            for metric in metrics
        )
        return f"""
<div class="report-section card mb-4 border-secondary-subtle">
  <div class="card-header d-flex align-items-center gap-2">
    <span class="badge bg-secondary">Centro</span>
    <span class="fw-semibold">{survey_name}</span>
  </div>
  <div class="card-body">{sections_html}</div>
</div>"""

    @api.model
    def _adhoc_metric_html(self, survey_id, metric, role):
        sn         = metric['metric_name']
        label      = metric['metric_label']
        center_avg = metric.get('center_avg')

        center_badge = ''
        if center_avg is not None:
            center_badge = (f'<span class="center-summary-band ms-3">'
                            f'<span class="text-muted small me-1">Media centro:</span>'
                            f'<strong>{center_avg}</strong>'
                            f'<span class="text-muted small">/100</span></span>')

        if role == ROLE_TUTOR:
            body = self._adhoc_tutor_view(survey_id, sn, metric)
        elif role == ROLE_MANAGEMENT:
            body = self._adhoc_management_view(survey_id, sn, metric)
        else:
            body = self._adhoc_full_view(survey_id, sn, metric)

        return f"""
<div class="metric-block mb-4">
  <div class="d-flex align-items-center mb-2">
    <h6 class="fw-semibold mb-0">{label}</h6>
    {center_badge}
  </div>
  {body}
</div>"""

    @api.model
    def _adhoc_full_view(self, survey_id, sn, metric):
        """Admin/Counselor: grupos | niveles."""
        base  = f'{survey_id}-{sn}'
        pills = (
            f'<ul class="nav nav-pills mb-3 view-pills" role="tablist">'
            f'<li class="nav-item"><button class="nav-link active" data-bs-toggle="pill" '
            f'data-bs-target="#vg-ad-{base}">Por grupo</button></li>'
            f'<li class="nav-item"><button class="nav-link" data-bs-toggle="pill" '
            f'data-bs-target="#vl-ad-{base}">Por nivel</button></li>'
            f'</ul>'
        )
        groups_panel = self._adhoc_panel_html(f'g-ad-{base}', metric['groups'],
                                               name_key='group_name', center=metric.get('center_avg'))
        levels_panel = self._adhoc_panel_html(f'l-ad-{base}', metric['by_level'],
                                               name_key='label', center=metric.get('center_avg'))
        return (pills +
                f'<div class="tab-content">'
                f'<div class="tab-pane show active" id="vg-ad-{base}">{groups_panel}</div>'
                f'<div class="tab-pane" id="vl-ad-{base}">{levels_panel}</div>'
                f'</div>')

    @api.model
    def _adhoc_management_view(self, survey_id, sn, metric):
        """Management: solo por nivel."""
        uid   = f'l-ad-{survey_id}-{sn}'
        return self._adhoc_panel_html(uid, metric['by_level'],
                                      name_key='label', center=metric.get('center_avg'))

    @api.model
    def _adhoc_tutor_view(self, survey_id, sn, metric):
        """Tutor: barras agrupadas — grupo(s) + nivel educativo + centro."""
        canvas_id        = f'amrep-adhoc-tutor-{survey_id}-{sn}'
        groups           = metric['groups']
        center_avg       = metric.get('center_avg')
        center_min       = metric.get('center_min')
        center_max       = metric.get('center_max')
        center_n         = metric.get('center_n')
        tutor_level_ref  = metric.get('tutor_level_ref') or {}

        bar_items = []
        for g in groups:
            bar_items.append({'name': g['group_name'], 'value': g['avg'],
                              'color': _GROUP_COLORS[0]})
        for ldata in tutor_level_ref.values():
            bar_items.append({'name': ldata['label'], 'value': ldata['avg'],
                              'color': _GROUP_COLORS[1 % len(_GROUP_COLORS)]})
        if center_avg is not None:
            bar_items.append({'name': 'Centro', 'value': center_avg,
                              'color': _GROUP_COLORS[2 % len(_GROUP_COLORS)]})

        labels = [it['name'] for it in bar_items]
        values = [it['value'] for it in bar_items]
        colors = [it['color'] for it in bar_items]
        cfg = {
            'type': 'bar',
            'data': {'labels': labels, 'datasets': [{
                'data': values, 'backgroundColor': colors,
                'borderColor': colors, 'borderRadius': 4, 'borderWidth': 1,
            }]},
            'options': {
                'responsive': True, 'maintainAspectRatio': True,
                'plugins': {'legend': {'display': False}},
                'scales': {
                    'y': {'min': 0, 'suggestedMax': 100,
                          'title': {'display': True, 'text': 'Puntuación (0-100)'}},
                    'x': {'ticks': {'maxRotation': 45}},
                },
            },
        }
        chart = f'<div class="chart-wrapper-sm">{self._canvas_with_script(canvas_id, cfg)}</div>'

        rows = ''.join(
            f'<tr><td class="fw-medium small">{g["group_name"]}</td>'
            f'<td class="text-center small">{g.get("n","")}</td>'
            f'<td class="text-center small fw-semibold">{g.get("avg","")}</td>'
            f'<td class="text-center small text-muted">{g.get("min","—")}</td>'
            f'<td class="text-center small text-muted">{g.get("max","—")}</td>'
            f'</tr>'
            for g in groups
        )
        for ldata in tutor_level_ref.values():
            rows += (
                f'<tr style="background:rgba(26,92,82,.06);">'
                f'<td class="fw-semibold small" style="color:var(--am-primary,#1A5C52);">'
                f'<i class="fa-solid fa-graduation-cap me-1"></i>{ldata["label"]}</td>'
                f'<td class="text-center small">{ldata.get("n","—")}</td>'
                f'<td class="text-center small fw-semibold">{ldata.get("avg","")}</td>'
                f'<td class="text-center small text-muted">{ldata.get("min","—")}</td>'
                f'<td class="text-center small text-muted">{ldata.get("max","—")}</td>'
                f'</tr>'
            )
        if center_avg is not None:
            rows += (
                f'<tr style="background:var(--am-subtle,#f8fafc);">'
                f'<td class="fw-semibold small text-muted">'
                f'<i class="fa-solid fa-school me-1"></i>Centro</td>'
                f'<td class="text-center small">{center_n if center_n is not None else "—"}</td>'
                f'<td class="text-center small fw-semibold">{center_avg}</td>'
                f'<td class="text-center small text-muted">{center_min if center_min is not None else "—"}</td>'
                f'<td class="text-center small text-muted">{center_max if center_max is not None else "—"}</td>'
                f'</tr>'
            )
        table = f"""
<table class="table table-sm report-table mb-0">
  <thead><tr><th>Grupo / Referencia</th><th class="text-center">N</th>
  <th class="text-center">Media</th><th class="text-center">Mín</th>
  <th class="text-center">Máx</th></tr></thead>
  <tbody>{rows}</tbody>
</table>"""
        return f'<div class="row g-3"><div class="col-lg-7">{chart}</div><div class="col-lg-5">{table}</div></div>'

    @api.model
    def _adhoc_panel_html(self, uid, items, name_key, center):
        """Panel genérico ad-hoc: gráfico + tabla (grupos o niveles)."""
        if not items:
            return '<p class="text-muted small py-2">Sin datos suficientes.</p>'
        canvas_id = f'amrep-adhoc-{uid}'
        labels    = [it.get(name_key, '') for it in items]
        values    = [it.get('avg', 0) for it in items]
        colors    = [_GROUP_COLORS[i % len(_GROUP_COLORS)] for i in range(len(items))]
        cfg = {
            'type': 'bar',
            'data': {'labels': labels, 'datasets': [{'data': values,
                     'backgroundColor': colors, 'borderRadius': 4,
                     'borderWidth': 1, 'borderColor': colors}]},
            'options': {'responsive': True, 'maintainAspectRatio': True,
                        'plugins': {'legend': {'display': False}},
                        'scales': {'y': {'min': 0, 'suggestedMax': 100,
                                         'title': {'display': True, 'text': 'Puntuación (0-100)'}},
                                   'x': {'ticks': {'maxRotation': 45}}}},
        }
        chart = self._canvas_with_script(canvas_id, cfg)
        col   = 'Nivel' if name_key == 'label' else 'Grupo'
        rows  = ''.join(
            f'<tr><td class="fw-medium small">{it[name_key]}</td>'
            f'<td class="text-center small">{it.get("n","")}</td>'
            f'<td class="text-center small fw-semibold">{it.get("avg","")}</td>'
            f'<td class="text-center small text-muted">{it.get("min","—")}</td>'
            f'<td class="text-center small text-muted">{it.get("max","—")}</td>'
            f'</tr>'
            for it in items
        )
        table = f"""
<table class="table table-sm report-table mb-0">
  <thead><tr><th>{col}</th><th class="text-center">N</th>
  <th class="text-center">Media</th><th class="text-center">Mín</th>
  <th class="text-center">Máx</th></tr></thead>
  <tbody>{rows}</tbody>
</table>"""
        return f'<div class="row g-3"><div class="col-lg-7">{chart}</div><div class="col-lg-5">{table}</div></div>'

    # ──────────────────────────────────────────────────────────────────────
    # CSS específico del informe
    # ──────────────────────────────────────────────────────────────────────

    @staticmethod
    def _report_styles():
        return """
<style>
.evaluation-report-page { max-width: 1200px; margin: 0 auto; }

/* ── Secciones ─────────────────────────────────────────────────── */
.report-section.card {
    border-radius: 16px;
    overflow: hidden;
    box-shadow: 0 1px 3px rgba(15,30,54,.05), 0 6px 18px rgba(15,30,54,.08);
    border: 1px solid var(--am-border,#e5e7eb);
    margin-bottom: 24px;
}
.report-section .card-header {
    padding: 16px 24px;
    border-bottom: 1px solid var(--am-border,#E0D8CF);
    background: var(--am-light,#FAF6F0);
    font-size: .9rem;
}
.report-section .card-body { padding: 20px 24px; }

/* ── Tablas ─────────────────────────────────────────────────────── */
.report-table              { font-size: .875rem; }
.report-table th {
    font-size: .72rem; font-weight: 700; text-transform: uppercase;
    letter-spacing: .05em;
    background: var(--am-light,#FAF6F0);
    color: var(--am-muted,#7A6D65);
    padding: .5rem .75rem; vertical-align: middle;
}
.report-table td           { padding: .45rem .75rem; vertical-align: middle; }
.report-table tbody tr:last-child td { border-bottom: none; }
.report-table .progress    { height: 6px; border-radius: 3px; }

/* ── Selector de vistas (pills) ─────────────────────────────────── */
.view-pills                { gap: 6px; flex-wrap: wrap; }
.view-pills .nav-link {
    font-size: .8rem; padding: .3rem .9rem;
    border-radius: 20px; border: 1.5px solid var(--am-border,#e5e7eb);
    color: var(--am-muted,#6b7280);
    background: var(--am-bg,#F5EEE6);
    transition: all .15s;
}
.view-pills .nav-link.active,
.view-pills .nav-link:hover {
    background: var(--am-primary,#1A5C52);
    border-color: var(--am-primary,#1A5C52);
    color: #fff;
}

/* ── Charts ──────────────────────────────────────────────────────── */
.chart-wrapper-sm          { position: relative; }
.chart-wrapper-donut       { position: relative; }

/* ── Resumen de centro ──────────────────────────────────────────── */
.center-view-wrapper {
    display: flex; flex-wrap: wrap; gap: 2.5rem;
    align-items: center; justify-content: center;
    padding: 2rem 1rem;
    min-height: 280px;
}
.center-kpi-block {
    display: flex; flex-direction: column; align-items: center; text-align: center;
}
.center-kpi-score {
    font-size: 3.5rem; font-weight: 700; line-height: 1;
    color: var(--am-text,#1C1814);
}
.center-pie-col { width: 300px; flex-shrink: 0; }
.center-summary-band {
    display: inline-flex; align-items: center; gap: .3rem;
    background: rgba(26,92,82,.07); border-radius: 8px;
    padding: .3rem .65rem; font-size: .875rem;
    border: 1px solid rgba(26,92,82,.18);
    color: var(--am-primary,#1A5C52);
}

/* ── Bloques de métrica ad-hoc ──────────────────────────────────── */
.metric-block + .metric-block {
    border-top: 1px solid var(--am-border,#e5e7eb); padding-top: 1.5rem;
}

/* ── Enlace de informe en cards de home ─────────────────────────── */
.eval-report-link {
    display: inline-flex; align-items: center; font-size: .78rem;
    font-weight: 600; color: var(--am-primary,#1A5C52);
    text-decoration: none; gap: .25rem;
}
.eval-report-link:hover { text-decoration: underline; }

/* ── Tabla de frecuencia de palabras (cuestionario texto abierto) ── */
.text-freq-table { font-size: .83rem; }
.text-freq-word-col { min-width: 110px; }
.text-freq-table th { white-space: nowrap; font-size: .78rem;
    background: var(--am-subtle,#f8fafc); }
.text-freq-table td { vertical-align: middle; padding: .28rem .5rem; }
</style>"""
