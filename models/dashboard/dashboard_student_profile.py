# -*- coding: utf-8 -*-
"""
Dashboard Student Profile - Perfil individual longitudinal de alumno
"""
from odoo import models, api, fields
import pandas as pd
import json

# Importar utilidades compartidas del dashboard
from markupsafe import Markup
from ...utils import dashboard_styles, dashboard_helpers, palette, role_service
from ...utils.constants import ROLE_ADMIN, ROLE_COUNSELOR, ROLE_MANAGEMENT, ROLE_TUTOR

class DashboardStudentProfile(models.TransientModel):
    _name = 'aula_metrics.dashboard.student_profile'
    _description = 'Generador de Perfil Individual de Estudiante'

    @api.model
    def generate_student_profile(self, student_id, role_info=None):
        """
        Genera el dashboard de perfil individual de un estudiante con Chart.js.
        
        Args:
            student_id (int): ID del estudiante (res.partner)
            role_info (dict): Información del rol del usuario
        
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

        # Tab "Cuestionarios del Centro": excluir métricas de cuestionarios oficiales AulaMetrics
        centro_metrics = self._get_centro_metrics(student_id)
        df_centro = self._prepare_metrics_dataframe(centro_metrics) if centro_metrics else pd.DataFrame()

        evolution_charts = self._generate_evolution_chartjs(df_centro, student)
        radar_chart = self._generate_radar_chart(df_centro, student)
        kpis = self._generate_student_kpis(student, df)
        alerts_html = self._get_student_alerts_html(student_id)
        alerts_history_html = self._get_student_alerts_history_html(student_id)
        participations_html = self._get_participations_html(student_id)
        qualitative_html = self._get_qualitative_responses_html(student_id)
        official_surveys_html = self._get_official_surveys_html(student_id)

        return self._build_profile_html_chartjs(
            student, role_info, kpis,
            evolution_charts, radar_chart, alerts_html, alerts_history_html, participations_html, qualitative_html,
            official_surveys=official_surveys_html
        )

    @api.model
    def generate_students_list(self, role_info=None):
        """
        Genera una lista HTML de estudiantes accesibles según el rol.
        
        Args:
            role_info (dict): Información del rol del usuario
        
        Returns:
            dict: Valores para renderizado QWeb via 'aula_metrics.dashboard_page_base'
        """
        if role_info is None:
            role_info = {'role': 'admin'}
        
        # Obtener estudiantes según rol
        Partner = self.env['res.partner']
        domain = [('is_student', '=', True)]
        
        # Tutores solo ven sus grupos (None = sin grupos asignados → vacío)
        filtered_domain = role_service.apply_group_filter(domain, role_info, field='academic_group_id')
        if filtered_domain is None:
            students = Partner.browse([])
        else:
            students = Partner.search(filtered_domain, order='name')
        
        # Generar HTML
        return self._build_students_list_html(students, role_info)

    @api.model
    def _can_access_student(self, student, role_info):
        """Verifica si el usuario tiene permisos para ver este estudiante."""
        return role_service.can_access_student(role_info, student)

    def _get_student_metrics(self, student_id):
        """Obtiene todas las métricas del estudiante ordenadas por fecha."""
        MetricValue = self.env['aula_metrics.metric_value']
        return MetricValue.search([
            ('student_id', '=', student_id)
        ], order='timestamp desc')

    def _get_centro_metrics(self, student_id):
        """
        Obtiene solo las métricas procedentes de encuestas del centro
        (excluye cuestionarios oficiales AulaMetrics no-adhoc).
        """
        MetricValue = self.env['aula_metrics.metric_value']
        return MetricValue.search([
            ('student_id', '=', student_id),
            '|',
            ('survey_id.is_aulametrics', '=', False),
            ('survey_id.is_adhoc', '=', True),
        ], order='timestamp desc')

    def _prepare_metrics_dataframe(self, metrics):
        """
        Construye el DataFrame de las métricas de un alumno para análisis
        longitudinal.

        La conversión se delega en dashboard_helpers.metric_values_to_records.
        El DataFrame resultante contiene todas las columnas disponibles;
        los métodos consumidores proyectan las que necesitan.
        """
        if not metrics:
            return pd.DataFrame()
        return pd.DataFrame(dashboard_helpers.metric_values_to_records(metrics))

    def _generate_student_kpis(self, student, df):
        """Genera KPIs del estudiante - diseño profesional."""
        kpis = []
        
        # Total de evaluaciones completadas
        total_evals = df['evaluation_id'].nunique() if not df.empty else 0
        kpis.append(f"""
        <div class="kpi-card">
            <div class="kpi-label">Evaluaciones</div>
            <div class="kpi-value">{total_evals}</div>
            <div class="kpi-description">Completadas</div>
        </div>
        """)
        
        # Total de métricas registradas
        total_metrics = len(df) if not df.empty else 0
        kpis.append(f"""
        <div class="kpi-card">
            <div class="kpi-label">Métricas</div>
            <div class="kpi-value">{total_metrics}</div>
            <div class="kpi-description">Registradas</div>
        </div>
        """)
        
        # Grupo académico
        group_name = student.academic_group_id.name if student.academic_group_id else 'Sin grupo'
        kpis.append(f"""
        <div class="kpi-card">
            <div class="kpi-label">Grupo</div>
            <div class="kpi-value" style="font-size: 22px; font-weight: 600;">{group_name}</div>
            <div class="kpi-description">Académico</div>
        </div>
        """)
        
        # Alertas activas
        alerts_count = self.env['aula_metrics.alert'].search_count([
            ('student_id', '=', student.id),
            ('status', '=', 'active')
        ])
        kpis.append(f"""
        <div class="kpi-card">
            <div class="kpi-label">Alertas</div>
            <div class="kpi-value" style="color: {palette.UI_DANGER if alerts_count > 0 else palette.UI_SUCCESS};">{alerts_count}</div>
            <div class="kpi-description">Activas</div>
        </div>
        """)
        
        return '\n'.join(kpis)

    def _get_student_alerts_html(self, student_id):
        """Obtiene HTML con las alertas activas del estudiante."""
        Alert = self.env['aula_metrics.alert']
        alerts = Alert.search([
            ('student_id', '=', student_id),
            ('status', '=', 'active')
        ], order='severity desc, alert_date desc')
        
        if not alerts:
            return '<div class="alert alert-success"><i class="fa-solid fa-check-circle me-2"></i>No hay alertas activas para este estudiante</div>'
        
        html = '<div class="alerts-container">'
        for alert in alerts:
            severity_classes = {
                'low': 'info',
                'moderate': 'warning',
                'high': 'danger'
            }
            severity_labels = {
                'low': 'Baja',
                'moderate': 'Moderada',
                'high': 'Alta'
            }
            badge_class = severity_classes.get(alert.severity, 'secondary')
            severity_label = severity_labels.get(alert.severity, alert.severity)
            
            html += f"""
            <div class="alert alert-{badge_class} d-flex justify-content-between align-items-start">
                <div>
                    <h6>{alert.name}</h6>
                    <p class="mb-1">{alert.message or ''}</p>
                    <small class="text-muted">Creada: {alert.alert_date.strftime('%d/%m/%Y %H:%M')}</small>
                </div>
                <span class="badge bg-{badge_class}">{severity_label}</span>
            </div>
            """
        
        html += '</div>'
        return html

    def _get_student_alerts_history_html(self, student_id):
        """Obtiene HTML con el historial de alertas resueltas/descartadas del estudiante."""
        Alert = self.env['aula_metrics.alert']
        alerts = Alert.search([
            ('student_id', '=', student_id),
            ('status', 'in', ['resolved', 'dismissed'])
        ], order='resolution_date desc, alert_date desc', limit=20)
        
        if not alerts:
            return '<div class="alert alert-light">No hay historial de alertas</div>'
        
        html = '<div class="alerts-history-container">'
        for alert in alerts:
            severity_classes = {
                'low': 'info',
                'moderate': 'warning',
                'high': 'danger'
            }
            severity_labels = {
                'low': 'Baja',
                'moderate': 'Moderada',
                'high': 'Alta'
            }
            status_labels = {
                'resolved': 'Resuelta',
                'dismissed': 'Descartada'
            }
            status_colors = {
                'resolved': 'success',
                'dismissed': 'secondary'
            }
            
            badge_class = severity_classes.get(alert.severity, 'secondary')
            severity_label = severity_labels.get(alert.severity, alert.severity)
            status_label = status_labels.get(alert.status, alert.status)
            status_color = status_colors.get(alert.status, 'secondary')
            
            resolution_info = ''
            if alert.resolution_date:
                resolution_info = f'<small class="text-muted d-block">Resuelta: {alert.resolution_date.strftime("%d/%m/%Y %H:%M")}</small>'
            if alert.resolution_action:
                resolution_info += f'<small class="text-muted d-block mt-1"><strong>Acción:</strong> {alert.resolution_action}</small>'
            
            html += f"""
            <div class="alert alert-light border-start border-{badge_class} border-3 mb-2">
                <div class="d-flex justify-content-between align-items-start">
                    <div class="flex-grow-1">
                        <h6 class="mb-1">{alert.name} <span class="badge bg-{status_color} ms-2">{status_label}</span></h6>
                        <p class="mb-1 text-muted small">{alert.message or ''}</p>
                        <small class="text-muted">Creada: {alert.alert_date.strftime('%d/%m/%Y %H:%M')}</small>
                        {resolution_info}
                    </div>
                    <span class="badge bg-{badge_class} ms-2">{severity_label}</span>
                </div>
            </div>
            """
        
        html += '</div>'
        return html

    def _get_participations_html(self, student_id):
        """Obtiene HTML con el histórico de participaciones."""
        Participation = self.env['aula_metrics.participation']
        participations = Participation.search([
            ('student_id', '=', student_id)
        ], order='completed_at desc', limit=20)
        
        if not participations:
            return '<p class="text-muted">No hay participaciones registradas</p>'
        
        html = """
        <div class="table-responsive">
            <table class="table table-striped table-hover">
                <thead>
                    <tr>
                        <th>Fecha</th>
                        <th>Evaluación</th>
                        <th>Encuesta</th>
                        <th>Estado</th>
                    </tr>
                </thead>
                <tbody>
        """
        
        for p in participations:
            state_badges = {
                'pending': '<span class="badge bg-warning">Pendiente</span>',
                'completed': '<span class="badge bg-success">Completada</span>',
                'expired': '<span class="badge bg-secondary">Expirada</span>'
            }
            state_html = state_badges.get(p.state, p.state)
            completed_date = p.completed_at.strftime('%d/%m/%Y') if p.completed_at else 'N/A'
            
            # Las evaluaciones pueden tener múltiples encuestas
            surveys_names = ', '.join(p.evaluation_id.survey_ids.mapped('title')) if p.evaluation_id.survey_ids else 'N/A'
            
            html += f"""
                <tr>
                    <td>{completed_date}</td>
                    <td>{p.evaluation_id.name}</td>
                    <td>{surveys_names}</td>
                    <td>{state_html}</td>
                </tr>
            """
        
        html += """
                </tbody>
            </table>
        </div>
        """
        return html

    def _get_qualitative_responses_html(self, student_id):
        """Obtiene HTML con las respuestas cualitativas del estudiante."""
        QualitativeResponse = self.env['aula_metrics.qualitative_response']
        responses = QualitativeResponse.search([
            ('student_id', '=', student_id)
        ], order='response_date desc', limit=20)
        
        if not responses:
            return '<p class="text-muted">No hay respuestas cualitativas registradas</p>'
        
        html = '<div class="qualitative-responses">'
        
        for resp in responses:
            alert_class = 'alert-warning' if resp.has_alert_keywords else ''
            # Usar clases de badge para heredar tema centralizado
            alert_badge = '<span class="badge bg-danger">Alerta</span>' if resp.has_alert_keywords else '<span class="badge bg-success"><i class="fa-solid fa-check"></i></span>'
            
            # Información de la pregunta
            question_title = resp.question_id.title if resp.question_id else 'Pregunta sin título'
            evaluation_name = resp.evaluation_id.name if resp.evaluation_id else 'Sin evaluación'
            date_str = resp.response_date.strftime('%d/%m/%Y') if resp.response_date else 'Sin fecha'
            
            # Detectar keywords encontradas
            keywords_html = ''
            if resp.has_alert_keywords and resp.detected_keyword_ids:
                keywords_list = ', '.join([f'<strong>{kw.keyword}</strong>' for kw in resp.detected_keyword_ids])
                if keywords_list:
                    keywords_html = f'<div class="mt-2"><small class="text-danger">Palabras detectadas: {keywords_list}</small></div>'
            
            html += f"""
            <div class="card mb-3 {alert_class}">
                <div class="card-header d-flex justify-content-between align-items-start">
                    <div>
                        <h6 class="mb-1">{question_title}</h6>
                        <small class="text-muted">{evaluation_name} · {date_str} · {resp.word_count} palabras</small>
                    </div>
                    {alert_badge}
                </div>
                <div class="card-body">
                    <p class="mb-0">{resp.response_text}</p>
                    {keywords_html}
                </div>
            </div>
            """
        
        html += '</div>'
        return html

    # ────────────────────────────────────────────────────────────────────────
    # Cuestionarios Oficiales — acordeón por resultado
    # ────────────────────────────────────────────────────────────────────────

    def _get_official_surveys_html(self, student_id):
        """
        Sección de cuestionarios oficiales: lista de filas compactas ordenadas
        por fecha. Cada fila muestra [cuestionario · fecha · puntuación · badge]
        y al pulsar se expande inline con el desglose completo por sub-escalas.
        No hay navegación fuera del perfil.

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

        # Pre-calcular scale_maxes y meta (etiqueta + orden) por survey_id una sola vez
        BaremoRange = self.env['aula_metrics.survey_baremo_range']
        maxes_cache = {}   # {survey_id: {scale_name: max_value}}
        meta_cache  = {}   # {survey_id: {scale_name: {'label': str, 'order': int}}}
        seen_sids = list(dict.fromkeys(r.survey_id.id for r in results))
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

        # Agrupar por cuestionario manteniendo orden de aparición
        groups = {}    # {survey_id: {'title': str, 'results': [...]}}
        for r in results:
            sid = r.survey_id.id
            if sid not in groups:
                groups[sid] = {
                    'title': r.survey_id.title or '—',
                    'results': [],
                }
            groups[sid]['results'].append(r)

        # Construir grupos de acordeón
        groups_html = []
        for sid in seen_sids:
            g = groups[sid]
            scale_maxes = maxes_cache[sid]

            # Comparativa grupo / centro (se inyecta dentro de cada fila)
            ctx = self._get_survey_result_context(sid, student_id)

            # Una fila acordeón por cada resultado, con marcadores de media
            scale_meta = meta_cache[sid]
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
                <div class="official-survey-list">
                    {rows_html}
                </div>
            </div>""")

        # Devuelve sólo el cuerpo con los grupos — el tab panel hace de contenedor
        return '\n'.join(groups_html)

    def _build_survey_result_row(self, result, scale_maxes, context=None, scale_meta=None):
        """
        Fila acordeón para un resultado de cuestionario oficial.

        Cabecera: fecha · evaluación · puntuación global · badge de severidad.
        Cuerpo expandible: barra horizontal por sub-escala coloreada según severidad,
        con marcadores de media de grupo (gris) y centro (verde) superpuestos.
        Valor mostrado como score/max. Leyenda compacta arriba.
        """
        rid = result.id
        collapse_id = f'sr-detail-{rid}'

        # ── Metadatos de cabecera ─────────────────────────────────────────
        date_str  = result.completed_at.strftime('%d/%m/%Y') if result.completed_at else '—'
        age_str   = f'{result.age_at_completion} a.' if result.age_at_completion else ''
        eval_name = result.evaluation_id.name if result.evaluation_id else ''

        sev         = min(result.baremo_severity, 2)

        # Obtener mapeo dinámico de severidad para este cuestionario
        BaremoRange = self.env['aula_metrics.survey_baremo_range']
        severity_mapping = BaremoRange.get_severity_mapping(result.survey_id.id)
        sev_info = severity_mapping.get(sev, {})
        bar_color = sev_info.get('color', '#ccc')
        badge_style = f"background:{sev_info.get('bg_color', '#fff')};color:{sev_info.get('color', '#000')}"
        global_label = result.baremo_label or sev_info.get('label', f'Severity {sev}')

        meta_parts = [date_str]
        if age_str:
            meta_parts.append(age_str)
        if eval_name:
            meta_parts.append(eval_name)
        meta_str = ' · '.join(meta_parts)

        # ── Contexto comparativo ──────────────────────────────────────────
        has_ctx = bool(context and (context.get('group_count') or context.get('center_count')))
        g_means = context['group_means']  if has_ctx else {}
        c_means = context['center_means'] if has_ctx else {}

        # ── Leyenda de marcadores (solo si hay contexto con datos de grupo/centro) ──
        legend_parts = []
        if has_ctx and context.get('group_count'):
            n = context['group_count']
            legend_parts.append(
                f'<span style="display:inline-block;width:2px;height:12px;background:#94a3b8;'
                f'border-radius:1px;vertical-align:middle;"></span>'
                f'&nbsp;Media grupo ({n})'
            )
        if has_ctx and context.get('center_count'):
            n = context['center_count']
            legend_parts.append(
                f'<span style="display:inline-block;width:2px;height:12px;background:{palette.UI_SUCCESS};'
                f'border-radius:1px;vertical-align:middle;"></span>'
                f'&nbsp;Media centro ({n})'
            )
        legend_html = (
            ('<div class="d-flex gap-3 mb-3" style="font-size:10px;color:var(--am-muted);">'
             + '&emsp;'.join(legend_parts)
             + '</div>')
            if legend_parts else ''
        )

        # ── Contenido expandido: sub-escalas ─────────────────────────────
        scale_scores = result.get_scale_scores()
        scale_bars_html = ''

        if scale_scores:
            _meta = scale_meta or {}
            has_total = 'total' in scale_scores
            non_total = [s for s in scale_scores if s != 'total']
            non_total.sort(key=lambda s: _meta.get(s, {}).get('order', 99))
            ordered_scales = non_total + (['total'] if has_total else [])

            bars = []
            for scale_name in ordered_scales:
                scale_data   = scale_scores[scale_name]
                score        = scale_data.get('score', 0) if isinstance(scale_data, dict) else float(scale_data)
                s_sev        = min(scale_data.get('severity', 0) if isinstance(scale_data, dict) else 0, 2)
                sev_info_s = severity_mapping.get(s_sev, {})
                val_color = sev_info_s.get('color', '#ccc')
                scale_max    = max(scale_maxes.get(scale_name, 10), 1)
                display_name = (_meta.get(scale_name) or {}).get('label') or scale_name.replace('_', ' ').capitalize()
                is_total     = scale_name == 'total' and has_total and len(ordered_scales) > 1

                def pct(v, mx=scale_max):
                    return min(v / mx * 100, 100)

                # ── Barra del alumno (color según severidad) ──────────────
                s_pct    = pct(score)
                bar_html = (f'<div title="{display_name}: {score:.0f}/{scale_max:.0f}" '
                            f'style="position:absolute;left:0;top:50%;transform:translateY(-50%);'
                            f'width:{s_pct:.1f}%;height:9px;background:{val_color};'
                            f'border-radius:0 2px 2px 0;z-index:2;"></div>')

                # ── Marcadores grupo / centro ─────────────────────────────
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

                top_border = 'border-top:1px solid var(--am-border);padding-top:8px;margin-top:4px;' \
                             if is_total else ''

                bars.append(f"""
                <div class="d-flex align-items-center gap-2 mb-2" style="{top_border}">
                    <small style="width:145px;min-width:115px;flex-shrink:0;
                                  color:var(--am-muted);font-size:11px;">{display_name}</small>
                    <div style="flex:1;position:relative;height:22px;border-radius:3px;
                                overflow:hidden;background:var(--am-border);">
                        {bar_html}
                        {g_mk}
                        {c_mk}
                    </div>
                    <small style="width:44px;text-align:right;font-weight:700;
                                  font-size:11px;color:{val_color};flex-shrink:0;"
                           title="{display_name}">{score:.0f}<span style="font-weight:400;color:var(--am-muted);">/{scale_max:.0f}</span></small>
                </div>""")
            scale_bars_html = '\n'.join(bars)

        # ── Descripción global del baremo ─────────────────────────────────
        desc_html = ''
        if result.baremo_description:
            desc_html = f'<p style="font-size:13px;color:var(--am-muted);margin-bottom:14px;">{result.baremo_description}</p>'

        # ── Notas del orientador ──────────────────────────────────────────
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

        # ── Row HTML ─────────────────────────────────────────────────────
        return f"""
        <div style="border:1px solid var(--am-border);border-radius:8px;margin-bottom:6px;overflow:hidden;">

            <!-- Cabecera: wrapper flex externo sin toggle -->
            <div class="d-flex align-items-center"
                 style="border-left:4px solid {bar_color};">

                <!-- Zona clicable para colapsar (ocupa todo el espacio menos el botón) -->
                <div class="d-flex align-items-center justify-content-between px-3 py-2"
                     role="button"
                     data-bs-toggle="collapse"
                     data-bs-target="#{collapse_id}"
                     aria-expanded="false"
                     aria-controls="{collapse_id}"
                     style="flex:1;min-width:0;cursor:pointer;user-select:none;transition:background 0.15s;"
                     onmouseover="this.style.background='var(--am-light)'"
                     onmouseout="this.style.background=''">

                    <!-- Fecha y meta -->
                    <div style="min-width:0;flex:1;">
                        <span style="font-size:14px;font-weight:500;color:var(--am-text);">{meta_str}</span>
                    </div>

                    <!-- Puntuación global + badge + flecha -->
                    <div class="d-flex align-items-center gap-3 ms-3 flex-shrink-0">
                        <span style="font-size:22px;font-weight:700;line-height:1;color:{bar_color};">{result.raw_score:.0f}<span style="font-weight:400;color:var(--am-muted);"><t t-if="scale_maxes.get('total')">/{scale_maxes['total']:.0f}</t></span></span>
                        <span class="badge" style="{badge_style};font-size:11px;padding:3px 10px;">{global_label}</span>
                        <i class="fa-solid fa-chevron-down"
                           id="chevron-{rid}"
                           style="color:var(--am-muted);font-size:11px;transition:transform 0.25s;"></i>
                    </div>
                </div>

                <!-- Botón informe: FUERA del div de colapso -->
                <a href="/report/pdf/aula_metrics.report_survey_result_document/{rid}"
                   target="_blank"
                   title="Generar informe PDF"
                   style="display:inline-flex;align-items:center;gap:4px;padding:3px 10px;
                          margin-right:10px;flex-shrink:0;
                          border:1px solid var(--am-border);border-radius:5px;
                          font-size:10px;color:var(--am-muted);text-decoration:none;
                          background:var(--am-surface);line-height:1.4;white-space:nowrap;"
                   onmouseover="this.style.borderColor='var(--am-primary)';this.style.color='var(--am-primary)';"
                   onmouseout="this.style.borderColor='var(--am-border)';this.style.color='var(--am-muted)';"
                ><i class="fa-solid fa-file-pdf" style="font-size:10px;"></i>&nbsp;Informe</a>

            </div>

            <!-- Cuerpo expandible -->
            <div class="collapse" id="{collapse_id}">
                <div style="padding:16px 20px;border-top:1px solid var(--am-border);background:var(--am-surface);">
                    {desc_html}
                    {legend_html}
                    {scale_bars_html}
                    {notes_html}
                </div>
            </div>
        </div>
        <script>
        (function() {{
            var el  = document.getElementById('{collapse_id}');
            var chv = document.getElementById('chevron-{rid}');
            if (el && chv) {{
                el.addEventListener('show.bs.collapse',  function() {{ chv.style.transform = 'rotate(180deg)'; }});
                el.addEventListener('hide.bs.collapse',  function() {{ chv.style.transform = 'rotate(0deg)'; }});
            }}
        }})();
        </script>"""

    def _get_survey_result_context(self, survey_id, student_id):
        """
        Calcula medias por escala de otros alumnos para el mismo cuestionario.
        Retorna medias del grupo del alumno y del centro completo.
        """
        SurveyResult = self.env['aula_metrics.survey_result']
        student = self.env['res.partner'].browse(student_id)
        group_id = student.academic_group_id.id if student.academic_group_id else None

        all_others = SurveyResult.search([
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

    def _build_empty_profile(self, student, role_info):
        """Contexto para perfil sin métricas (template dashboard_page_base)."""
        group_name = student.academic_group_id.name if student.academic_group_id else 'Sin grupo'

        # Obtener alertas aunque no haya métricas
        alerts_html = self._get_student_alerts_html(student.id)
        alerts_history_html = self._get_student_alerts_history_html(student.id)

        content_html = f"""
                        <div class="container-fluid">
                            <div class="card" style="text-align: center; padding: 60px 40px;">
                                <i class="fa-solid fa-chart-line" style="font-size: 80px; color: var(--am-light); margin-bottom: 24px;"></i>
                                <h3 style="color: var(--am-muted); margin-bottom: 12px;">Sin datos de métricas disponibles</h3>
                                <p style="color: var(--am-muted); font-size: 15px;">Este estudiante aún no tiene métricas registradas. Complete una evaluación para comenzar a ver datos.</p>
                            </div>

                            <div class="row mt-4">
                                <div class="col-12">
                                    <div class="card">
                                        <div class="card-header">
                                            <h5 class="card-title">Alertas Activas</h5>
                                            <p class="card-subtitle">Puntos de atención identificados</p>
                                        </div>
                                        <div class="card-body">
                                            {alerts_html}

                                            <div class="mt-3">
                                                <button class="btn btn-outline-secondary btn-sm w-100" type="button" data-bs-toggle="collapse" data-bs-target="#alertsHistory" aria-expanded="false" aria-controls="alertsHistory">
                                                    <i class="fa-solid fa-clock-rotate-left me-2"></i>Ver Historial de Alertas
                                                </button>
                                                <div class="collapse mt-3" id="alertsHistory">
                                                    <hr>
                                                    <h6 class="text-muted mb-3">Historial de Alertas Resueltas/Descartadas</h6>
                                                    {alerts_history_html}
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

    def _build_students_list_html(self, students, role_info):
        """Construye los datos de la lista de estudiantes para el template QWeb."""
        # Obtener grupos únicos para el filtro
        groups = {}
        for student in students:
            if student.academic_group_id:
                groups[student.academic_group_id.id] = student.academic_group_id.name
        
        # Generar opciones del select de grupos
        group_options = '<option value="">Todos los grupos</option>'
        for group_id, group_name in sorted(groups.items(), key=lambda x: x[1]):
            group_options += f'<option value="{group_id}">{group_name}</option>'
        
        # Generar filas de tabla
        students_rows = ''
        if not students:
            students_rows = '''
            <tr>
                <td colspan="5" class="text-center text-muted py-5">
                    <i class="fa-solid fa-user-slash fa-3x mb-3 d-block"></i>
                    No hay estudiantes disponibles
                </td>
            </tr>
            '''
        else:
            for student in students:
                group_name = student.academic_group_id.name if student.academic_group_id else 'Sin grupo'
                group_id = student.academic_group_id.id if student.academic_group_id else 0
                email = student.email or 'N/A'
                
                # Contar métricas y alertas
                metrics_count = self.env['aula_metrics.metric_value'].search_count([
                    ('student_id', '=', student.id)
                ])
                alerts_count = self.env['aula_metrics.alert'].search_count([
                    ('student_id', '=', student.id),
                    ('status', '=', 'active')
                ])
                
                # Badge de alertas
                alerts_badge = ''
                if alerts_count > 0:
                    alerts_badge = f'<span class="badge bg-danger">{alerts_count} alerta(s)</span>'
                else:
                    alerts_badge = '<span class="badge bg-success"><i class="fa-solid fa-check"></i></span>'
                
                students_rows += f'''
                <tr data-group-id="{group_id}">
                    <td>
                        <div class="d-flex align-items-center">
                            <div class="student-avatar me-3">
                                <i class="fa-solid fa-user-circle fa-2x text-primary"></i>
                            </div>
                            <div>
                                <div class="fw-bold">{student.name}</div>
                                <small class="text-muted">{email}</small>
                            </div>
                        </div>
                    </td>
                    <td>{group_name}</td>
                    <td class="text-center">{metrics_count}</td>
                    <td>{alerts_badge}</td>
                    <td class="text-end">
                        <a href="/aulametrics/student/{student.id}" class="btn btn-sm btn-outline-primary">
                            <i class="fa-solid fa-chart-line me-1"></i> Ver Perfil
                        </a>
                    </td>
                </tr>
                '''
        
        list_page_styles = dashboard_styles.get_common_styles() + """
        <style>
            .card { border-radius: 12px; border: 1px solid var(--am-border); box-shadow: 0 1px 3px rgba(0,0,0,0.05); background: var(--am-surface); }
            .card-header { background: var(--am-surface); border-bottom: 1px solid var(--am-border); font-weight: 600; padding: 1.25rem 1.5rem; }
            .table { margin-bottom: 0; }
            .table thead th { background: var(--am-bg); font-weight: 600; border-bottom: 2px solid var(--am-border); padding: 1rem; }
            .table tbody td { padding: 1rem; vertical-align: middle; }
            .table tbody tr:hover { background: var(--am-bg); }

            .search-box { margin-bottom: 1.5rem; }
            .search-box input { border-radius: 8px; padding: 0.75rem 1rem; border: 1px solid var(--am-border); }
            .search-box input:focus { border-color: var(--am-primary); box-shadow: 0 0 0 3px rgba(var(--am-primary-rgb), 0.1); }

            .filters-bar { margin-bottom: 1.5rem; display: flex; gap: 1rem; align-items: center; }
            .filters-bar select { border-radius: 8px; padding: 0.75rem 1rem; border: 1px solid var(--am-border); }
            .filters-bar select:focus { border-color: var(--am-primary); box-shadow: 0 0 0 3px rgba(var(--am-primary-rgb), 0.1); }
        </style>"""



        content_html = f"""
                        <div class="container-fluid">
                            <div class="filters-bar">
                                <div class="flex-grow-1">
                                    <input type="text" id="searchInput" class="form-control" placeholder="Buscar por nombre...">
                                </div>
                                <div style="min-width: 250px;">
                                    <select id="groupFilter" class="form-select">
                                        {group_options}
                                    </select>
                                </div>
                            </div>

                            <div class="card">
                                <div class="card-header d-flex justify-content-between align-items-center">
                                    <span><i class="fa-solid fa-list me-2"></i>Estudiantes ({len(students)})</span>
                                </div>
                                <div class="card-body p-0">
                                    <div class="table-responsive">
                                        <table class="table table-hover" id="studentsTable">
                                            <thead>
                                                <tr>
                                                    <th>Estudiante</th>
                                                    <th>Grupo</th>
                                                    <th class="text-center">Métricas</th>
                                                    <th>Estado</th>
                                                    <th class="text-end">Acciones</th>
                                                </tr>
                                            </thead>
                                            <tbody>
                                                {students_rows}
                                            </tbody>
                                        </table>
                                    </div>
                                </div>
                            </div>
                        </div>"""

        scripts_html = """
            <script>
                function applyFilters() {
                    const searchTerm = document.getElementById('searchInput').value.toLowerCase();
                    const selectedGroup = document.getElementById('groupFilter').value;
                    const rows = document.querySelectorAll('#studentsTable tbody tr');

                    let visibleCount = 0;
                    rows.forEach(row => {
                        const text = row.textContent.toLowerCase();
                        const groupId = row.getAttribute('data-group-id');
                        const matchesSearch = !searchTerm || text.includes(searchTerm);
                        const matchesGroup = !selectedGroup || groupId === selectedGroup;
                        if (matchesSearch && matchesGroup) {
                            row.style.display = '';
                            visibleCount++;
                        } else {
                            row.style.display = 'none';
                        }
                    });

                    const header = document.querySelector('.card-header span');
                    if (header) {
                        const totalCount = rows.length;
                        if (visibleCount === totalCount) {
                            header.innerHTML = '<i class="fa-solid fa-list me-2"></i>Estudiantes (' + totalCount + ')';
                        } else {
                            header.innerHTML = '<i class="fa-solid fa-list me-2"></i>Estudiantes (' + visibleCount + ' de ' + totalCount + ')';
                        }
                    }
                }

                document.getElementById('searchInput').addEventListener('keyup', applyFilters);
                document.getElementById('groupFilter').addEventListener('change', applyFilters);
            </script>"""

        return {
            'page_title':           'Perfiles de Alumnos',
            'css_styles':           Markup(list_page_styles),
            'head_extra':           Markup('<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet"/>'),
            'role_info':            role_info,
            'active_section':       'profiles',
            'topbar_title':         'Perfiles de Alumnos',
            'topbar_subtitle':      Markup(
                f'<i class="fa-solid fa-users me-2"></i>Listado de estudiantes · {fields.Date.today().strftime("%d/%m/%Y")}'
            ),
            'topbar_extra_actions': Markup(''),
            'content_html':         Markup(content_html),
            'scripts_html':         Markup(scripts_html),
        }

    def _generate_evolution_chartjs(self, df, student):
        """Gráficos individuales con contexto del grupo - estilo profesional."""
        if df.empty:
            return ''
        
        df_numeric = df[df['metric_type'] == 'numeric'].copy()
        if df_numeric.empty:
            return ''
        
        # Obtener datos del grupo para contexto
        group_data = self._get_group_context_data(student, df_numeric)
        
        charts_html = ''
        
        for idx, metric in enumerate(df_numeric['metric_label'].unique()[:4]):
            df_metric = df_numeric[df_numeric['metric_label'] == metric].sort_values('timestamp')
            metric_name = df_metric.iloc[0]['metric_name']
            
            # Solo mostrar si hay 2+ mediciones
            if len(df_metric) < 2:
                continue
            
            labels = [row['timestamp'].strftime('%d/%m') for _, row in df_metric.iterrows()]
            values = [float(row['value']) for _, row in df_metric.iterrows()]
            
            # Calcular porcentaje de cambio entre primera y última medición
            first_value = values[0]
            last_value = values[-1]
            percent_change = ((last_value - first_value) / first_value * 100) if first_value != 0 else 0
            change_icon = '↑' if percent_change > 0 else '↓' if percent_change < 0 else '→'
            change_color = palette.UI_SUCCESS if percent_change > 0 else palette.UI_DANGER if percent_change < 0 else palette.UI_MUTED
            change_text = f"<span style='color: {change_color}; font-weight: 600;'>{change_icon} {abs(percent_change):.1f}%</span>"
            
            # Color consistente para las barras del estudiante (usar color principal del tema)
            student_color = palette.UI_PRIMARY
            
            # Obtener media del grupo en los mismos periodos si disponible
            group_means = []
            if metric_name in group_data:
                for timestamp in df_metric['timestamp']:
                    # Buscar mediciones del grupo cercanas a esta fecha (±7 días)
                    group_vals = group_data[metric_name].get('values', [])
                    matching = [v for t, v in group_vals if abs((t - timestamp).days) <= 7]
                    if matching:
                        group_means.append(sum(matching) / len(matching))
                    else:
                        group_means.append(None)
            
            chart_id = f'evolution_{student.id}_{idx}'

            # Eje Y dinámico: usar el máximo real de los datos de esta métrica
            all_chart_vals = values + [v for v in group_means if v is not None]
            y_suggested_max = round(max(all_chart_vals) * 1.20, 1) if all_chart_vals else 100

            # Crear datasets: las barras representan al estudiante (etiquetadas con su nombre); líneas para media grupo/centro
            datasets = [
                {
                    'label': student.name,
                    'data': values,
                    'backgroundColor': student_color,
                    'borderColor': student_color,
                    'borderRadius': 6,
                    'borderSkipped': False,
                    'order': 2
                }
            ]

            # Agregar línea de media del grupo si hay datos
            if group_means and any(v is not None for v in group_means):
                datasets.append({
                    'label': 'Media grupo',
                    'data': group_means,
                    'type': 'line',
                    'borderColor': palette.UI_MUTED,
                    'backgroundColor': 'transparent',
                    'borderWidth': 2,
                    'borderDash': [5, 5],
                    'pointRadius': 4,
                    'pointBackgroundColor': palette.UI_MUTED,
                    'pointBorderColor': '#ffffff',
                    'pointBorderWidth': 2,
                    'order': 1,
                    'tension': 0.3
                })



            charts_html += f'''
            <div class="col-lg-6 mb-4">
                <div class="card">
                    <div class="card-header">
                        <h6 class="card-title-sm">{metric}</h6>
                        <p style="font-size: 11px; color: var(--am-muted); margin: 4px 0 0 0;">
                            Evolución con contexto del grupo · Cambio: {change_text}
                        </p>
                    </div>
                    <div class="card-body">
                        <canvas id="{chart_id}" height="180"></canvas>
                    </div>
                </div>
            </div>
            
            <script>
            new Chart(document.getElementById('{chart_id}'), {{
                type: 'bar',
                data: {{
                    labels: {json.dumps(labels)},
                    datasets: {json.dumps(datasets)}
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: true,
                    plugins: {{
                        legend: {{
                            display: true,
                            position: 'bottom',
                            labels: {{
                                usePointStyle: true,
                                padding: 12,
                                font: {{
                                    size: 11,
                                    family: "'Inter', sans-serif"
                                }},
                                color: getComputedStyle(document.documentElement).getPropertyValue('--am-muted').trim()
                            }}
                        }},
                        tooltip: {{
                            backgroundColor: getComputedStyle(document.documentElement).getPropertyValue('--am-primary-darker').trim(),
                            padding: 12,
                            cornerRadius: 6,
                            titleFont: {{
                                family: "'Inter', sans-serif",
                                size: 12,
                                weight: '600'
                            }},
                            bodyFont: {{
                                family: "'Inter', sans-serif",
                                size: 12
                            }},
                            callbacks: {{
                                label: function(context) {{
                                    let label = context.dataset.label || '';
                                    if (label) {{
                                        label += ': ';
                                    }}
                                    if (context.parsed.y !== null) {{
                                        label += context.parsed.y.toFixed(1) + ' pts';
                                    }}
                                    return label;
                                }}
                            }}
                        }}
                    }},
                    scales: {{
                        x: {{
                            grid: {{
                                display: false,
                                drawBorder: false
                            }},
                            ticks: {{
                                font: {{
                                    size: 11,
                                    family: "'Inter', sans-serif"
                                }},
                                color: getComputedStyle(document.documentElement).getPropertyValue('--am-muted').trim()
                            }}
                        }},
                        y: {{
                            beginAtZero: true,
                            suggestedMax: {y_suggested_max},
                            grid: {{
                                color: getComputedStyle(document.documentElement).getPropertyValue('--am-light').trim(),
                                drawBorder: false
                            }},
                            ticks: {{
                                font: {{
                                    size: 11,
                                    family: "'Inter', sans-serif"
                                }},
                                color: getComputedStyle(document.documentElement).getPropertyValue('--am-muted').trim()
                            }}
                        }}
                    }},
                    animation: {{
                        duration: 600,
                        easing: 'easeInOutCubic'
                    }}
                }}
            }});
            </script>
            '''
        
        if charts_html:
            return f'<div class="row">{charts_html}</div>'
        return ''

    def _get_group_context_data(self, student, df_student):
        """Obtiene datos del grupo para contextualizar el perfil individual."""
        if not student.academic_group_id:
            return {}
        
        group_id = student.academic_group_id.id
        group_data = {}
        
        # Para cada métrica del estudiante, obtener valores del grupo
        for metric_name in df_student['metric_name'].unique():
            MetricValue = self.env['aula_metrics.metric_value']
            group_metrics = MetricValue.search([
                ('metric_name', '=', metric_name),
                ('academic_group_id', '=', group_id)
            ])
            
            if group_metrics:
                values_with_ts = [
                    (m.timestamp, m.value_float) 
                    for m in group_metrics 
                    if m.value_float is not None
                ]
                
                if values_with_ts:
                    group_data[metric_name] = {
                        'values': values_with_ts,
                        'mean': sum(v for _, v in values_with_ts) / len(values_with_ts)
                    }
        
        return group_data
    
    def _get_center_context_data(self, student, df_student):
        """Obtiene datos del centro completo para contextualizar el perfil."""
        center_data = {}
        
        # Para cada métrica del estudiante, obtener valores de todo el centro
        for metric_name in df_student['metric_name'].unique():
            MetricValue = self.env['aula_metrics.metric_value']
            center_metrics = MetricValue.search([
                ('metric_name', '=', metric_name)
            ])
            
            if center_metrics:
                values = [m.value_float for m in center_metrics if m.value_float is not None]
                
                if values:
                    center_data[metric_name] = {
                        'mean': sum(values) / len(values)
                    }
        
        return center_data
    
    def _generate_radar_chart(self, df, student):
        """
        Resumen de Métricas — reemplaza el radar chart.

        Muestra cada métrica numérica como una fila horizontal con:
        - Nombre de la métrica y fecha de última medición
        - Barra normalizada (0–100 % del rango observado en el centro) con:
            · Barra rellena hasta el valor del alumno (color semáforo si hay umbral)
            · Marcador vertical gris = media del grupo
            · Marcador vertical verde = media del centro
        - Valor bruto destacado a la derecha + flecha de tendencia

        La normalización es independiente por métrica, por lo que métricas con
        rangos completamente diferentes son siempre comparables entre sí.
        """
        if df.empty:
            return ''

        df_numeric = df[df['metric_type'] == 'numeric'].copy()
        if df_numeric.empty:
            return ''

        group_data  = self._get_group_context_data(student, df_numeric)
        center_data = self._get_center_context_data(student, df_numeric)
        MetricValue = self.env['aula_metrics.metric_value']

        rows_html = []
        metrics_shown = 0

        for metric_name in df_numeric['metric_name'].unique():
            df_m = df_numeric[df_numeric['metric_name'] == metric_name].sort_values('timestamp')
            if df_m.empty:
                continue

            label     = df_m.iloc[-1]['metric_label']
            last_val  = float(df_m.iloc[-1]['value'])
            last_date = df_m.iloc[-1]['timestamp'].strftime('%d/%m/%Y')

            # ── Tendencia vs medición anterior ──────────────────────────
            if len(df_m) >= 2:
                prev_val = float(df_m.iloc[-2]['value'])
                diff = last_val - prev_val
                if abs(diff) < 0.5:
                    trend_icon  = '<i class="fa-solid fa-minus" style="color:var(--am-muted);font-size:10px;"></i>'
                    trend_color = 'var(--am-muted)'
                elif diff > 0:
                    trend_icon  = '<i class="fa-solid fa-arrow-up" style="color:var(--am-primary);font-size:10px;"></i>'
                    trend_color = palette.UI_PRIMARY
                else:
                    trend_icon  = '<i class="fa-solid fa-arrow-down" style="color:var(--am-danger, #ef4444);font-size:10px;"></i>'
                    trend_color = palette.UI_DANGER
            else:
                trend_icon  = ''
                trend_color = 'var(--am-muted)'

            # ── Rango de normalización: máximo observado en el centro ────
            all_vals = MetricValue.search_read(
                [('metric_name', '=', metric_name), ('value_float', '!=', False)],
                ['value_float']
            )
            all_floats = [r['value_float'] for r in all_vals if r['value_float'] is not None]
            observed_max = max(all_floats) if all_floats else max(last_val, 1)
            if observed_max <= 0:
                observed_max = 1

            def to_pct(v):
                return min(int(v / observed_max * 100), 100)

            student_pct = to_pct(last_val)

            bar_color = palette.UI_PRIMARY

            # ── Marcadores de grupo y centro ─────────────────────────────
            group_marker_html  = ''
            center_marker_html = ''
            group_tooltip = ''
            center_tooltip = ''

            if metric_name in group_data:
                gm = group_data[metric_name]['mean']
                gp = to_pct(gm)
                group_tooltip = f'Media grupo: {gm:.1f}'
                group_marker_html = f'''
                <div title="{group_tooltip}"
                     style="position:absolute;left:{gp}%;top:50%;transform:translate(-50%,-50%);
                            width:3px;height:20px;background:#94a3b8;border-radius:2px;z-index:2;"></div>'''

            if metric_name in center_data:
                cm = center_data[metric_name]['mean']
                cp = to_pct(cm)
                center_tooltip = f'Media centro: {cm:.1f}'
                center_marker_html = f'''
                <div title="{center_tooltip}"
                     style="position:absolute;left:{cp}%;top:50%;transform:translate(-50%,-50%);
                            width:3px;height:20px;background:{palette.UI_SUCCESS};border-radius:2px;z-index:2;"></div>'''

            rows_html.append(f"""
            <div class="d-flex align-items-center gap-3 py-2"
                 style="border-bottom:1px solid var(--am-border);">

                <!-- Nombre + meta -->
                <div style="width:180px;min-width:140px;flex-shrink:0;">
                    <div style="font-size:13px;font-weight:500;color:var(--am-text);
                                white-space:nowrap;overflow:hidden;text-overflow:ellipsis;"
                         title="{label}">{label}</div>
                    <div style="font-size:11px;color:var(--am-muted);">{last_date} {trend_icon}</div>
                </div>

                <!-- Barra normalizada -->
                <div style="flex:1;position:relative;height:28px;display:flex;align-items:center;">
                    <!-- Track -->
                    <div style="position:absolute;left:0;right:0;top:50%;transform:translateY(-50%);
                                height:8px;background:var(--am-border);border-radius:4px;overflow:visible;">
                        <!-- Fill alumno -->
                        <div style="width:{student_pct}%;height:100%;background:{bar_color};
                                    border-radius:4px;transition:width 0.5s ease;"></div>
                    </div>
                    {group_marker_html}
                    {center_marker_html}
                </div>

                <!-- Valor bruto -->
                <div style="width:64px;flex-shrink:0;text-align:right;">
                    <span style="font-size:18px;font-weight:700;color:{bar_color};line-height:1;">
                        {last_val:.0f}</span>
                    <div style="font-size:10px;color:var(--am-muted);">/ {observed_max:.0f}</div>
                </div>
            </div>""")
            metrics_shown += 1

        if not rows_html:
            return ''

        rows_joined = '\n'.join(rows_html)
        return f"""
        <div class="row mb-4">
            <div class="col-12">
                <div class="card">
                    <div class="card-header">
                        <h5 class="card-title">Resumen de Métricas</h5>
                        <p class="card-subtitle">Posición del alumno en cada variable respecto al grupo y al centro</p>
                    </div>
                    <div class="card-body" style="padding-top:4px;padding-bottom:4px;">
                        {rows_joined}

                        <!-- Leyenda -->
                        <div class="d-flex gap-4 pt-3" style="font-size:11px;color:var(--am-muted);">
                            <span><span style="display:inline-block;width:18px;height:7px;background:var(--am-primary);border-radius:3px;vertical-align:middle;"></span> Alumno</span>
                            <span><span style="display:inline-block;width:3px;height:14px;background:#94a3b8;border-radius:1px;vertical-align:middle;"></span> Media grupo</span>
                            <span><span style="display:inline-block;width:3px;height:14px;background:{palette.UI_SUCCESS};border-radius:1px;vertical-align:middle;"></span> Media centro</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>"""

    def _build_profile_html_chartjs(self, student, role_info, kpis, evolution, radar, alerts, alerts_history, participations, qualitative='', official_surveys=''):
        """Contexto para perfil con Chart.js (template dashboard_page_base)."""
        group_name = student.academic_group_id.name if student.academic_group_id else 'Sin grupo'

        # Determinar pestaña activa: Oficiales si hay resultados, Centro en otro caso
        has_official = bool(official_surveys and official_surveys.strip())
        active_oficial = 'show active' if has_official else ''
        active_centro  = '' if has_official else 'show active'
        tab_oficial_cls = 'nav-link active' if has_official else 'nav-link'
        tab_centro_cls  = 'nav-link' if has_official else 'nav-link active'

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

                            <!-- KPIs -->
                            <div class="kpi-grid">
                                {kpis}
                            </div>

                            <!-- ═══ PESTAÑAS DE CUESTIONARIOS ═══ -->
                            <div class="card mb-4">
                                <div class="card-header" style="padding-bottom:0;border-bottom:none;">
                                    <ul class="nav nav-tabs" style="border-bottom:none;margin-bottom:-1px;gap:4px;">
                                        <li class="nav-item">
                                            <a class="{tab_oficial_cls}" id="tab-oficial-btn"
                                               data-bs-toggle="tab" href="#tab-oficial" role="tab"
                                               style="font-size:13px;font-weight:600;">
                                                <i class="fa-solid fa-clipboard-check me-1"></i>Cuestionarios Oficiales
                                            </a>
                                        </li>
                                        <li class="nav-item">
                                            <a class="{tab_centro_cls}" id="tab-centro-btn"
                                               data-bs-toggle="tab" href="#tab-centro" role="tab"
                                               style="font-size:13px;font-weight:600;">
                                                <i class="fa-solid fa-school me-1"></i>Cuestionarios del Centro
                                            </a>
                                        </li>
                                    </ul>
                                </div>
                                <div class="card-body" style="padding-top:20px;">
                                    <div class="tab-content">
                                        <div class="tab-pane fade {active_oficial}" id="tab-oficial" role="tabpanel">
                                            {oficial_content}
                                        </div>
                                        <div class="tab-pane fade {active_centro}" id="tab-centro" role="tabpanel">
                                            {centro_content}
                                        </div>
                                    </div>
                                </div>
                            </div>

                            <!-- ═══ RESPUESTAS CUALITATIVAS ═══ -->
                            <div class="row">
                                <div class="col-12">
                                    <div class="card">
                                        <div class="card-header">
                                            <h5 class="card-title">Respuestas Cualitativas</h5>
                                            <p class="card-subtitle">Textos y comentarios abiertos</p>
                                        </div>
                                        <div class="card-body">
                                            {qualitative}
                                        </div>
                                    </div>
                                </div>
                            </div>

                            <!-- ═══ ALERTAS + PARTICIPACIÓN ═══ -->
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
                                                <button class="btn btn-outline-secondary btn-sm w-100"
                                                        type="button"
                                                        data-bs-toggle="collapse"
                                                        data-bs-target="#alertsHistory"
                                                        aria-expanded="false">
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
                                        <div class="card-body">
                                            {participations}
                                        </div>
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
        """Estilos profesionales estilo Stripe/Linear/Notion."""
        return """
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
            
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }
            
            body {
                font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                background-color: var(--am-bg);
                color: var(--am-text);
                line-height: 1.6;
                font-size: 15px;
                padding-bottom: 80px;
            }
            
            .container {
                max-width: 1200px;
                margin: 0 auto;
                padding: 32px 24px;
            }
            
            h1 {
                font-size: 32px;
                font-weight: 700;
                color: var(--am-text);
                margin-bottom: 8px;
                letter-spacing: -0.5px;
            }
            
            .subtitle {
                color: var(--am-muted);
                font-size: 16px;
                font-weight: 400;
                margin-bottom: 32px;
            }
            
            .kpi-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
                gap: 20px;
                margin-bottom: 32px;
            }
            
            .kpi-card {
                background: var(--am-surface);
                border: 1px solid var(--am-border);
                border-radius: 10px;
                padding: 24px;
                transition: all 0.2s ease;
            }
            
            .kpi-card:hover {
                transform: translateY(-2px);
                box-shadow: 0 4px 12px rgba(0,0,0,0.08);
                border-color: var(--am-border);
            }
            
            .kpi-label {
                font-size: 13px;
                font-weight: 500;
                color: var(--am-muted);
                text-transform: uppercase;
                letter-spacing: 0.5px;
                margin-bottom: 8px;
            }
            
            .kpi-value {
                font-size: 36px;
                font-weight: 700;
                color: var(--am-text);
                line-height: 1;
                margin-bottom: 4px;
            }
            
            .kpi-description {
                font-size: 13px;
                color: var(--am-muted);
                font-weight: 400;
            }
            
            .card {
                background: var(--am-surface);
                border: 1px solid var(--am-border);
                border-radius: 10px;
                margin-bottom: 24px;
                overflow: hidden;
                box-shadow: 0 1px 3px rgba(0,0,0,0.04);
            }
            
            .card-header {
                padding: 20px 24px;
                border-bottom: 1px solid var(--am-light);
                background: var(--am-surface);
            }
            
            .card-title {
                font-size: 18px;
                font-weight: 600;
                color: var(--am-text);
                margin: 0;
            }
            
            .card-title-sm {
                font-size: 15px;
                font-weight: 600;
                color: var(--am-text);
                margin: 0;
            }
            
            .card-subtitle {
                font-size: 13px;
                color: var(--am-muted);
                margin: 4px 0 0 0;
                font-weight: 400;
            }
            
            .card-body {
                padding: 24px;
            }
            
            .alert {
                background: var(--am-bg);
                border: 1px solid var(--am-border);
                border-radius: 8px;
                padding: 16px 20px;
                color: var(--am-muted);
                font-size: 14px;
                margin-bottom: 20px;
            }
            
            .alert-info {
                background: var(--am-primary-100);
                border-color: var(--am-primary-200);
                color: var(--am-primary-600);
            }
            
            .alert-warning {
                background: var(--am-light);
                border-color: var(--am-border);
                color: var(--am-warning);
            }
            
            .alert-danger {
                background: var(--am-light);
                border-color: var(--am-border);
                color: var(--am-danger);
            }
            
            .badge {
                display: inline-block;
                padding: 4px 10px;
                border-radius: 6px;
                font-size: 12px;
                font-weight: 500;
                letter-spacing: 0.3px;
            }
            
            .badge-info {
                background: var(--am-primary-100);
                color: var(--am-primary-600);
            }
            
            .badge-warning {
                background: var(--am-warning);
                color: var(--am-text);
            }
            
            .badge-danger {
                background: var(--am-light);
                color: var(--am-danger);
            }
            
            .row {
                display: flex;
                flex-wrap: wrap;
                margin: 0 -12px;
            }
            
            .col-lg-6 {
                flex: 0 0 50%;
                max-width: 50%;
                padding: 0 12px;
            }
            
            @media (max-width: 991px) {
                .col-lg-6 {
                    flex: 0 0 100%;
                    max-width: 100%;
                }
            }
            
            table {
                width: 100%;
                border-collapse: collapse;
                font-size: 14px;
            }
            
            thead {
                background: var(--am-bg);
                border-bottom: 1px solid var(--am-border);
            }
            
            th {
                padding: 12px 16px;
                text-align: left;
                font-weight: 600;
                color: var(--am-muted);
                font-size: 13px;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }
            
            td {
                padding: 14px 16px;
                border-bottom: 1px solid var(--am-light);
                color: var(--am-text);
            }
            
            tr:last-child td {
                border-bottom: none;
            }
            
            tbody tr:hover {
                background: var(--am-bg);
            }
            
            ul {
                list-style: none;
                padding: 0;
            }
            
            li {
                padding: 12px 0;
                border-bottom: 1px solid var(--am-light);
                color: var(--am-text);
                font-size: 14px;
            }
            
            li:last-child {
                border-bottom: none;
            }
        </style>
        """

    def _error_html(self, message):
        """Raises ValueError so the controller can render the appropriate error template."""
        raise ValueError(message)
