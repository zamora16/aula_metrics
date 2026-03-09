# -*- coding: utf-8 -*-
"""
Dashboard Page Builder - Compila el contexto de datos para los templates QWeb.

Las plantillas se encuentran en views/dashboard_main_templates.xml.
Este módulo NO genera HTML — sólo prepara los dicts de datos que QWeb consume.
"""
from markupsafe import Markup
from odoo import models, fields
from ...utils import dashboard_styles, dashboard_helpers, role_service
from ...utils.constants import ROLE_ADMIN, ROLE_COUNSELOR


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

    def _get_home_data(self, role_info):
        """
        Extrae los datos estructurados para dashboard_home_section.
        Reemplaza a _home_section(), _build_evaluation_cards() y _build_quick_stats().

        Returns:
            dict con: home_evaluations, home_total_evaluations,
                      home_avg_participation, home_total_alerts
        """
        try:
            active_evals = self._get_active_evaluations(role_info)
            total = len(active_evals)
            avg = (
                sum(e['participation_rate'] for e in active_evals) / total
                if active_evals else 0.0
            )
            role = (role_info or {}).get('role', '')
            total_alerts = (
                self.env['aula_metrics.alert'].search_count([('status', '=', 'active')])
                if role in [ROLE_ADMIN, ROLE_COUNSELOR] else 0
            )

            formatted = []
            for ev in active_evals:
                rate = ev['participation_rate']
                formatted.append({
                    'name': ev['name'],
                    'date_range': dashboard_helpers.format_date_range(
                        ev['date_start'], ev['date_end']
                    ),
                    'participation_display': dashboard_helpers.format_participation_rate(rate),
                    'participation_class': (
                        'high' if rate >= 80 else ('medium' if rate >= 50 else 'low')
                    ),
                    'completed_students': ev['completed_students'],
                    'total_students': ev['total_students'],
                    'alert_count': ev.get('alert_count', 0),
                })

            return {
                'home_evaluations': formatted,
                'home_total_evaluations': total,
                'home_avg_participation': dashboard_helpers.format_participation_rate(avg),
                'home_total_alerts': total_alerts,
            }
        except Exception:
            return {
                'home_evaluations': [],
                'home_total_evaluations': 0,
                'home_avg_participation': '0%',
                'home_total_alerts': 0,
            }

    def _get_active_evaluations(self, role_info):
        """Evaluaciones activas filtradas por rol, con conteo de alertas para counselor/admin."""
        domain = role_service.apply_group_filter(
            [('state', '=', 'active')],
            role_info,
            field='academic_group_ids',
        )
        if domain is None:
            return []

        result = []
        for ev in self.env['aula_metrics.evaluation'].search(domain, order='date_start desc'):
            entry = {
                'id':                  ev.id,
                'name':                ev.name,
                'date_start':          ev.date_start,
                'date_end':            ev.date_end,
                'participation_rate':  ev.participation_rate,
                'total_students':      ev.total_students,
                'completed_students':  ev.completed_students,
            }
            if (role_info or {}).get('role') in [ROLE_ADMIN, ROLE_COUNSELOR]:
                entry['alert_count'] = self.env['aula_metrics.alert'].search_count([
                    ('status', '=', 'active'),
                    '|',
                    ('participation_id.evaluation_id', '=', ev.id),
                    ('qualitative_response_id.evaluation_id', '=', ev.id),
                ])
            result.append(entry)
        return result

    # ------------------------------------------------------------------
    # Page context builders  →  used by generate_dashboard()
    # ------------------------------------------------------------------

    def _build_html_empty(self, metrics, groups, evaluations, filters, role_info):
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

    def _build_html(self, metrics, groups, evaluations, filters, role_info,
                    kpi_values, charts, segmentation_vars):
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
