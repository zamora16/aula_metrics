# -*- coding: utf-8 -*-
"""
Dashboard Student Profile - Perfil individual longitudinal de alumno
"""
from odoo import models, api, fields
import pandas as pd
import json


class DashboardStudentProfile(models.TransientModel):
    _name = 'aulametrics.dashboard.student_profile'
    _description = 'Generador de Perfil Individual de Estudiante'

    @api.model
    def generate_student_profile(self, student_id, role_info=None):
        """
        Genera el dashboard de perfil individual de un estudiante con Chart.js.
        
        Args:
            student_id (int): ID del estudiante (res.partner)
            role_info (dict): Información del rol del usuario
        
        Returns:
            str: HTML completo del perfil
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
        
        evolution_charts = self._generate_evolution_chartjs(df, student)
        radar_chart = self._generate_radar_chart(df, student)
        kpis = self._generate_student_kpis(student, df)
        alerts_html = self._get_student_alerts_html(student_id)
        participations_html = self._get_participations_html(student_id)
        qualitative_html = self._get_qualitative_responses_html(student_id)
        
        return self._build_profile_html_chartjs(
            student, role_info, kpis, '', 
            evolution_charts, radar_chart, alerts_html, participations_html, qualitative_html
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

    @api.model
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
        alerts_count = self.env['aulametrics.alert'].search_count([
            ('student_id', '=', student.id),
            ('status', '=', 'active')
        ])
        kpis.append(f"""
        <div class="kpi-card">
            <div class="kpi-label">Alertas</div>
            <div class="kpi-value" style="color: {'#ef4444' if alerts_count > 0 else '#10b981'};">{alerts_count}</div>
            <div class="kpi-description">Activas</div>
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

    def _get_qualitative_responses_html(self, student_id):
        """Obtiene HTML con las respuestas cualitativas del estudiante."""
        QualitativeResponse = self.env['aulametrics.qualitative_response']
        responses = QualitativeResponse.search([
            ('student_id', '=', student_id)
        ], order='response_date desc', limit=20)
        
        if not responses:
            return '<p class="text-muted">No hay respuestas cualitativas registradas</p>'
        
        html = '<div class="qualitative-responses">'
        
        for resp in responses:
            alert_class = 'alert-warning' if resp.has_alert_keywords else ''
            alert_badge = '<span class="badge bg-danger">Alerta</span>' if resp.has_alert_keywords else '<span class="badge bg-success">OK</span>'
            
            # Información de la pregunta
            question_title = resp.question_id.title if resp.question_id else 'Pregunta sin título'
            evaluation_name = resp.evaluation_id.name if resp.evaluation_id else 'Sin evaluación'
            date_str = resp.response_date.strftime('%d/%m/%Y') if resp.response_date else 'Sin fecha'
            
            # Detectar keywords encontradas
            keywords_html = ''
            if resp.has_alert_keywords and resp.detected_keywords:
                try:
                    import json
                    detected = json.loads(resp.detected_keywords)
                    if detected:
                        keywords_list = ', '.join([f'<strong>{kw}</strong>' for kw in detected])
                        keywords_html = f'<div class="mt-2"><small class="text-danger">Palabras detectadas: {keywords_list}</small></div>'
                except:
                    pass
            
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
        group_name = student.academic_group_id.name if student.academic_group_id else 'Sin grupo'
        
        return f"""
        <!DOCTYPE html>
        <html lang="es">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Perfil de {student.name} - AulaMetrics</title>
            <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
            {self._profile_styles_chartjs()}
        </head>
        <body>
            <div class="container">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 32px;">
                    <div>
                        <h1>{student.name}</h1>
                        <p class="subtitle">{group_name} · {fields.Date.today().strftime('%d/%m/%Y')}</p>
                    </div>
                    <div>
                        {role_badge}
                        <a href="/aulametrics/students" style="margin-left: 12px; padding: 8px 16px; background: white; border: 1px solid #e5e7eb; border-radius: 6px; text-decoration: none; color: #64748b; font-weight: 500; font-size: 14px;">
                            <i class="fa-solid fa-users"></i> Lista
                        </a>
                    </div>
                </div>
                
                <div class="card" style="text-align: center; padding: 60px 40px;">
                    <i class="fa-solid fa-chart-line" style="font-size: 80px; color: #cbd5e1; margin-bottom: 24px;"></i>
                    <h3 style="color: #64748b; margin-bottom: 12px;">Sin datos disponibles</h3>
                    <p style="color: #94a3b8; font-size: 15px;">Este estudiante aún no tiene métricas registradas. Complete una evaluación para comenzar a ver datos.</p>
                </div>
            </div>
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

    def _generate_timeline_chartjs(self, df, student):
        """Timeline con Chart.js - estilo profesional."""
        if df.empty:
            return '<div class="alert alert-info">No hay datos temporales disponibles</div>'
        
        df_numeric = df[df['value_type'] == 'numeric'].copy()
        if df_numeric.empty:
            return '<div class="alert alert-info">No hay métricas numéricas para graficar</div>'
        
        # Paleta profesional estilo Stripe/Linear
        colors = [
            '#3b82f6',  # Blue
            '#10b981',  # Green
            '#f59e0b',  # Amber
            '#8b5cf6',  # Purple
            '#ef4444',  # Red
            '#06b6d4',  # Cyan
            '#ec4899',  # Pink
            '#f97316',  # Orange
        ]
        
        datasets = []
        for idx, metric in enumerate(df_numeric['metric_label'].unique()[:5]):
            df_metric = df_numeric[df_numeric['metric_label'] == metric].sort_values('timestamp')
            
            data_points = [
                {'x': row['timestamp'].strftime('%Y-%m-%d %H:%M:%S'), 'y': float(row['value'])}
                for _, row in df_metric.iterrows()
            ]
            
            color = colors[idx % len(colors)]
            datasets.append({
                'label': metric,
                'data': data_points,
                'borderColor': color,
                'backgroundColor': 'transparent',
                'borderWidth': 2,
                'tension': 0.3,
                'fill': False,
                'pointRadius': 4,
                'pointHoverRadius': 6,
                'pointBackgroundColor': color,
                'pointBorderColor': '#ffffff',
                'pointBorderWidth': 2
            })
        
        chart_id = f'timeline_{student.id}'
        datasets_json = json.dumps(datasets)
        
        return f'''
        <div class="card">
            <div class="card-header">
                <h5 class="card-title">Evolución Temporal</h5>
                <p class="card-subtitle">Seguimiento longitudinal de métricas</p>
            </div>
            <div class="card-body">
                <canvas id="{chart_id}" style="max-height: 350px;"></canvas>
            </div>
        </div>
        
        <script>
        new Chart(document.getElementById('{chart_id}'), {{
            type: 'line',
            data: {{
                datasets: {datasets_json}
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                interaction: {{
                    mode: 'index',
                    intersect: false
                }},
                plugins: {{
                    legend: {{
                        display: true,
                        position: 'bottom',
                        labels: {{
                            usePointStyle: true,
                            padding: 16,
                            font: {{
                                size: 13,
                                family: "'Inter', sans-serif",
                                weight: '500'
                            }},
                            color: '#64748b'
                        }}
                    }},
                    tooltip: {{
                        backgroundColor: '#1e293b',
                        padding: 12,
                        titleFont: {{
                            size: 13,
                            family: "'Inter', sans-serif",
                            weight: '600'
                        }},
                        bodyFont: {{
                            size: 13,
                            family: "'Inter', sans-serif"
                        }},
                        cornerRadius: 6,
                        displayColors: true,
                        borderColor: '#e5e7eb',
                        borderWidth: 1,
                        callbacks: {{
                            title: function(context) {{
                                let date = new Date(context[0].parsed.x);
                                return date.toLocaleDateString('es-ES', {{day: '2-digit', month: 'short', year: 'numeric'}});
                            }}
                        }}
                    }}
                }},
                scales: {{
                    x: {{
                        type: 'time',
                        time: {{
                            unit: 'day',
                            displayFormats: {{
                                day: 'dd/MM'
                            }}
                        }},
                        grid: {{
                            display: false,
                            drawBorder: false
                        }},
                        ticks: {{
                            font: {{
                                size: 12,
                                family: "'Inter', sans-serif"
                            }},
                            color: '#94a3b8'
                        }}
                    }},
                    y: {{
                        beginAtZero: true,
                        grid: {{
                            color: '#f1f5f9',
                            drawBorder: false
                        }},
                        ticks: {{
                            font: {{
                                size: 12,
                                family: "'Inter', sans-serif"
                            }},
                            color: '#94a3b8'
                        }}
                    }}
                }},
                animation: {{
                    duration: 750,
                    easing: 'easeInOutCubic'
                }}
            }}
        }});
        </script>
        '''

    def _generate_evolution_chartjs(self, df, student):
        """Gráficos individuales con contexto del grupo - estilo profesional."""
        if df.empty:
            return ''
        
        df_numeric = df[df['value_type'] == 'numeric'].copy()
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
            change_color = '#10b981' if percent_change > 0 else '#ef4444' if percent_change < 0 else '#94a3b8'
            change_text = f"<span style='color: {change_color}; font-weight: 600;'>{change_icon} {abs(percent_change):.1f}%</span>"
            
            # Colores semáforo por cada barra
            colors = [self._get_semaphore_color(v) for v in values]
            
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
            
            # Crear datasets
            datasets = [
                {
                    'label': 'Estudiante',
                    'data': values,
                    'backgroundColor': colors,
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
                    'borderColor': '#94a3b8',
                    'backgroundColor': 'transparent',
                    'borderWidth': 2,
                    'borderDash': [5, 5],
                    'pointRadius': 4,
                    'pointBackgroundColor': '#94a3b8',
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
                        <p style="font-size: 11px; color: #94a3b8; margin: 4px 0 0 0;">
                            Evolución con contexto del grupo · Cambio: {change_text}
                        </p>
                    </div>
                    <div class="card-body">
                        <canvas id="{chart_id}" height="200"></canvas>
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
                                color: '#64748b'
                            }}
                        }},
                        tooltip: {{
                            backgroundColor: '#1e293b',
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
                                color: '#94a3b8'
                            }}
                        }},
                        y: {{
                            beginAtZero: true,
                            max: 100,
                            grid: {{
                                color: '#f1f5f9',
                                drawBorder: false
                            }},
                            ticks: {{
                                font: {{
                                    size: 11,
                                    family: "'Inter', sans-serif"
                                }},
                                color: '#94a3b8'
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
    
    def _get_semaphore_color(self, value):
        """Retorna color semáforo según valor normalizado 0-100."""
        if value >= 80:
            return '#10b981'  # Verde - Excelente
        elif value >= 60:
            return '#3b82f6'  # Azul - Normal
        elif value >= 40:
            return '#f59e0b'  # Ámbar - Atención
        else:
            return '#ef4444'  # Rojo - Crítico
    
    def _get_group_context_data(self, student, df_student):
        """Obtiene datos del grupo para contextualizar el perfil individual."""
        if not student.academic_group_id:
            return {}
        
        group_id = student.academic_group_id.id
        group_data = {}
        
        # Para cada métrica del estudiante, obtener valores del grupo
        for metric_name in df_student['metric_name'].unique():
            MetricValue = self.env['aulametrics.metric_value']
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
            MetricValue = self.env['aulametrics.metric_value']
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
        """Genera radar chart si hay 3+ métricas numéricas."""
        if df.empty:
            return ''
        
        df_numeric = df[df['value_type'] == 'numeric'].copy()
        if df_numeric.empty:
            return ''
        
        # Obtener último valor de cada métrica
        latest_by_metric = df_numeric.groupby('metric_label').last().reset_index()
        
        # Necesitamos al menos 3 métricas
        if len(latest_by_metric) < 3:
            return ''
        
        # Obtener contexto del grupo y centro
        group_data = self._get_group_context_data(student, df_numeric)
        center_data = self._get_center_context_data(student, df_numeric)
        
        # Preparar datos del estudiante
        student_labels = []
        student_values = []
        group_values = []
        center_values = []
        
        for _, row in latest_by_metric.iterrows():
            student_labels.append(row['metric_label'])
            student_values.append(float(row['value']))
            
            # Media del grupo para esta métrica
            metric_name = row['metric_name']
            if metric_name in group_data:
                group_values.append(group_data[metric_name]['mean'])
            else:
                group_values.append(None)
            
            # Media del centro para esta métrica
            if metric_name in center_data:
                center_values.append(center_data[metric_name]['mean'])
            else:
                center_values.append(None)
        
        chart_id = f'radar_{student.id}'
        
        datasets = [
            {
                'label': student.name,
                'data': student_values,
                'backgroundColor': 'rgba(59, 130, 246, 0.2)',
                'borderColor': '#3b82f6',
                'borderWidth': 2,
                'pointBackgroundColor': '#3b82f6',
                'pointBorderColor': '#ffffff',
                'pointBorderWidth': 2,
                'pointRadius': 4,
                'pointHoverRadius': 6
            }
        ]
        
        # Agregar dataset del grupo si hay datos
        if any(v is not None for v in group_values):
            datasets.append({
                'label': 'Media grupo',
                'data': group_values,
                'backgroundColor': 'rgba(148, 163, 184, 0.1)',
                'borderColor': '#94a3b8',
                'borderWidth': 2,
                'borderDash': [5, 5],
                'pointBackgroundColor': '#94a3b8',
                'pointBorderColor': '#ffffff',
                'pointBorderWidth': 2,
                'pointRadius': 3,
                'pointHoverRadius': 5
            })
        
        # Agregar dataset del centro si hay datos
        if any(v is not None for v in center_values):
            datasets.append({
                'label': 'Media centro',
                'data': center_values,
                'backgroundColor': 'rgba(16, 185, 129, 0.05)',
                'borderColor': '#10b981',
                'borderWidth': 2,
                'borderDash': [2, 2],
                'pointBackgroundColor': '#10b981',
                'pointBorderColor': '#ffffff',
                'pointBorderWidth': 2,
                'pointRadius': 3,
                'pointHoverRadius': 5
            })
        
        return f'''
        <div class="card">
            <div class="card-header">
                <h5 class="card-title">Perfil Multidimensional</h5>
                <p class="card-subtitle">Comparativa visual con grupo y centro</p>
            </div>
            <div class="card-body">
                <canvas id="{chart_id}" height="220"></canvas>
            </div>
        </div>
        
        <script>
        new Chart(document.getElementById('{chart_id}'), {{
            type: 'radar',
            data: {{
                labels: {json.dumps(student_labels)},
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
                            padding: 16,
                            font: {{
                                size: 13,
                                family: "'Inter', sans-serif",
                                weight: '500'
                            }},
                            color: '#64748b'
                        }}
                    }},
                    tooltip: {{
                        backgroundColor: '#1e293b',
                        padding: 12,
                        cornerRadius: 6,
                        titleFont: {{
                            family: "'Inter', sans-serif",
                            size: 13,
                            weight: '600'
                        }},
                        bodyFont: {{
                            family: "'Inter', sans-serif",
                            size: 12
                        }},
                        callbacks: {{
                            label: function(context) {{
                                return context.dataset.label + ': ' + context.parsed.r.toFixed(1) + ' pts';
                            }}
                        }}
                    }}
                }},
                scales: {{
                    r: {{
                        beginAtZero: true,
                        max: 100,
                        ticks: {{
                            stepSize: 20,
                            font: {{
                                size: 11,
                                family: "'Inter', sans-serif"
                            }},
                            color: '#94a3b8'
                        }},
                        grid: {{
                            color: '#e5e7eb'
                        }},
                        pointLabels: {{
                            font: {{
                                size: 12,
                                family: "'Inter', sans-serif",
                                weight: '500'
                            }},
                            color: '#475569'
                        }}
                    }}
                }},
                animation: {{
                    duration: 800,
                    easing: 'easeInOutCubic'
                }}
            }}
        }});
        </script>
        '''

    def _build_profile_html_chartjs(self, student, role_info, kpis, timeline, evolution, radar, alerts, participations, qualitative=''):
        """HTML del perfil con Chart.js - diseño profesional."""
        role_badge = self._get_role_badge(role_info)
        group_name = student.academic_group_id.name if student.academic_group_id else 'Sin grupo'
        
        return f"""
        <!DOCTYPE html>
        <html lang="es">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Perfil de {student.name} - AulaMetrics</title>
            <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
            <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
            <script src="https://cdn.jsdelivr.net/npm/chartjs-adapter-date-fns@3.0.0/dist/chartjs-adapter-date-fns.bundle.min.js"></script>
            {self._profile_styles_chartjs()}
        </head>
        <body>
            <div class="container">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 32px;">
                    <div>
                        <h1>{student.name}</h1>
                        <p class="subtitle">{group_name} · Visualizado el {fields.Date.today().strftime('%d/%m/%Y')}</p>
                    </div>
                    <div>
                        {role_badge}
                        <a href="/aulametrics/students" style="margin-left: 12px; padding: 8px 16px; background: white; border: 1px solid #e5e7eb; border-radius: 6px; text-decoration: none; color: #64748b; font-weight: 500; font-size: 14px;">
                            <i class="fa-solid fa-users"></i> Lista
                        </a>
                    </div>
                </div>
                
                <div class="kpi-grid">
                    {kpis}
                </div>
                
                {radar if radar else ''}
                
                {evolution}
                
                {timeline}
                
                <div class="row">
                    <div class="col-lg-6">
                        <div class="card">
                            <div class="card-header">
                                <h5 class="card-title">Alertas Activas</h5>
                                <p class="card-subtitle">Puntos de atención identificados</p>
                            </div>
                            <div class="card-body">
                                {alerts}
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
            </div>
        </body>
        </html>
        """

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
                background-color: #fafbfc;
                color: #0f172a;
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
                color: #0f172a;
                margin-bottom: 8px;
                letter-spacing: -0.5px;
            }
            
            .subtitle {
                color: #64748b;
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
                background: white;
                border: 1px solid #e5e7eb;
                border-radius: 10px;
                padding: 24px;
                transition: all 0.2s ease;
            }
            
            .kpi-card:hover {
                transform: translateY(-2px);
                box-shadow: 0 4px 12px rgba(0,0,0,0.08);
                border-color: #d1d5db;
            }
            
            .kpi-label {
                font-size: 13px;
                font-weight: 500;
                color: #64748b;
                text-transform: uppercase;
                letter-spacing: 0.5px;
                margin-bottom: 8px;
            }
            
            .kpi-value {
                font-size: 36px;
                font-weight: 700;
                color: #0f172a;
                line-height: 1;
                margin-bottom: 4px;
            }
            
            .kpi-description {
                font-size: 13px;
                color: #94a3b8;
                font-weight: 400;
            }
            
            .card {
                background: white;
                border: 1px solid #e5e7eb;
                border-radius: 10px;
                margin-bottom: 24px;
                overflow: hidden;
                box-shadow: 0 1px 3px rgba(0,0,0,0.04);
            }
            
            .card-header {
                padding: 20px 24px;
                border-bottom: 1px solid #f1f5f9;
                background: white;
            }
            
            .card-title {
                font-size: 18px;
                font-weight: 600;
                color: #0f172a;
                margin: 0;
            }
            
            .card-title-sm {
                font-size: 15px;
                font-weight: 600;
                color: #0f172a;
                margin: 0;
            }
            
            .card-subtitle {
                font-size: 13px;
                color: #64748b;
                margin: 4px 0 0 0;
                font-weight: 400;
            }
            
            .card-body {
                padding: 24px;
            }
            
            .alert {
                background: #f8fafc;
                border: 1px solid #e2e8f0;
                border-radius: 8px;
                padding: 16px 20px;
                color: #475569;
                font-size: 14px;
                margin-bottom: 20px;
            }
            
            .alert-info {
                background: #eff6ff;
                border-color: #bfdbfe;
                color: #1e40af;
            }
            
            .alert-warning {
                background: #fef3c7;
                border-color: #fde68a;
                color: #92400e;
            }
            
            .alert-danger {
                background: #fee2e2;
                border-color: #fecaca;
                color: #991b1b;
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
                background: #dbeafe;
                color: #1e40af;
            }
            
            .badge-warning {
                background: #fef3c7;
                color: #92400e;
            }
            
            .badge-danger {
                background: #fee2e2;
                color: #991b1b;
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
                background: #f8fafc;
                border-bottom: 1px solid #e5e7eb;
            }
            
            th {
                padding: 12px 16px;
                text-align: left;
                font-weight: 600;
                color: #475569;
                font-size: 13px;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }
            
            td {
                padding: 14px 16px;
                border-bottom: 1px solid #f1f5f9;
                color: #334155;
            }
            
            tr:last-child td {
                border-bottom: none;
            }
            
            tbody tr:hover {
                background: #fafbfc;
            }
            
            ul {
                list-style: none;
                padding: 0;
            }
            
            li {
                padding: 12px 0;
                border-bottom: 1px solid #f1f5f9;
                color: #334155;
                font-size: 14px;
            }
            
            li:last-child {
                border-bottom: none;
            }
        </style>
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
