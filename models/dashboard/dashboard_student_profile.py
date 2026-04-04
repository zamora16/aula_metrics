# -*- coding: utf-8 -*-
"""
Dashboard Student Profile — Perfil individual longitudinal de alumno.

La clase base define la API pública y los métodos de datos/orquestación.
Presentación delegada a QWeb (student_profile_templates.xml).
Secciones en:
  - dashboard_student_sections.py  (alertas, participaciones, cualitativos, lista)
  - dashboard_student_surveys.py   (cuestionarios oficiales AulaMetrics)
  - dashboard_student_charts.py    (gráficos de evolución y resumen)
"""
from odoo import models, api, fields
import pandas as pd

from markupsafe import Markup
from ...utils import dashboard_styles, dashboard_profile_styles, dashboard_helpers, role_service


def _qweb(env, template_id, values):
    result = env['ir.qweb']._render(template_id, values)
    if isinstance(result, bytes):
        return Markup(result.decode('utf-8'))
    return Markup(result)


class DashboardStudentProfile(models.TransientModel):
    _name = 'aula_metrics.dashboard.student_profile'
    _description = 'Generador de Perfil Individual de Estudiante'

    # ──────────────────────────────────────────────────────────────────────
    # API pública
    # ──────────────────────────────────────────────────────────────────────

    @api.model
    def generate_student_profile(self, student_id, role_info=None):
        """
        Genera el dashboard de perfil individual de un estudiante.

        Returns:
            dict: Valores para renderizado QWeb via 'aula_metrics.dashboard_page_base'
        """
        if role_info is None:
            role_info = {'role': 'admin', 'anonymize_students': False}

        student = self.env['res.partner'].browse(student_id)
        if not student.exists():
            return self._error_html("Estudiante no encontrado")

        if not self._can_access_student(student, role_info):
            return self._error_html("No tiene permisos para ver este perfil")

        metrics = self._get_student_metrics(student_id)
        if not metrics:
            return self._build_empty_profile(student, role_info)

        df = self._prepare_metrics_dataframe(metrics)

        # Métricas de cuestionarios del centro (excluye oficiales AulaMetrics)
        centro_metrics = self._get_centro_metrics(student_id)
        df_centro      = self._prepare_metrics_dataframe(centro_metrics) if centro_metrics else pd.DataFrame()

        evolution_charts      = self._generate_evolution_chartjs(df_centro, student)
        radar_chart           = self._generate_radar_chart(df_centro, student)
        kpis_html             = self._generate_student_kpis(student, df)
        alerts_html           = self._get_student_alerts_html(student_id)
        alerts_history_html   = self._get_student_alerts_history_html(student_id)
        participations_html   = self._get_participations_html(student_id)
        qualitative_html      = self._get_qualitative_responses_html(student_id)
        official_surveys_data = self._get_official_surveys_html(student_id)

        return self._build_profile_html_chartjs(
            student, role_info, kpis_html,
            evolution_charts, radar_chart,
            alerts_html, alerts_history_html,
            participations_html, qualitative_html,
            official_surveys_data=official_surveys_data,
        )

    @api.model
    def generate_students_list(self, role_info=None):
        """
        Genera una lista HTML de estudiantes accesibles según el rol.

        Returns:
            dict: Valores para renderizado QWeb via 'aula_metrics.dashboard_page_base'
        """
        if role_info is None:
            role_info = {'role': 'admin'}

        Partner  = self.env['res.partner']
        domain   = [('is_student', '=', True)]
        filtered = role_service.apply_group_filter(domain, role_info, field='academic_group_id')
        if filtered is None:
            students = Partner.browse([])
        else:
            students = Partner.search(filtered, order='name')

        return self._build_students_list_html(students, role_info)

    # ──────────────────────────────────────────────────────────────────────
    # Data access
    # ──────────────────────────────────────────────────────────────────────

    @api.model
    def _can_access_student(self, student, role_info):
        return role_service.can_access_student(role_info, student)

    def _get_student_metrics(self, student_id):
        """Obtiene todas las métricas del estudiante ordenadas por fecha."""
        return self.env['aula_metrics.metric_value'].search([
            ('student_id', '=', student_id)
        ], order='timestamp desc')

    def _get_centro_metrics(self, student_id):
        """Métricas de encuestas del centro (excluye oficiales AulaMetrics no-adhoc)."""
        return self.env['aula_metrics.metric_value'].search([
            ('student_id', '=', student_id),
            '|',
            ('survey_id.is_aulametrics', '=', False),
            ('survey_id.is_adhoc', '=', True),
        ], order='timestamp desc')

    def _prepare_metrics_dataframe(self, metrics):
        """Construye el DataFrame de métricas del alumno para análisis longitudinal."""
        if not metrics:
            return pd.DataFrame()
        return pd.DataFrame(dashboard_helpers.metric_values_to_records(metrics))

    # ──────────────────────────────────────────────────────────────────────
    # KPIs
    # ──────────────────────────────────────────────────────────────────────

    def _generate_student_kpis(self, student, df):
        """Genera la banda de 4 KPIs via QWeb."""
        total_evals  = df['evaluation_id'].nunique() if not df.empty else 0
        group_name   = student.academic_group_id.name if student.academic_group_id else 'Sin grupo'
        alerts_count = self.env['aula_metrics.alert'].search_count([
            ('student_id', '=', student.id),
            ('status',     '=', 'active'),
        ])

        participations    = self.env['aula_metrics.participation'].search([('student_id', '=', student.id)])
        total_parts       = len(participations)
        completed_parts   = len(participations.filtered(lambda p: p.state == 'completed'))
        participation_pct = f'{round(completed_parts / total_parts * 100)}%' if total_parts else '—'

        kpis = [
            {'label': 'Evaluaciones',  'value': total_evals,        'value_cls': 'kpi-value',                  'description': 'Completadas'},
            {'label': 'Participación', 'value': participation_pct,  'value_cls': 'kpi-value',                  'description': 'Encuestas respondidas'},
            {'label': 'Grupo',         'value': group_name,         'value_cls': 'kpi-value kpi-value--group', 'description': 'Académico'},
            {'label': 'Alertas',       'value': alerts_count,       'value_cls': 'kpi-value kpi-value--danger' if alerts_count > 0 else 'kpi-value', 'description': 'Activas'},
        ]

        return _qweb(self.env, 'aula_metrics.student_kpis_strip', {'kpis': kpis})

    # ──────────────────────────────────────────────────────────────────────
    # Page builders
    # ──────────────────────────────────────────────────────────────────────

    def _build_empty_profile(self, student, role_info):
        """Contexto para perfil sin métricas — layout via QWeb."""
        group_name          = student.academic_group_id.name if student.academic_group_id else 'Sin grupo'
        alerts_html         = self._get_student_alerts_html(student.id)
        alerts_history_html = self._get_student_alerts_history_html(student.id)

        content_html = _qweb(self.env, 'aula_metrics.student_empty_profile_content', {
            'group_name':         group_name,
            'alerts_html':        alerts_html,
            'alerts_history_html': alerts_history_html,
        })

        return {
            'page_title':           f'Perfil de {student.name}',
            'css_styles':           Markup(dashboard_styles.get_common_styles() + self._profile_styles_chartjs()),
            'head_extra':           Markup(''),
            'role_info':            role_info,
            'active_section':       'profiles',
            'topbar_title':         student.name,
            'topbar_subtitle':      Markup(
                f'<i class="fa-solid fa-user me-2"></i>{group_name} · {fields.Date.today().strftime("%d/%m/%Y")}'
            ),
            'topbar_extra_actions': Markup(
                '<a href="/aulametrics/students" class="btn btn-outline-secondary btn-sm">'
                '<i class="fa-solid fa-users"></i> Lista</a>'
            ),
            'content_html':  content_html,
            'scripts_html':  Markup(''),
        }

    def _build_profile_html_chartjs(self, student, role_info, kpis_html, evolution, radar,
                                     alerts, alerts_history, participations,
                                     qualitative='', official_surveys_data=None):
        """
        Contexto completo para el perfil — layout y JS via QWeb template.
        """
        if official_surveys_data is None:
            official_surveys_data = {
                'timeline_html': '', 'evolution_html': '',
                'has_surveys': False, 'student_id': student.id,
            }

        group_name     = student.academic_group_id.name if student.academic_group_id else 'Sin grupo'
        timeline_html  = official_surveys_data.get('timeline_html', '')
        evol_ofic_html = official_surveys_data.get('evolution_html', '')
        has_surveys    = official_surveys_data.get('has_surveys', False)

        chart_libs = Markup(
            '<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>\n'
            '<script src="https://cdn.jsdelivr.net/npm/chartjs-adapter-date-fns@3.0.0/dist/chartjs-adapter-date-fns.bundle.min.js"></script>'
        )

        content_html = _qweb(self.env, 'aula_metrics.student_profile_content', {
            'student_name':          student.name,
            'student_id':            student.id,
            'group_name':            group_name,
            'today_str':             fields.Date.today().strftime('%d/%m/%Y'),
            'kpis_html':             Markup(kpis_html) if kpis_html else Markup(''),
            'timeline_html':         Markup(timeline_html) if timeline_html else Markup(''),
            'has_surveys':           has_surveys,
            'participations_html':   Markup(participations) if participations else Markup(''),
            'radar_html':            Markup(radar) if radar else Markup(''),
            'evol_ofic_html':        Markup(evol_ofic_html) if evol_ofic_html else Markup(''),
            'evolution_charts_html': Markup(evolution) if evolution else Markup(''),
            'qualitative_html':      Markup(qualitative) if qualitative else Markup(''),
            'alerts_html':           Markup(alerts) if alerts else Markup(''),
            'alerts_history_html':   Markup(alerts_history) if alerts_history else Markup(''),
        })

        return {
            'page_title':           f'Perfil de {student.name}',
            'css_styles':           Markup(dashboard_styles.get_common_styles() + self._profile_styles_chartjs()),
            'head_extra':           chart_libs,
            'role_info':            role_info,
            'active_section':       'profiles',
            'topbar_title':         student.name,
            'topbar_subtitle':      Markup(
                f'<i class="fa-solid fa-user me-2"></i>{group_name} · {fields.Date.today().strftime("%d/%m/%Y")}'
            ),
            'topbar_extra_actions': Markup(''),
            'content_html':         content_html,
            'scripts_html':         Markup(''),
        }

    def _profile_styles_chartjs(self):
        return dashboard_profile_styles.get_profile_styles()

    def _error_html(self, message):
        raise ValueError(message)
