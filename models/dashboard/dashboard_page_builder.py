# -*- coding: utf-8 -*-
"""
Dashboard Page Builder - Compila el contexto de datos para los templates QWeb.

Las plantillas se encuentran en views/dashboard_main_templates.xml.
Este módulo NO genera HTML — sólo prepara los dicts de datos que QWeb consume.
"""
import logging
from markupsafe import Markup
from odoo import models, fields
from ...utils import dashboard_styles, dashboard_helpers, role_service

_logger = logging.getLogger(__name__)


class DashboardChartsBuilder(models.TransientModel):
    _inherit = 'aula_metrics.dashboard.charts'

    # ------------------------------------------------------------------
    # KPI data
    # ------------------------------------------------------------------

    def _generate_kpis(self, df, filters, role_info):
        """Retorna un dict con los contadores para la plantilla dashboard_kpis."""
        eval_ids = df['evaluation_id'].dropna().unique().tolist()
        if eval_ids:
            evals = self.env['aula_metrics.evaluation'].browse([int(i) for i in eval_ids])
            rates = [ev.participation_rate for ev in evals if ev.total_students > 0]
            avg_participation = round(sum(rates) / len(rates)) if rates else 0
        else:
            avg_participation = 0
        return {
            'kpi_students':      int(df['student_id'].nunique()),
            'kpi_groups':        int(df['group_id'].nunique()),
            'kpi_evals':         int(df['evaluation_id'].nunique()),
            'kpi_participation': avg_participation,
        }

    # ------------------------------------------------------------------
    # Home section data
    # ------------------------------------------------------------------

    # Labels y orden de visualización por estado de evaluación
    _EVAL_STATE_META = {
        'active':    {'label': 'Activa',     'css': 'state-active'},
        'scheduled': {'label': 'Programada', 'css': 'state-scheduled'},
        'closed':    {'label': 'Cerrada',    'css': 'state-closed'},
        'draft':     {'label': 'Borrador',   'css': 'state-draft'},
        'cancelled': {'label': 'Cancelada',  'css': 'state-cancelled'},
    }
    _EVAL_STATE_ORDER = ['active', 'scheduled', 'draft', 'closed', 'cancelled']

    def _get_home_data(self, role_info):
        """
        Extrae los datos estructurados para dashboard_home_section.

        Muestra TODAS las evaluaciones (no solo activas) con sus estados,
        y KPIs agregados: conteos por estado, participación media global,
        participación media de activas, y total de alertas activas.

        Returns:
            dict con claves home_evaluations, home_kpi_active,
            home_kpi_scheduled, home_kpi_closed, home_kpi_avg_all,
            home_kpi_avg_active, home_kpi_alerts
        """
        all_evals = self._get_all_evaluations(role_info)

        # ── Conteos por estado ────────────────────────────────────────
        counts = {'active': 0, 'scheduled': 0, 'closed': 0, 'draft': 0}
        for ev in all_evals:
            state = ev['state']
            if state in counts:
                counts[state] += 1

        # ── Participación media (excluye borradores y canceladas) ─────
        measurable = [e for e in all_evals if e['state'] in ('active', 'closed') and e['total_students'] > 0]
        active_only = [e for e in all_evals if e['state'] == 'active' and e['total_students'] > 0]

        avg_all = (
            sum(e['participation_rate'] for e in measurable) / len(measurable)
            if measurable else None
        )
        avg_active = (
            sum(e['participation_rate'] for e in active_only) / len(active_only)
            if active_only else None
        )

        # ── Alertas activas (todos los roles, sin datos individuales) ─
        total_alerts = self.env['aula_metrics.alert'].search_count(
            [('status', '=', 'active')]
        )

        # ── Formatear cards de evaluaciones ──────────────────────────
        state_meta = self._EVAL_STATE_META
        state_order = {s: i for i, s in enumerate(self._EVAL_STATE_ORDER)}
        sorted_evals = sorted(all_evals, key=lambda e: (state_order.get(e['state'], 99), -(e['date_start'].timestamp() if e['date_start'] else 0)))

        formatted = []
        for ev in sorted_evals:
            rate = ev['participation_rate']
            pct  = round(rate)
            meta = state_meta.get(ev['state'], {'label': ev['state'], 'css': 'state-draft'})
            formatted.append({
                'id':                   ev['id'],
                'name':                 ev['name'],
                'state':                ev['state'],
                'state_label':          meta['label'],
                'state_css':            meta['css'],
                'date_range':           dashboard_helpers.format_date_range(
                                            ev['date_start'], ev['date_end']
                                        ),
                'groups':               ev['groups'],
                'surveys':              ev['surveys'],
                'completed_students':   ev['completed_students'],
                'total_students':       ev['total_students'],
                'participation_pct':    pct,
                'participation_class':  'high' if rate >= 80 else ('medium' if rate >= 50 else 'low'),
            })

        return {
            'home_evaluations':    formatted,
            'home_kpi_active':     counts['active'],
            'home_kpi_scheduled':  counts['scheduled'],
            'home_kpi_closed':     counts['closed'],
            'home_kpi_avg_all':    dashboard_helpers.format_participation_rate(avg_all) if avg_all is not None else None,
            'home_kpi_avg_active': dashboard_helpers.format_participation_rate(avg_active) if avg_active is not None else None,
            'home_kpi_alerts':     total_alerts,
        }

    def _get_all_evaluations(self, role_info):
        """Todas las evaluaciones (excl. canceladas) filtradas por rol."""
        domain = role_service.apply_group_filter(
            [('state', 'not in', ['cancelled'])],
            role_info,
            field='academic_group_ids',
        )
        if domain is None:
            return []

        total_groups = self.env['aula_metrics.academic_group'].search_count([])

        result = []
        for ev in self.env['aula_metrics.evaluation'].search(domain, order='date_start desc'):
            group_names = ev.academic_group_ids.mapped('name')
            if total_groups and len(group_names) >= total_groups:
                groups_label = 'Todos los grupos'
            else:
                groups_label = ', '.join(group_names) or '—'
            result.append({
                'id':                ev.id,
                'name':              ev.name,
                'state':             ev.state,
                'date_start':        ev.date_start,
                'date_end':          ev.date_end,
                'participation_rate': ev.participation_rate,
                'total_students':    ev.total_students,
                'completed_students': ev.completed_students,
                'groups':            groups_label,
                'surveys':           ', '.join(ev.survey_ids.mapped('title')) or '—',
            })
        return result

    # ------------------------------------------------------------------
    # Page context builders  →  used by generate_dashboard()
    # ------------------------------------------------------------------

    def _build_html_empty(self, evaluations, filters, role_info):
        """Contexto para dashboard_main cuando no hay datos de métricas."""
        date_str = dashboard_helpers.format_date(fields.Date.today())
        return {
            'page_title':           'Dashboard de Métricas',
            'head_extra':           Markup(''),
            'css_styles':           Markup(dashboard_styles.get_common_styles()),
            'role_info':            role_info,
            'active_section':       'home',
            'topbar_title':         'Inicio',
            'topbar_subtitle':      Markup(
                f'<i class="fa-regular fa-calendar me-2"></i>{date_str}'
            ),
            'topbar_extra_actions': Markup(''),
            'available_evaluations': evaluations,
            'selected_evals':       filters.get('evaluation_ids', []),
            'kpi_students':         None,
            'kpi_groups':           None,
            'kpi_evals':            None,
            'kpi_participation':    None,
            'charts':               [],
            **self._get_home_data(role_info),
        }

    def _build_html(self, evaluations, filters, role_info, kpi_values, charts):
        """Contexto para dashboard_main con datos completos."""
        date_str = dashboard_helpers.format_date(fields.Date.today())
        chart_libs = Markup(
            '<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>\n'
            '<script src="https://cdn.jsdelivr.net/npm/chartjs-adapter-date-fns@3.0.0/dist/chartjs-adapter-date-fns.bundle.min.js"></script>'
        )
        return {
            'page_title':           'Dashboard de Métricas',
            'head_extra':           chart_libs,
            'css_styles':           Markup(dashboard_styles.get_common_styles()),
            'role_info':            role_info,
            'active_section':       'home',
            'topbar_title':         'Inicio',
            'topbar_subtitle':      Markup(
                f'<i class="fa-regular fa-calendar me-2"></i>{date_str}'
            ),
            'topbar_extra_actions': Markup(''),
            'available_evaluations': evaluations,
            'selected_evals':       filters.get('evaluation_ids', []),
            **kpi_values,
            'charts':               [Markup(c) for c in charts if c],
            **self._get_home_data(role_info),
        }
