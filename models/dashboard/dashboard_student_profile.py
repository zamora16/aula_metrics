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
from ...utils.constants import QUERY_LIMIT_STUDENTS
from ...utils.constants import centro_surveys_enabled


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

        _centro_active = centro_surveys_enabled(self.env)

        # Métricas de cuestionarios del centro (excluye oficiales AulaMetrics)
        centro_metrics = self._get_centro_metrics(student_id) if _centro_active else None
        df_centro      = self._prepare_metrics_dataframe(centro_metrics) if centro_metrics else pd.DataFrame()

        evolution_charts      = self._generate_evolution_chartjs(df_centro, student)
        radar_chart           = self._generate_radar_chart(df_centro, student)
        kpis_html             = self._generate_student_kpis(student, df)
        alerts_html           = self._get_student_alerts_html(student_id)
        alerts_history_html   = self._get_student_alerts_history_html(student_id)
        participations_html   = self._get_participations_html(student_id)
        qualitative_html      = self._get_qualitative_responses_html(student_id)
        official_surveys_data = self._get_official_surveys_html(student_id)
        centro_surveys_html   = self._get_centro_surveys_html(student_id, student) if _centro_active else ''

        return self._build_profile_html_chartjs(
            student, role_info, kpis_html,
            evolution_charts, radar_chart,
            alerts_html, alerts_history_html,
            participations_html, qualitative_html,
            official_surveys_data=official_surveys_data,
            centro_surveys_html=centro_surveys_html,
            centro_active=_centro_active,
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
            students = Partner.search(filtered, order='name', limit=QUERY_LIMIT_STUDENTS)

        return self._build_students_list_html(students, role_info)

    # ──────────────────────────────────────────────────────────────────────
    # Data access
    # ──────────────────────────────────────────────────────────────────────

    @api.model
    def _can_access_student(self, student, role_info):
        return role_service.can_access_student(role_info, student)

    def _get_student_metrics(self, student_id):
        """Obtiene las métricas más recientes del estudiante (máx. 500 registros)."""
        return self.env['aula_metrics.metric_value'].search([
            ('student_id', '=', student_id)
        ], order='timestamp desc', limit=500)

    def _get_centro_metrics(self, student_id):
        """Métricas de encuestas del centro (excluye oficiales AulaMetrics no-adhoc). Máx. 500."""
        return self.env['aula_metrics.metric_value'].search([
            ('student_id', '=', student_id),
            '|',
            ('survey_id.is_aulametrics', '=', False),
            ('survey_id.is_adhoc', '=', True),
        ], order='timestamp desc', limit=500)

    def _get_centro_surveys_html(self, student_id, student):
        """
        Sección de cuestionarios del centro organizada por evaluación (más reciente primero).
        Muestra el valor del alumno comparado con la media de grupo y centro, por evaluación.
        Sin baremos — vista simplificada de comparativa.
        """
        MetricValue = self.env['aula_metrics.metric_value']

        records = MetricValue.search([
            ('student_id', '=', student_id),
            '|',
            ('survey_id.is_aulametrics', '=', False),
            ('survey_id.is_adhoc', '=', True),
        ], order='timestamp desc', limit=500)
        records = records.filtered(
            lambda r: (not r.value_text
                       and r.value_float is not None
                       and not (r.question_id and r.question_id.is_segmentation))
        )

        if not records:
            return ''

        group_id = student.academic_group_id.id if student.academic_group_id else None

        # Agrupar: {ev_id: {survey_id: {metric_name: mdata}}}
        evals_dict = {}
        for r in records:
            ev    = r.evaluation_id
            ev_id = ev.id if ev else 0
            if ev_id not in evals_dict:
                evals_dict[ev_id] = {
                    'id':      ev_id,
                    'name':    ev.name if ev else 'Sin evaluación',
                    'date':    ev.date_start if ev and ev.date_start else r.timestamp,
                    'surveys': {},
                }
            sid   = r.survey_id.id
            sdata = evals_dict[ev_id]['surveys']
            if sid not in sdata:
                sdata[sid] = {
                    'title':   r.survey_id.title or r.survey_id.survey_code or '',
                    'metrics': {},
                }
            mname = r.metric_name
            if mname not in sdata[sid]['metrics']:
                sdata[sid]['metrics'][mname] = {
                    'label': r.metric_label or mname.replace('_', ' ').capitalize(),
                    'value': r.value_float,
                }

        if not evals_dict:
            return ''

        ordered_evals = sorted(evals_dict.values(), key=lambda e: e['date'] or '', reverse=True)

        # Máximo observable por métrica para la barra de referencia
        all_metric_names = list({r.metric_name for r in records})
        max_by_metric = {}
        for mname in all_metric_names:
            recs = MetricValue.search([('metric_name', '=', mname)], limit=500)
            vals = [r2.value_float for r2 in recs if r2.value_float is not None]
            max_by_metric[mname] = max(vals) if vals else 1.0

        _P  = 'var(--am-primary)'
        _MU = 'var(--am-muted)'
        _BO = 'var(--am-border)'
        _SU = 'var(--am-surface)'

        sections = []
        for ev_data in ordered_evals:
            ev_name = ev_data['name']
            ev_id   = ev_data['id']
            ev_date_str = ev_data['date'].strftime('%d/%m/%Y') if ev_data['date'] else ''
            ev_date_sp  = (
                f' <span style="color:{_MU};font-weight:400;font-size:11px;">· {ev_date_str}</span>'
                if ev_date_str else ''
            )

            survey_blocks = []
            for sid, sinfo in ev_data['surveys'].items():
                metrics = sinfo['metrics']
                if not metrics:
                    continue

                rows_html = []
                for mname, mdata in metrics.items():
                    val   = mdata['value']
                    label = mdata['label']
                    max_v = max(max_by_metric.get(mname, 1.0), abs(val) if val else 0.001)

                    # Media grupo (misma evaluación, mismo grupo)
                    gm = None
                    if group_id and ev_id:
                        gm_recs = MetricValue.search([
                            ('metric_name',       '=', mname),
                            ('evaluation_id',     '=', ev_id),
                            ('academic_group_id', '=', group_id),
                        ], limit=200)
                        gm_vals = [r2.value_float for r2 in gm_recs if r2.value_float is not None]
                        gm = sum(gm_vals) / len(gm_vals) if gm_vals else None

                    # Media centro (misma evaluación, todos los alumnos)
                    cm = None
                    if ev_id:
                        cm_recs = MetricValue.search([
                            ('metric_name',   '=', mname),
                            ('evaluation_id', '=', ev_id),
                        ], limit=500)
                        cm_vals = [r2.value_float for r2 in cm_recs if r2.value_float is not None]
                        cm = sum(cm_vals) / len(cm_vals) if cm_vals else None

                    pct = min(int(val / max_v * 100), 100) if max_v > 0 else 0
                    bar = (
                        f'<div style="display:flex;align-items:center;gap:8px;min-width:120px;">'
                        f'<div style="flex:1;height:6px;background:{_BO};border-radius:3px;">'
                        f'<div style="width:{pct}%;height:100%;background:{_P};border-radius:3px;"></div>'
                        f'</div>'
                        f'<span style="font-size:13px;font-weight:700;color:{_P};white-space:nowrap;">'
                        f'{val:.1f}</span>'
                        f'</div>'
                    )
                    gm_td = (
                        f'<td class="am-td" style="font-size:12px;">{gm:.1f}</td>'
                        if gm is not None else f'<td class="am-td" style="color:{_MU};">—</td>'
                    )
                    cm_td = (
                        f'<td class="am-td" style="font-size:12px;">{cm:.1f}</td>'
                        if cm is not None else f'<td class="am-td" style="color:{_MU};">—</td>'
                    )
                    rows_html.append(
                        f'<tr>'
                        f'<td class="am-td-label">{label}</td>'
                        f'<td class="am-td" style="min-width:160px;">{bar}</td>'
                        f'{gm_td}{cm_td}'
                        f'</tr>'
                    )

                survey_blocks.append(
                    f'<div style="margin-bottom:12px;">'
                    f'<div style="font-size:12px;font-weight:600;color:{_P};text-transform:uppercase;'
                    f'letter-spacing:0.04em;margin-bottom:8px;padding-bottom:4px;'
                    f'border-bottom:1px solid {_BO};">{sinfo["title"]}</div>'
                    f'<div style="overflow-x:auto;">'
                    f'<table style="width:100%;border-collapse:collapse;background:{_SU};">'
                    f'<thead><tr style="border-bottom:2px solid {_BO};">'
                    f'<th class="am-th-label">Métrica</th>'
                    f'<th class="am-th-cell">Alumno</th>'
                    f'<th class="am-th-cell am-group-col">Grupo (media)</th>'
                    f'<th class="am-th-cell am-center-col">Centro (media)</th>'
                    f'</tr></thead>'
                    f'<tbody>{"".join(rows_html)}</tbody>'
                    f'</table></div></div>'
                )

            if not survey_blocks:
                continue

            # 1 cuestionario → ancho completo sin grid; >1 → grid 2 columnas
            if len(survey_blocks) == 1:
                inner_html  = survey_blocks[0]
                grid_class  = ''
            else:
                inner_html = ''.join(survey_blocks)
                grid_class  = 'am-survey-grid'

            sections.append(
                f'<div class="am-eval-card">'
                f'<div class="am-eval-card__header">'
                f'<i class="fa-solid fa-calendar-check" style="color:{_P};font-size:12px;"></i>'
                f'<span style="font-size:13px;font-weight:600;color:var(--am-text);">'
                f'{ev_name}{ev_date_sp}</span>'
                f'</div>'
                f'<div class="{grid_class}" style="padding:16px;">{inner_html}</div>'
                f'</div>'
            )

        return Markup('\n'.join(sections))

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
                '<a href="/aulametrics/students" class="btn-filter-action">'
                '<i class="fa-solid fa-users"></i>Lista</a>'
            ),
            'content_html':  content_html,
            'scripts_html':  Markup(''),
        }

    def _build_profile_html_chartjs(self, student, role_info, kpis_html, evolution, radar,
                                     alerts, alerts_history, participations,
                                     qualitative='', official_surveys_data=None,
                                     centro_surveys_html='', centro_active=False):
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
            'centro_surveys_html':   Markup(centro_surveys_html) if centro_surveys_html else Markup(''),
            'centro_active':         centro_active,
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
