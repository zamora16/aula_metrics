# -*- coding: utf-8 -*-
"""
Dashboard Student Profile — Perfil individual longitudinal de alumno.

La clase base define la API pública y los métodos de datos/orquestación.
Los métodos de renderizado están divididos en:
  - dashboard_student_sections.py  (alertas, participaciones, cualitativos, lista)
  - dashboard_student_surveys.py   (cuestionarios oficiales AulaMetrics)
  - dashboard_student_charts.py    (gráficos de evolución y resumen)
"""
from odoo import models, api, fields
import pandas as pd

from markupsafe import Markup
from ...utils import dashboard_styles, dashboard_helpers, palette, role_service


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
        kpis                  = self._generate_student_kpis(student, df)
        alerts_html           = self._get_student_alerts_html(student_id)
        alerts_history_html   = self._get_student_alerts_history_html(student_id)
        participations_html   = self._get_participations_html(student_id)
        qualitative_html      = self._get_qualitative_responses_html(student_id)
        official_surveys_html = self._get_official_surveys_html(student_id)

        return self._build_profile_html_chartjs(
            student, role_info, kpis,
            evolution_charts, radar_chart,
            alerts_html, alerts_history_html,
            participations_html, qualitative_html,
            official_surveys=official_surveys_html,
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
        """Genera las 4 tarjetas KPI del estudiante."""
        total_evals   = df['evaluation_id'].nunique() if not df.empty else 0
        total_metrics = len(df) if not df.empty else 0
        group_name    = student.academic_group_id.name if student.academic_group_id else 'Sin grupo'
        alerts_count  = self.env['aula_metrics.alert'].search_count([
            ('student_id', '=', student.id),
            ('status',     '=', 'active'),
        ])

        kpis = [
            f'<div class="kpi-card"><div class="kpi-label">Evaluaciones</div><div class="kpi-value">{total_evals}</div><div class="kpi-description">Completadas</div></div>',
            f'<div class="kpi-card"><div class="kpi-label">Métricas</div><div class="kpi-value">{total_metrics}</div><div class="kpi-description">Registradas</div></div>',
            f'<div class="kpi-card"><div class="kpi-label">Grupo</div><div class="kpi-value" style="font-size:22px;font-weight:600;">{group_name}</div><div class="kpi-description">Académico</div></div>',
            f'<div class="kpi-card"><div class="kpi-label">Alertas</div><div class="kpi-value" style="color:{"" if alerts_count == 0 else palette.UI_DANGER};">{alerts_count}</div><div class="kpi-description">Activas</div></div>',
        ]
        return '\n'.join(kpis)

    # ──────────────────────────────────────────────────────────────────────
    # Page builders
    # ──────────────────────────────────────────────────────────────────────

    def _build_empty_profile(self, student, role_info):
        """Contexto para perfil sin métricas."""
        group_name        = student.academic_group_id.name if student.academic_group_id else 'Sin grupo'
        alerts_html       = self._get_student_alerts_html(student.id)
        alerts_history    = self._get_student_alerts_history_html(student.id)

        content_html = f"""
        <div class="container-fluid">
            <div class="card" style="text-align:center;padding:60px 40px;">
                <i class="fa-solid fa-chart-line" style="font-size:80px;color:var(--am-light);margin-bottom:24px;"></i>
                <h3 style="color:var(--am-muted);margin-bottom:12px;">Sin datos de métricas disponibles</h3>
                <p style="color:var(--am-muted);font-size:15px;">Complete una evaluación para comenzar a ver datos.</p>
            </div>
            <div class="row mt-4">
                <div class="col-12">
                    <div class="card">
                        <div class="card-header"><h5 class="card-title">Alertas Activas</h5></div>
                        <div class="card-body">
                            {alerts_html}
                            <div class="mt-3">
                                <button class="btn btn-outline-secondary btn-sm w-100" type="button"
                                        data-bs-toggle="collapse" data-bs-target="#alertsHistory">
                                    <i class="fa-solid fa-clock-rotate-left me-2"></i>Ver Historial de Alertas
                                </button>
                                <div class="collapse mt-3" id="alertsHistory">
                                    <hr>
                                    <h6 class="text-muted mb-3">Historial de Alertas Resueltas/Descartadas</h6>
                                    {alerts_history}
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>"""

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
            'content_html':         Markup(content_html),
            'scripts_html':         Markup(''),
        }

    def _build_profile_html_chartjs(self, student, role_info, kpis, evolution, radar,
                                     alerts, alerts_history, participations,
                                     qualitative='', official_surveys=''):
        """Contexto completo para el perfil con Chart.js."""
        group_name = student.academic_group_id.name if student.academic_group_id else 'Sin grupo'

        has_official    = bool(official_surveys and official_surveys.strip())
        active_oficial  = 'show active' if has_official else ''
        active_centro   = ''            if has_official else 'show active'
        tab_oficial_cls = 'nav-link active' if has_official else 'nav-link'
        tab_centro_cls  = 'nav-link'        if has_official else 'nav-link active'

        oficial_content = official_surveys if has_official else """
            <div class="text-center py-5">
                <i class="fa-solid fa-clipboard-list fa-3x mb-3" style="color:var(--am-border);"></i>
                <p class="text-muted mb-0">Este alumno aún no tiene resultados de cuestionarios oficiales.</p>
            </div>"""

        centro_content = (radar or '') + (evolution or '')
        if not centro_content.strip():
            centro_content = """
            <div class="text-center py-5">
                <i class="fa-solid fa-chart-bar fa-3x mb-3" style="color:var(--am-border);"></i>
                <p class="text-muted mb-0">No hay métricas de cuestionarios del centro registradas.</p>
            </div>"""

        chart_libs = (
            '<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>\n'
            '<script src="https://cdn.jsdelivr.net/npm/chartjs-adapter-date-fns@3.0.0/dist/chartjs-adapter-date-fns.bundle.min.js"></script>'
        )

        content_html = f"""
        <div class="container-fluid">
            <div class="kpi-grid">{kpis}</div>

            <div class="card mb-4">
                <div class="card-header" style="padding-bottom:0;border-bottom:none;">
                    <ul class="nav nav-tabs" style="border-bottom:none;margin-bottom:-1px;gap:4px;">
                        <li class="nav-item">
                            <a class="{tab_oficial_cls}" data-bs-toggle="tab" href="#tab-oficial"
                               style="font-size:13px;font-weight:600;">
                                <i class="fa-solid fa-clipboard-check me-1"></i>Cuestionarios Oficiales
                            </a>
                        </li>
                        <li class="nav-item">
                            <a class="{tab_centro_cls}" data-bs-toggle="tab" href="#tab-centro"
                               style="font-size:13px;font-weight:600;">
                                <i class="fa-solid fa-school me-1"></i>Cuestionarios del Centro
                            </a>
                        </li>
                    </ul>
                </div>
                <div class="card-body" style="padding-top:20px;">
                    <div class="tab-content">
                        <div class="tab-pane fade {active_oficial}" id="tab-oficial">{oficial_content}</div>
                        <div class="tab-pane fade {active_centro}"  id="tab-centro">{centro_content}</div>
                    </div>
                </div>
            </div>

            <div class="row">
                <div class="col-12">
                    <div class="card">
                        <div class="card-header">
                            <h5 class="card-title">Respuestas Cualitativas</h5>
                            <p class="card-subtitle">Textos y comentarios abiertos</p>
                        </div>
                        <div class="card-body">{qualitative}</div>
                    </div>
                </div>
            </div>

            <div class="row">
                <div class="col-lg-6">
                    <div class="card">
                        <div class="card-header">
                            <h5 class="card-title">Alertas Activas</h5>
                            <p class="card-subtitle">Puntos de atención identificados</p>
                        </div>
                        <div class="card-body">
                            {alerts}
                            <div class="mt-3">
                                <button class="btn btn-outline-secondary btn-sm w-100" type="button"
                                        data-bs-toggle="collapse" data-bs-target="#alertsHistory">
                                    <i class="fa-solid fa-clock-rotate-left me-2"></i>Ver Historial de Alertas
                                </button>
                                <div class="collapse mt-3" id="alertsHistory">
                                    <hr>
                                    <h6 class="text-muted mb-3">Historial de Alertas Resueltas/Descartadas</h6>
                                    {alerts_history}
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                <div class="col-lg-6">
                    <div class="card">
                        <div class="card-header">
                            <h5 class="card-title">Histórico de Participación</h5>
                            <p class="card-subtitle">Encuestas completadas</p>
                        </div>
                        <div class="card-body">{participations}</div>
                    </div>
                </div>
            </div>
        </div>"""

        return {
            'page_title':           f'Perfil de {student.name}',
            'css_styles':           Markup(dashboard_styles.get_common_styles() + self._profile_styles_chartjs()),
            'head_extra':           Markup(chart_libs),
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
            'content_html':         Markup(content_html),
            'scripts_html':         Markup(''),
        }

    def _profile_styles_chartjs(self):
        """Estilos CSS del perfil de alumno."""
        return """
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
            * { margin:0; padding:0; box-sizing:border-box; }
            body { font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
                   background-color:var(--am-bg);color:var(--am-text);line-height:1.6;font-size:15px;padding-bottom:80px; }
            .kpi-grid { display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:20px;margin-bottom:32px; }
            .kpi-card { background:var(--am-surface);border:1px solid var(--am-border);border-radius:10px;padding:24px;transition:all 0.2s ease; }
            .kpi-card:hover { transform:translateY(-2px);box-shadow:0 4px 12px rgba(0,0,0,0.08); }
            .kpi-label { font-size:13px;font-weight:500;color:var(--am-muted);text-transform:uppercase;letter-spacing:0.5px;margin-bottom:8px; }
            .kpi-value { font-size:36px;font-weight:700;color:var(--am-text);line-height:1;margin-bottom:4px; }
            .kpi-description { font-size:13px;color:var(--am-muted);font-weight:400; }
            .card { background:var(--am-surface);border:1px solid var(--am-border);border-radius:10px;margin-bottom:24px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,0.04); }
            .card-header { padding:20px 24px;border-bottom:1px solid var(--am-light);background:var(--am-surface); }
            .card-title { font-size:18px;font-weight:600;color:var(--am-text);margin:0; }
            .card-title-sm { font-size:15px;font-weight:600;color:var(--am-text);margin:0; }
            .card-subtitle { font-size:13px;color:var(--am-muted);margin:4px 0 0;font-weight:400; }
            .card-body { padding:24px; }
            .col-lg-6 { flex:0 0 50%;max-width:50%;padding:0 12px; }
            @media (max-width:991px) { .col-lg-6 { flex:0 0 100%;max-width:100%; } }
            table { width:100%;border-collapse:collapse;font-size:14px; }
            thead { background:var(--am-bg);border-bottom:1px solid var(--am-border); }
            th { padding:12px 16px;text-align:left;font-weight:600;color:var(--am-muted);font-size:13px;text-transform:uppercase;letter-spacing:0.5px; }
            td { padding:14px 16px;border-bottom:1px solid var(--am-light);color:var(--am-text); }
            tr:last-child td { border-bottom:none; }
            tbody tr:hover { background:var(--am-bg); }
        </style>"""

    def _error_html(self, message):
        raise ValueError(message)
