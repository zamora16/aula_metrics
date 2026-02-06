# -*- coding: utf-8 -*-
"""
Dashboard Student Profile - Perfil individual longitudinal de alumno
"""
from odoo import models, api, fields
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import json


class DashboardStudentProfile(models.TransientModel):
    _name = 'aulametrics.dashboard.student_profile'
    _description = 'Generador de Perfil Individual de Estudiante'

    @api.model
    def generate_student_profile(self, student_id, role_info=None):
        """
        Genera el dashboard de perfil individual de un estudiante.
        
        Args:
            student_id (int): ID del estudiante (res.partner)
            role_info (dict): Información del rol del usuario
        
        Returns:
            str: HTML completo del perfil
        """
        if role_info is None:
            role_info = {'role': 'admin', 'anonymize_students': False}

        # Verificar acceso al estudiante
        student = self.env['res.partner'].browse(student_id)
        if not student.exists():
            return self._error_html("Estudiante no encontrado")

        # Validar permisos de acceso
        if not self._can_access_student(student, role_info):
            return self._error_html("No tiene permisos para ver este perfil")

        # Obtener todas las métricas del estudiante
        metrics = self._get_student_metrics(student_id)
        
        if not metrics:
            return self._build_empty_profile(student, role_info)

        # Preparar DataFrame
        df = self._prepare_metrics_dataframe(metrics)
        
        # Generar componentes del dashboard
        timeline_chart = self._generate_timeline_chart(df, student)
        evolution_charts = self._generate_evolution_charts(df, student)
        comparison_charts = self._generate_comparison_charts(student_id, df)
        radar_chart = self._generate_radar_chart(student_id, df)
        
        # KPIs del estudiante
        kpis = self._generate_student_kpis(student, df)
        
        # Alertas activas
        alerts_html = self._get_student_alerts_html(student_id)
        
        # Histórico de participaciones
        participations_html = self._get_participations_html(student_id)
        
        # Construir HTML final
        return self._build_profile_html(
            student, role_info, kpis, timeline_chart, evolution_charts,
            comparison_charts, radar_chart, alerts_html, participations_html
        )

    @api.model
    def generate_students_list(self, role_info=None):
        """
        Genera una lista HTML de estudiantes accesibles según el rol.
        
        Args:
            role_info (dict): Información del rol del usuario
        
        Returns:
            str: HTML completo con la lista de estudiantes
        """
        if role_info is None:
            role_info = {'role': 'admin'}
        
        # Obtener estudiantes según rol
        Partner = self.env['res.partner']
        domain = [('is_student', '=', True)]
        
        # Tutores solo ven sus grupos
        if role_info.get('role') == 'tutor':
            allowed_groups = role_info.get('allowed_group_ids', [])
            if not allowed_groups:
                students = Partner.browse([])
            else:
                domain.append(('academic_group_id', 'in', allowed_groups))
                students = Partner.search(domain, order='name')
        else:
            # Counselor y admin ven todos
            students = Partner.search(domain, order='name')
        
        # Generar HTML
        return self._build_students_list_html(students, role_info)

    def _can_access_student(self, student, role_info):
        """Verifica si el usuario tiene permisos para ver este estudiante."""
        role = role_info.get('role', 'tutor')
        
        # Admin y counselor tienen acceso a todos
        if role in ['admin', 'counselor']:
            return True
        
        # Management no tiene acceso a perfiles individuales
        if role == 'management':
            return False
        
        # Tutores: solo alumnos de sus grupos
        if role == 'tutor':
            allowed_groups = role_info.get('allowed_group_ids', [])
            student_group = student.academic_group_id.id if student.academic_group_id else None
            return student_group in allowed_groups
        
        return False

    def _get_student_metrics(self, student_id):
        """Obtiene todas las métricas del estudiante ordenadas por fecha."""
        MetricValue = self.env['aulametrics.metric_value']
        return MetricValue.search([
            ('student_id', '=', student_id)
        ], order='timestamp desc')

    def _prepare_metrics_dataframe(self, metrics):
        """Convierte las métricas a DataFrame para análisis."""
        data = []
        for m in metrics:
            # Detectar tipo y valor
            if m.value_float:
                value = m.value_float
                value_type = 'numeric'
            elif m.value_json:
                value = m.value_json
                value_type = 'json'
            elif m.value_text:
                value = m.value_text
                value_type = 'text'
            else:
                continue
            
            row = {
                'timestamp': m.timestamp,
                'metric_name': m.metric_name,
                'metric_label': m.metric_label or m.metric_name,
                'value': value,
                'value_type': value_type,
                'evaluation_name': m.evaluation_id.name if m.evaluation_id else 'Sin evaluación',
                'evaluation_id': m.evaluation_id.id if m.evaluation_id else None,
            }
            data.append(row)
        
        return pd.DataFrame(data)

    def _generate_timeline_chart(self, df, student):
        """Genera gráfico de timeline con todas las métricas."""
        if df.empty:
            return ''
        
        # Filtrar solo métricas numéricas
        df_numeric = df[df['value_type'] == 'numeric'].copy()
        if df_numeric.empty:
            return ''
        
        fig = go.Figure()
        
        # Una línea por cada métrica
        for metric in df_numeric['metric_label'].unique():
            df_metric = df_numeric[df_numeric['metric_label'] == metric].sort_values('timestamp')
            
            fig.add_trace(go.Scatter(
                x=df_metric['timestamp'],
                y=df_metric['value'],
                name=metric,
                mode='lines+markers',
                line=dict(width=2),
                marker=dict(size=8)
            ))
        
        fig.update_layout(
            title=f'📈 Evolución Temporal de Métricas - {student.name}',
            xaxis_title='Fecha',
            yaxis_title='Puntuación',
            height=400,
            hovermode='x unified',
            template='plotly_white',
            legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1)
        )
        
        return fig.to_html(full_html=False, include_plotlyjs='cdn', div_id='timeline_chart')

    def _generate_evolution_charts(self, df, student):
        """Genera gráficos individuales de evolución por métrica."""
        if df.empty:
            return []
        
        charts = []
        df_numeric = df[df['value_type'] == 'numeric'].copy()
        
        for metric_label in df_numeric['metric_label'].unique():
            df_metric = df_numeric[df_numeric['metric_label'] == metric_label].sort_values('timestamp')
            
            # Buscar umbrales configurados
            metric_name = df_metric.iloc[0]['metric_name']
            threshold = self._get_metric_threshold(metric_name)
            
            fig = go.Figure()
            
            # Línea de evolución
            fig.add_trace(go.Scatter(
                x=df_metric['timestamp'],
                y=df_metric['value'],
                mode='lines+markers',
                name='Valor',
                line=dict(color='#667eea', width=3),
                marker=dict(size=10)
            ))
            
            # Línea de umbral si existe
            if threshold:
                fig.add_hline(
                    y=threshold['value'],
                    line_dash='dash',
                    line_color='red',
                    annotation_text=f"Umbral: {threshold['name']}",
                    annotation_position='right'
                )
            
            # Anotaciones con evaluaciones
            for _, row in df_metric.iterrows():
                fig.add_annotation(
                    x=row['timestamp'],
                    y=row['value'],
                    text=row['evaluation_name'],
                    showarrow=True,
                    arrowhead=2,
                    arrowsize=1,
                    arrowwidth=1,
                    ax=0,
                    ay=-40,
                    font=dict(size=9)
                )
            
            fig.update_layout(
                title=f'{metric_label}',
                xaxis_title='Fecha',
                yaxis_title='Puntuación',
                height=300,
                template='plotly_white',
                showlegend=False
            )
            
            charts.append(fig.to_html(full_html=False, include_plotlyjs=False, div_id=f'evolution_{metric_name}'))
        
        return charts

    def _generate_comparison_charts(self, student_id, df_student):
        """Genera comparativa del estudiante vs. su grupo y curso."""
        charts = []
        
        student = self.env['res.partner'].browse(student_id)
        if not student.academic_group_id:
            return charts
        
        group_id = student.academic_group_id.id
        
        # Para cada métrica numérica del estudiante, comparar con grupo
        df_numeric = df_student[df_student['value_type'] == 'numeric'].copy()
        
        for metric_name in df_numeric['metric_name'].unique():
            # Obtener valor actual del estudiante
            student_value = df_numeric[df_numeric['metric_name'] == metric_name].iloc[-1]['value']
            metric_label = df_numeric[df_numeric['metric_name'] == metric_name].iloc[-1]['metric_label']
            
            # Obtener valores del grupo
            MetricValue = self.env['aulametrics.metric_value']
            group_metrics = MetricValue.search([
                ('metric_name', '=', metric_name),
                ('academic_group_id', '=', group_id)
            ])
            
            if len(group_metrics) < 2:  # Necesitamos al menos 2 valores para comparar
                continue
            
            group_values = [m.value_float for m in group_metrics if m.value_float]
            
            if not group_values:
                continue
            
            # Box plot comparativo
            fig = go.Figure()
            
            fig.add_trace(go.Box(
                y=group_values,
                name='Grupo',
                marker_color='lightblue',
                boxmean='sd'
            ))
            
            fig.add_trace(go.Scatter(
                x=['Grupo'],
                y=[student_value],
                mode='markers',
                name=student.name,
                marker=dict(size=15, color='red', symbol='star')
            ))
            
            fig.update_layout(
                title=f'{metric_label} - Comparativa con Grupo',
                yaxis_title='Puntuación',
                showlegend=True,
                height=350,
                template='plotly_white'
            )
            
            charts.append(fig.to_html(full_html=False, include_plotlyjs=False, div_id=f'comparison_{metric_name}'))
        
        return charts

    def _generate_radar_chart(self, student_id, df):
        """Genera radar chart con perfil multidimensional del estudiante."""
        if df.empty:
            return ''
        
        df_numeric = df[df['value_type'] == 'numeric'].copy()
        if len(df_numeric['metric_name'].unique()) < 3:
            return ''  # Necesitamos al menos 3 métricas
        
        # Obtener valor más reciente de cada métrica
        latest_values = df_numeric.groupby('metric_label').last().reset_index()
        
        # Normalizar valores a escala 0-100
        latest_values['normalized'] = (latest_values['value'] / latest_values['value'].max()) * 100
        
        fig = go.Figure()
        
        fig.add_trace(go.Scatterpolar(
            r=latest_values['normalized'].tolist(),
            theta=latest_values['metric_label'].tolist(),
            fill='toself',
            name='Perfil Actual',
            line_color='#667eea'
        ))
        
        fig.update_layout(
            polar=dict(
                radialaxis=dict(
                    visible=True,
                    range=[0, 100]
                )
            ),
            title='Perfil Multidimensional',
            height=400,
            template='plotly_white'
        )
        
        return fig.to_html(full_html=False, include_plotlyjs=False, div_id='radar_chart')

    def _generate_student_kpis(self, student, df):
        """Genera KPIs del estudiante."""
        kpis = []
        
        # Total de evaluaciones completadas
        total_evals = df['evaluation_id'].nunique() if not df.empty else 0
        kpis.append(f"""
        <div class="kpi-card">
            <div class="kpi-icon-bg"><i class="fa-solid fa-clipboard-check"></i></div>
            <div class="kpi-label">Evaluaciones Completadas</div>
            <div class="kpi-number">{total_evals}</div>
        </div>
        """)
        
        # Total de métricas registradas
        total_metrics = len(df) if not df.empty else 0
        kpis.append(f"""
        <div class="kpi-card">
            <div class="kpi-icon-bg"><i class="fa-solid fa-chart-line"></i></div>
            <div class="kpi-label">Métricas Registradas</div>
            <div class="kpi-number">{total_metrics}</div>
        </div>
        """)
        
        # Grupo académico
        group_name = student.academic_group_id.name if student.academic_group_id else 'Sin grupo'
        kpis.append(f"""
        <div class="kpi-card">
            <div class="kpi-icon-bg"><i class="fa-solid fa-users"></i></div>
            <div class="kpi-label">Grupo Académico</div>
            <div class="kpi-number" style="font-size: 1.2rem;">{group_name}</div>
        </div>
        """)
        
        # Alertas activas
        alerts_count = self.env['aulametrics.alert'].search_count([
            ('student_id', '=', student.id),
            ('status', '=', 'active')
        ])
        alert_color = 'danger' if alerts_count > 0 else 'success'
        kpis.append(f"""
        <div class="kpi-card kpi-{alert_color}">
            <div class="kpi-icon-bg"><i class="fa-solid fa-bell"></i></div>
            <div class="kpi-label">Alertas Activas</div>
            <div class="kpi-number">{alerts_count}</div>
        </div>
        """)
        
        return '\n'.join(kpis)

    def _get_student_alerts_html(self, student_id):
        """Obtiene HTML con las alertas activas del estudiante."""
        Alert = self.env['aulametrics.alert']
        alerts = Alert.search([
            ('student_id', '=', student_id),
            ('status', '=', 'active')
        ], order='severity desc, alert_date desc')
        
        if not alerts:
            return '<div class="alert alert-success"><i class="fa-solid fa-check-circle me-2"></i>No hay alertas activas para este estudiante</div>'
        
        html = '<div class="alerts-container">'
        for alert in alerts:
            severity_icons = {
                'low': ('info', 'fa-info-circle'),
                'medium': ('warning', 'fa-exclamation-triangle'),
                'high': ('danger', 'fa-exclamation-circle'),
                'critical': ('danger', 'fa-skull-crossbones')
            }
            badge_class, icon = severity_icons.get(alert.severity, ('secondary', 'fa-question'))
            
            html += f"""
            <div class="alert alert-{badge_class} d-flex justify-content-between align-items-start">
                <div>
                    <h6><i class="fa-solid {icon} me-2"></i>{alert.name}</h6>
                    <p class="mb-1">{alert.message or ''}</p>
                    <small class="text-muted">Creada: {alert.alert_date.strftime('%d/%m/%Y %H:%M')}</small>
                </div>
                <span class="badge bg-{badge_class}">{alert.severity.upper()}</span>
            </div>
            """
        
        html += '</div>'
        return html

    def _get_participations_html(self, student_id):
        """Obtiene HTML con el histórico de participaciones."""
        Participation = self.env['aulametrics.participation']
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

    def _get_metric_threshold(self, metric_name):
        """Obtiene el umbral configurado para una métrica."""
        Threshold = self.env['aulametrics.threshold']
        threshold = Threshold.search([
            ('score_field', '=', metric_name),
            ('active', '=', True)
        ], limit=1, order='severity desc')
        
        if threshold:
            return {
                'value': threshold.threshold_value,
                'name': threshold.name,
                'operator': threshold.operator
            }
        return None

    def _build_empty_profile(self, student, role_info):
        """HTML cuando el estudiante no tiene métricas."""
        role_badge = self._get_role_badge(role_info)
        
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Perfil de {student.name} - AulaMetrics</title>
            <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
            <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
            {self._profile_styles()}
        </head>
        <body>
            {self._profile_header(student, role_badge)}
            <div class="container-fluid mt-4">
                <div class="text-center py-5">
                    <i class="fa-solid fa-user-slash fa-5x text-muted mb-4"></i>
                    <h3 class="text-muted">Este estudiante aún no tiene métricas registradas</h3>
                    <p class="text-muted">Complete una evaluación para comenzar a ver datos</p>
                </div>
            </div>
        </body>
        </html>
        """

    def _build_profile_html(self, student, role_info, kpis, timeline, evolution_charts, 
                           comparison_charts, radar, alerts, participations):
        """Construye el HTML completo del perfil."""
        role_badge = self._get_role_badge(role_info)
        
        evolution_html = '<div class="row">' + ''.join([
            f'<div class="col-md-6 mb-4">{chart}</div>' for chart in evolution_charts
        ]) + '</div>'
        
        comparison_html = '<div class="row">' + ''.join([
            f'<div class="col-md-6 mb-4">{chart}</div>' for chart in comparison_charts
        ]) + '</div>'
        
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Perfil de {student.name} - AulaMetrics</title>
            <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
            <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
            <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
            <script src="https://cdn.plot.ly/plotly-2.26.0.min.js"></script>
            {self._profile_styles()}
        </head>
        <body>
            {self._profile_header(student, role_badge)}
            
            <div class="container-fluid mt-4">
                <!-- KPIs -->
                <div class="kpi-container mb-4">
                    {kpis}
                </div>
                
                <!-- Alertas -->
                <div class="card mb-4">
                    <div class="card-header">
                        <h5><i class="fa-solid fa-bell me-2"></i>Alertas Activas</h5>
                    </div>
                    <div class="card-body">
                        {alerts}
                    </div>
                </div>
                
                <!-- Timeline general -->
                <div class="card mb-4">
                    <div class="card-body">
                        {timeline}
                    </div>
                </div>
                
                <!-- Radar chart -->
                {f'<div class="card mb-4"><div class="card-body">{radar}</div></div>' if radar else ''}
                
                <!-- Evolución por métrica -->
                <div class="card mb-4">
                    <div class="card-header">
                        <h5><i class="fa-solid fa-chart-line me-2"></i>Evolución por Métrica</h5>
                    </div>
                    <div class="card-body">
                        {evolution_html}
                    </div>
                </div>
                
                <!-- Comparativa con grupo -->
                {f'<div class="card mb-4"><div class="card-header"><h5><i class="fa-solid fa-users me-2"></i>Comparativa con Grupo</h5></div><div class="card-body">{comparison_html}</div></div>' if comparison_charts else ''}
                
                <!-- Histórico de participaciones -->
                <div class="card mb-4">
                    <div class="card-header">
                        <h5><i class="fa-solid fa-history me-2"></i>Histórico de Participaciones</h5>
                    </div>
                    <div class="card-body">
                        {participations}
                    </div>
                </div>
            </div>
            
            <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
        </body>
        </html>
        """

    def _get_role_badge(self, role_info):
        """Genera el badge de rol."""
        role = role_info.get('role', 'tutor')
        badges = {
            'admin': '<span class="badge bg-danger"><i class="fa-solid fa-shield-halved"></i> Administrador</span>',
            'counselor': '<span class="badge bg-primary"><i class="fa-solid fa-user-tie"></i> Orientador/a</span>',
            'management': '<span class="badge bg-warning text-dark"><i class="fa-solid fa-briefcase"></i> Equipo Directivo</span>',
            'tutor': '<span class="badge bg-success"><i class="fa-solid fa-chalkboard-user"></i> Tutor/a</span>',
        }
        return badges.get(role, '')

    def _profile_header(self, student, role_badge):
        """Encabezado del perfil."""
        group_name = student.academic_group_id.name if student.academic_group_id else 'Sin grupo'
        
        return f"""
        <header class="dashboard-header">
            <div>
                <div class="header-title">
                    <h1><i class="fa-solid fa-user me-2 text-primary"></i>Perfil de {student.name}</h1>
                </div>
                <div class="header-meta">
                    {group_name} &bull; {fields.Date.today().strftime('%d/%m/%Y')}
                </div>
            </div>
            <div>
                {role_badge}
                <a href="/web" class="btn btn-outline-secondary btn-sm ms-2">
                    <i class="fa-solid fa-arrow-left"></i> Volver
                </a>
            </div>
        </header>
        """

    def _profile_styles(self):
        """Estilos CSS del perfil."""
        return """
        <style>
            body { background: #f1f5f9; font-family: 'Inter', sans-serif; padding-bottom: 60px; color: #1e293b; }
            .dashboard-header { background: white; padding: 1.5rem 2rem; border-bottom: 1px solid #e2e8f0; margin-bottom: 2rem; display: flex; justify-content: space-between; align-items: center; box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.05); }
            .header-title h1 { font-size: 1.5rem; font-weight: 700; margin: 0; color: #0f172a; }
            .header-meta { color: #64748b; font-size: 0.875rem; margin-top: 4px; }
            
            .kpi-container { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; }
            .kpi-card { background: white; border-radius: 16px; padding: 1.25rem; border: 1px solid #f1f5f9; box-shadow: 0 2px 4px rgba(0,0,0,0.05); position: relative; overflow: hidden; transition: transform 0.2s; }
            .kpi-card:hover { transform: translateY(-2px); box-shadow: 0 4px 8px rgba(0,0,0,0.1); }
            .kpi-card.kpi-danger { border-left: 4px solid #dc3545; }
            .kpi-card.kpi-success { border-left: 4px solid #28a745; }
            .kpi-icon-bg { position: absolute; right: -5px; top: -5px; font-size: 4rem; opacity: 0.05; transform: rotate(15deg); }
            .kpi-label { font-size: 0.8rem; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; }
            .kpi-number { font-size: 2rem; font-weight: 700; color: #0f172a; margin: 0.25rem 0; }
            
            .card { border-radius: 12px; border: 1px solid #e2e8f0; box-shadow: 0 1px 3px rgba(0,0,0,0.05); margin-bottom: 1.5rem; }
            .card-header { background: white; border-bottom: 1px solid #e2e8f0; font-weight: 600; padding: 1rem 1.5rem; }
            .card-body { padding: 1.5rem; }
            
            .alerts-container .alert { border-radius: 8px; margin-bottom: 1rem; }
            
            .table { margin-bottom: 0; }
            .table thead th { background: #f8fafc; font-weight: 600; border-bottom: 2px solid #e2e8f0; }
        </style>
        """

    def _build_students_list_html(self, students, role_info):
        """Construye el HTML de la lista de estudiantes."""
        role_badge = self._get_role_badge(role_info)
        
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
                metrics_count = self.env['aulametrics.metric_value'].search_count([
                    ('student_id', '=', student.id)
                ])
                alerts_count = self.env['aulametrics.alert'].search_count([
                    ('student_id', '=', student.id),
                    ('status', '=', 'active')
                ])
                
                # Badge de alertas
                alerts_badge = ''
                if alerts_count > 0:
                    alerts_badge = f'<span class="badge bg-danger">{alerts_count} alerta(s)</span>'
                else:
                    alerts_badge = '<span class="badge bg-success">Sin alertas</span>'
                
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
                        <a href="/aulametrics/student/{student.id}" class="btn btn-sm btn-primary">
                            <i class="fa-solid fa-chart-line me-1"></i> Ver Perfil
                        </a>
                    </td>
                </tr>
                '''
        
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Perfiles de Alumnos - AulaMetrics</title>
            <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
            <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
            <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
            <style>
                body {{ background: #f1f5f9; font-family: 'Inter', sans-serif; color: #1e293b; }}
                .dashboard-header {{ background: white; padding: 1.5rem 2rem; border-bottom: 1px solid #e2e8f0; margin-bottom: 2rem; display: flex; justify-content: space-between; align-items: center; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }}
                .header-title h1 {{ font-size: 1.75rem; font-weight: 700; margin: 0; color: #0f172a; }}
                .header-meta {{ color: #64748b; font-size: 0.875rem; margin-top: 4px; }}
                
                .card {{ border-radius: 12px; border: 1px solid #e2e8f0; box-shadow: 0 1px 3px rgba(0,0,0,0.05); background: white; }}
                .card-header {{ background: white; border-bottom: 1px solid #e2e8f0; font-weight: 600; padding: 1.25rem 1.5rem; }}
                .table {{ margin-bottom: 0; }}
                .table thead th {{ background: #f8fafc; font-weight: 600; border-bottom: 2px solid #e2e8f0; padding: 1rem; }}
                .table tbody td {{ padding: 1rem; vertical-align: middle; }}
                .table tbody tr:hover {{ background: #f8fafc; }}
                
                .search-box {{ margin-bottom: 1.5rem; }}
                .search-box input {{ border-radius: 8px; padding: 0.75rem 1rem; border: 1px solid #e2e8f0; }}
                .search-box input:focus {{ border-color: #3b82f6; box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1); }}
                
                .filters-bar {{ margin-bottom: 1.5rem; display: flex; gap: 1rem; align-items: center; }}
                .filters-bar select {{ border-radius: 8px; padding: 0.75rem 1rem; border: 1px solid #e2e8f0; }}
                .filters-bar select:focus {{ border-color: #3b82f6; box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1); }}
            </style>
        </head>
        <body>
            <header class="dashboard-header">
                <div>
                    <div class="header-title">
                        <h1><i class="fa-solid fa-users me-2 text-primary"></i>Perfiles de Alumnos</h1>
                    </div>
                    <div class="header-meta">
                        Listado de estudiantes con acceso a perfil individual &bull; {fields.Date.today().strftime('%d/%m/%Y')}
                    </div>
                </div>
                <div>
                    {role_badge}
                    <a href="/aulametrics/dashboard" class="btn btn-outline-primary btn-sm ms-2">
                        <i class="fa-solid fa-gauge-high"></i> Dashboard
                    </a>
                    <a href="/web" class="btn btn-outline-secondary btn-sm ms-2">
                        <i class="fa-solid fa-arrow-left"></i> Volver
                    </a>
                </div>
            </header>
            
            <div class="container-fluid px-4">
                <div class="filters-bar">
                    <div class="flex-grow-1">
                        <input type="text" id="searchInput" class="form-control" placeholder="🔍 Buscar por nombre, email o grupo...">
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
            </div>
            
            <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
            <script>
                // Función para aplicar todos los filtros
                function applyFilters() {{
                    const searchTerm = document.getElementById('searchInput').value.toLowerCase();
                    const selectedGroup = document.getElementById('groupFilter').value;
                    const rows = document.querySelectorAll('#studentsTable tbody tr');
                    
                    let visibleCount = 0;
                    rows.forEach(row => {{
                        const text = row.textContent.toLowerCase();
                        const groupId = row.getAttribute('data-group-id');
                        
                        // Verificar filtro de texto
                        const matchesSearch = !searchTerm || text.includes(searchTerm);
                        
                        // Verificar filtro de grupo
                        const matchesGroup = !selectedGroup || groupId === selectedGroup;
                        
                        // Mostrar solo si cumple ambos filtros
                        if (matchesSearch && matchesGroup) {{
                            row.style.display = '';
                            visibleCount++;
                        }} else {{
                            row.style.display = 'none';
                        }}
                    }});
                    
                    // Actualizar contador en el header
                    const header = document.querySelector('.card-header span');
                    if (header) {{
                        const totalCount = rows.length;
                        if (visibleCount === totalCount) {{
                            header.innerHTML = '<i class="fa-solid fa-list me-2"></i>Estudiantes (' + totalCount + ')';
                        }} else {{
                            header.innerHTML = '<i class="fa-solid fa-list me-2"></i>Estudiantes (' + visibleCount + ' de ' + totalCount + ')';
                        }}
                    }}
                }}
                
                // Búsqueda en tiempo real
                document.getElementById('searchInput').addEventListener('keyup', applyFilters);
                
                // Filtro por grupo
                document.getElementById('groupFilter').addEventListener('change', applyFilters);
            </script>
        </body>
        </html>
        """

    def _error_html(self, message):
        """HTML de error."""
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Error - AulaMetrics</title>
            <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
            <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
        </head>
        <body style="background: #f1f5f9; font-family: sans-serif;">
            <div class="container mt-5">
                <div class="alert alert-danger text-center">
                    <i class="fa-solid fa-exclamation-triangle fa-3x mb-3"></i>
                    <h3>{message}</h3>
                    <a href="/web" class="btn btn-primary mt-3">Volver</a>
                </div>
            </div>
        </body>
        </html>
        """
