# -*- coding: utf-8 -*-
"""
Dashboard Charts - Generación de dashboard con métricas filtradas
"""
from odoo import models, api, fields
import pandas as pd
import plotly.graph_objects as go


class DashboardCharts(models.TransientModel):
    _name = 'aulametrics.dashboard.charts'
    _description = 'Generador de Dashboard de Métricas'

    @api.model
    def generate_dashboard(self, filters=None, role_info=None):
        """
        Genera el dashboard de métricas con filtros dinámicos.
        
        Args:
            filters (dict): Filtros aplicados {metric_names, date_from, date_to, group_ids, evaluation_ids}
            role_info (dict): Información de rol del usuario
        
        Returns:
            str: HTML completo del dashboard
        """
        if filters is None:
            filters = {}
        if role_info is None:
            role_info = {'role': 'admin', 'anonymize_students': False}

        # Obtener opciones disponibles para los filtros
        available_metrics = self._get_available_metrics(filters, role_info)
        available_groups = self._get_available_groups(role_info)
        available_evaluations = self._get_available_evaluations(role_info)

        # Si no hay datos disponibles, mostrar mensaje
        if not available_metrics:
            return self._build_html_empty(
                available_metrics, available_groups, available_evaluations, 
                filters, role_info
            )

        # Consultar valores de métricas según filtros
        metric_values = self._query_metric_values(filters, role_info)
        
        if not metric_values:
            return self._build_html_empty(
                available_metrics, available_groups, available_evaluations,
                filters, role_info
            )

        # Preparar DataFrame
        df = self._prepare_dataframe(metric_values, role_info)
        
        # Generar gráficos
        charts = self._generate_charts(df, filters, available_metrics)
        
        # Generar KPIs
        kpi_html = self._generate_kpis(df, filters, role_info)
        
        # Construir HTML final
        return self._build_html(
            available_metrics, available_groups, available_evaluations, 
            filters, role_info, kpi_html, charts
        )

    def _get_available_metrics(self, filters, role_info):
        """Obtiene las métricas únicas disponibles en metric_value."""
        MetricValue = self.env['aulametrics.metric_value']
        
        # Dominio base
        domain = []
        
        # Filtrar por grupos si rol tutor
        if role_info.get('role') == 'tutor':
            allowed_groups = role_info.get('allowed_group_ids', [])
            if allowed_groups:
                domain.append(('academic_group_id', 'in', allowed_groups))
            else:
                return []  # Tutor sin grupos asignados
        
        # Filtrar por evaluaciones si se especifica
        if filters.get('evaluation_ids'):
            domain.append(('evaluation_id', 'in', filters['evaluation_ids']))
        
        # Filtrar por fechas
        if filters.get('date_from'):
            domain.append(('timestamp', '>=', fields.Datetime.to_string(filters['date_from'])))
        if filters.get('date_to'):
            domain.append(('timestamp', '<=', fields.Datetime.to_string(filters['date_to'])))
        
        # Agrupar por metric_name y obtener labels
        result = MetricValue.read_group(
            domain,
            ['metric_name', 'metric_label'],
            ['metric_name']
        )
        
        # Obtener labels únicos y detectar tipo
        metrics = []
        seen = set()
        for r in result:
            name = r['metric_name']
            if name not in seen:
                seen.add(name)
                # Buscar un registro para obtener el label y detectar tipo
                sample = MetricValue.search([
                    ('metric_name', '=', name)
                ] + domain, limit=1)
                
                # Detectar tipo según qué campo tiene valor
                if sample.value_float:
                    metric_type = 'numeric'
                elif sample.value_json:
                    metric_type = 'json'
                elif sample.value_text:
                    metric_type = 'text'
                else:
                    metric_type = 'numeric'  # default
                
                metrics.append({
                    'name': name,
                    'label': sample.metric_label or name,
                    'type': metric_type
                })
        
        return sorted(metrics, key=lambda x: x['label'])

    def _get_available_groups(self, role_info):
        """Obtiene los grupos académicos disponibles según el rol."""
        AcademicGroup = self.env['aulametrics.academic_group']
        
        if role_info.get('role') == 'tutor':
            allowed = role_info.get('allowed_group_ids', [])
            groups = AcademicGroup.browse(allowed)
        else:
            groups = AcademicGroup.search([])
        
        return [{'id': g.id, 'name': g.name, 'course': g.course_level} for g in groups]

    def _get_available_evaluations(self, role_info):
        """Obtiene las evaluaciones disponibles según el rol."""
        Evaluation = self.env['aulametrics.evaluation']
        
        # Las record rules ya aplican filtros, simplemente buscamos todas
        evaluations = Evaluation.search([])
        
        return [{'id': e.id, 'name': e.name, 'state': e.state} for e in evaluations]

    def _query_metric_values(self, filters, role_info):
        """Consulta los valores de métricas aplicando todos los filtros."""
        MetricValue = self.env['aulametrics.metric_value']
        
        domain = []
        
        # Filtro por métricas específicas
        if filters.get('metric_names'):
            domain.append(('metric_name', 'in', filters['metric_names']))
        
        # Filtro por grupos académicos
        if filters.get('group_ids'):
            domain.append(('academic_group_id', 'in', filters['group_ids']))
        elif role_info.get('role') == 'tutor':
            # Tutores: solo sus grupos
            allowed = role_info.get('allowed_group_ids', [])
            if allowed:
                domain.append(('academic_group_id', 'in', allowed))
            else:
                return self.env['aulametrics.metric_value']
        
        # Filtro por evaluaciones
        if filters.get('evaluation_ids'):
            domain.append(('evaluation_id', 'in', filters['evaluation_ids']))
        
        # Filtro por fechas
        if filters.get('date_from'):
            domain.append(('timestamp', '>=', fields.Datetime.to_string(filters['date_from'])))
        if filters.get('date_to'):
            domain.append(('timestamp', '<=', fields.Datetime.to_string(filters['date_to'])))
        
        return MetricValue.search(domain)

    def _prepare_dataframe(self, metric_values, role_info):
        """Convierte metric_values a un DataFrame de pandas para análisis."""
        data = []
        
        anonymize = role_info.get('anonymize_students', False)
        
        for mv in metric_values:
            student = mv.student_id
            academic_group = mv.academic_group_id
            evaluation = mv.evaluation_id
            
            # Datos del estudiante
            student_name = "Anónimo" if anonymize else student.name
            student_id_val = "***" if anonymize else str(student.id)
            
            # Detectar tipo de métrica según qué campo tiene valor
            if mv.value_float:
                metric_type = 'numeric'
                value_numeric = mv.value_float
                value_json = None
                value_text = None
            elif mv.value_json:
                metric_type = 'json'
                value_numeric = None
                value_json = mv.value_json
                value_text = None
            elif mv.value_text:
                metric_type = 'text'
                value_numeric = None
                value_json = None
                value_text = mv.value_text
            else:
                continue  # Saltar si no tiene ningún valor
            
            row = {
                'metric_name': mv.metric_name,
                'metric_label': mv.metric_label,
                'metric_type': metric_type,
                'value_numeric': value_numeric,
                'value_json': value_json,
                'value_text': value_text,
                'student_id': student_id_val,
                'student_name': student_name,
                'student_gender': student.gender if student.gender else 'Otro',
                'group_id': academic_group.id if academic_group else None,
                'group_name': academic_group.name if academic_group else 'Sin grupo',
                'curso': academic_group.course_level if academic_group and academic_group.course_level else 'Sin curso',
                'evaluation_id': evaluation.id if evaluation else None,
                'evaluation_name': evaluation.name if evaluation else 'Sin evaluación',
                'completed_at': mv.timestamp,
            }
            data.append(row)
        
        return pd.DataFrame(data)

    def _generate_charts(self, df, filters, available_metrics):
        """Genera gráficos según las métricas presentes en el DataFrame."""
        charts = []
        
        # Obtener métricas únicas en el DataFrame
        grouped = df.groupby(['metric_name', 'metric_label', 'metric_type']).size().reset_index(name='count')
        
        for _, row in grouped.iterrows():
            metric_info = {
                'name': row['metric_name'],
                'label': row['metric_label'],
                'type': row['metric_type']
            }
            
            chart_html = self._generate_chart_by_metric_type(metric_info, df)
            if chart_html:
                charts.append(chart_html)
        
        return charts

    def _generate_chart_by_metric_type(self, metric_info, df):
        """Genera el gráfico apropiado según el tipo de métrica."""
        metric_name = metric_info['name']
        metric_label = metric_info['label']
        metric_type = metric_info['type']
        
        df_metric = df[df['metric_name'] == metric_name].copy()
        
        if metric_type == 'numeric':
            return self._chart_numeric_metric(df_metric, metric_label)
        elif metric_type == 'json':
            return self._chart_json_metric(df_metric, metric_label)
        elif metric_type == 'text':
            return self._chart_text_metric(df_metric, metric_label)
        
        return ''

    def _chart_numeric_metric(self, df, label):
        """Gráfico de caja (box plot) para métricas numéricas agrupadas por curso."""
        if df.empty or df['value_numeric'].isna().all():
            return ''
        
        # Agrupar por curso
        cursos = df['curso'].unique()
        
        fig = go.Figure()
        for curso in sorted(cursos):
            df_curso = df[df['curso'] == curso]
            fig.add_trace(go.Box(
                y=df_curso['value_numeric'],
                name=curso,
                boxmean='sd'
            ))
        
        fig.update_layout(
            title=f'📊 {label}',
            yaxis_title='Puntuación',
            xaxis_title='Curso',
            height=400,
            showlegend=False,
            template='plotly_white'
        )
        
        return fig.to_html(full_html=False, include_plotlyjs='cdn', div_id=f'chart_{label.replace(" ", "_")}')

    def _chart_json_metric(self, df, label):
        """Gráfico de barras para métricas JSON (respuestas múltiples)."""
        if df.empty:
            return ''
        
        # Contar frecuencias de respuestas
        import json
        responses = []
        for val in df['value_json'].dropna():
            try:
                parsed = json.loads(val) if isinstance(val, str) else val
                if isinstance(parsed, list):
                    responses.extend(parsed)
                elif isinstance(parsed, str):
                    responses.append(parsed)
            except:
                continue
        
        if not responses:
            return ''
        
        from collections import Counter
        counts = Counter(responses)
        
        fig = go.Figure(data=[
            go.Bar(
                x=list(counts.keys()),
                y=list(counts.values()),
                marker_color='#667eea'
            )
        ])
        
        fig.update_layout(
            title=f'📊 {label}',
            xaxis_title='Respuesta',
            yaxis_title='Frecuencia',
            height=400,
            template='plotly_white'
        )
        
        return fig.to_html(full_html=False, include_plotlyjs='cdn', div_id=f'chart_{label.replace(" ", "_")}')

    def _chart_text_metric(self, df, label):
        """Tabla simple para métricas de texto."""
        if df.empty:
            return ''
        
        # Mostrar solo primeros 50 registros
        df_sample = df[['student_name', 'value_text']].head(50)
        
        return f"""
        <div class="card mb-4">
            <div class="card-header">
                <h5>📝 {label}</h5>
            </div>
            <div class="card-body">
                <div style="max-height: 400px; overflow-y: auto;">
                    {df_sample.to_html(index=False, classes='table table-striped', border=0)}
                </div>
            </div>
        </div>
        """

    def _generate_kpis(self, df, filters, role_info):
        """Genera tarjetas KPI con estadísticas agregadas."""
        kpis = []
        
        # Total de estudiantes
        total_students = df['student_id'].nunique()
        kpis.append(f"""
        <div class="kpi-card">
            <div class="kpi-icon-bg"><i class="fa-solid fa-users"></i></div>
            <div class="kpi-label">Estudiantes</div>
            <div class="kpi-number">{total_students}</div>
        </div>
        """)
        
        # Total de grupos
        total_groups = df['group_id'].nunique()
        kpis.append(f"""
        <div class="kpi-card">
            <div class="kpi-icon-bg"><i class="fa-solid fa-user-group"></i></div>
            <div class="kpi-label">Grupos</div>
            <div class="kpi-number">{total_groups}</div>
        </div>
        """)
        
        # Total de evaluaciones
        total_evals = df['evaluation_id'].nunique()
        kpis.append(f"""
        <div class="kpi-card">
            <div class="kpi-icon-bg"><i class="fa-solid fa-clipboard-check"></i></div>
            <div class="kpi-label">Evaluaciones</div>
            <div class="kpi-number">{total_evals}</div>
        </div>
        """)
        
        # Total de métricas
        total_metrics = df['metric_name'].nunique()
        kpis.append(f"""
        <div class="kpi-card">
            <div class="kpi-icon-bg"><i class="fa-solid fa-chart-line"></i></div>
            <div class="kpi-label">Métricas</div>
            <div class="kpi-number">{total_metrics}</div>
        </div>
        """)
        
        return '\n'.join(kpis)

    def _build_html_empty(self, metrics, groups, evaluations, filters, role_info):
        """HTML cuando no hay datos disponibles."""
        role_badge = self._get_role_badge(role_info)
        filter_controls = self._build_filter_controls(metrics, groups, evaluations, filters)
        
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Dashboard de Métricas - AulaMetrics</title>
            <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
            <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
            <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
            {self._styles()}
        </head>
        <body>
            {self._header(role_badge, role_info)}
            <div class="container-fluid mt-4">
                {filter_controls}
                <div class="text-center py-5">
                    <i class="fa-solid fa-chart-line fa-5x text-muted mb-4"></i>
                    <h3 class="text-muted">No hay datos disponibles para mostrar</h3>
                    <p class="text-muted">Ajusta los filtros para ver resultados</p>
                </div>
            </div>
            <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
            {self._scripts()}
        </body>
        </html>
        """

    def _build_html(self, metrics, groups, evaluations, filters, role_info, kpi_html, charts):
        """Construye el HTML completo del dashboard."""
        role_badge = self._get_role_badge(role_info)
        filter_controls = self._build_filter_controls(metrics, groups, evaluations, filters)
        
        charts_html = '\n'.join(charts) if charts else '<p class="text-muted">No hay gráficos para mostrar</p>'
        
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Dashboard de Métricas - AulaMetrics</title>
            <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
            <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
            <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
            <script src="https://cdn.plot.ly/plotly-2.26.0.min.js"></script>
            {self._styles()}
        </head>
        <body>
            {self._header(role_badge, role_info)}
            <div class="container-fluid mt-4">
                {filter_controls}
                
                <div class="kpi-container my-4">
                    {kpi_html}
                </div>
                
                <div class="charts-container">
                    {charts_html}
                </div>
            </div>
            <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
            {self._scripts()}
        </body>
        </html>
        """

    def _get_role_badge(self, role_info):
        """Genera el badge de rol del usuario."""
        role = role_info.get('role', 'tutor')
        badges = {
            'admin': '<span class="badge bg-danger"><i class="fa-solid fa-shield-halved"></i> Administrador</span>',
            'counselor': '<span class="badge bg-primary"><i class="fa-solid fa-user-tie"></i> Orientador/a</span>',
            'management': '<span class="badge bg-warning text-dark"><i class="fa-solid fa-briefcase"></i> Equipo Directivo</span>',
            'tutor': '<span class="badge bg-success"><i class="fa-solid fa-chalkboard-user"></i> Tutor/a</span>',
        }
        return badges.get(role, '')

    def _build_filter_controls(self, metrics, groups, evaluations, filters):
        """Construye los controles de filtrado."""
        # Checkboxes de métricas
        metric_checks = ''
        selected_metrics = filters.get('metric_names', [])
        for m in metrics:
            checked = 'checked' if m['name'] in selected_metrics or not selected_metrics else ''
            metric_checks += f"""
            <div class="filter-checkbox">
                <input class="form-check-input metric-check" type="checkbox" 
                       id="metric_{m['name']}" name="metric_{m['name']}" value="{m['name']}" {checked}>
                <label class="form-check-label" for="metric_{m['name']}">{m['label']}</label>
            </div>
            """

        # Checkboxes de grupos
        groups_checks = ''
        selected_groups = filters.get('group_ids', [])
        for g in groups:
            checked = 'checked' if g['id'] in selected_groups or not selected_groups else ''
            
            groups_checks += f"""
            <div class="filter-checkbox">
                <input class="form-check-input group-check" type="checkbox" 
                       id="group_{g['id']}" name="group_{g['id']}" value="{g['id']}" {checked}>
                <label class="form-check-label" for="group_{g['id']}">{g['name']}</label>
            </div>
            """

        # Checkboxes de evaluaciones
        eval_checks = ''
        selected_evals = filters.get('evaluation_ids', [])
        for e in evaluations:
            checked = 'checked' if e['id'] in selected_evals or not selected_evals else ''
            
            eval_checks += f"""
            <div class="filter-checkbox">
                <input class="form-check-input eval-check" type="checkbox" 
                       id="eval_{e['id']}" name="eval_{e['id']}" value="{e['id']}" {checked}>
                <label class="form-check-label" for="eval_{e['id']}">{e['name']}</label>
            </div>
            """

        # Fechas
        date_from = filters.get('date_from', '')
        date_to = filters.get('date_to', '')
        if date_from:
            date_from = date_from.strftime('%Y-%m-%d') if hasattr(date_from, 'strftime') else str(date_from)
        if date_to:
            date_to = date_to.strftime('%Y-%m-%d') if hasattr(date_to, 'strftime') else str(date_to)

        # Calcular cuántos están seleccionados
        num_metrics = len(selected_metrics) if selected_metrics else len(metrics)
        num_groups = len(selected_groups) if selected_groups else len(groups)
        num_evals = len(selected_evals) if selected_evals else len(evaluations)

        return f"""
        <div class="filter-panel mb-4">
            <div class="filter-header">
                <div>
                    <i class="fa-solid fa-filter me-2"></i>
                    <strong>Filtros</strong>
                    <span class="badge bg-light text-dark ms-2">{num_metrics} métricas</span>
                    <span class="badge bg-light text-dark ms-1">{num_groups} grupos</span>
                    <span class="badge bg-light text-dark ms-1">{num_evals} evaluaciones</span>
                </div>
                <button type="button" class="btn btn-sm btn-outline-secondary" onclick="toggleFilters()">
                    <i class="fa-solid fa-chevron-down" id="toggleIcon"></i>
                </button>
            </div>
            <div class="filter-content collapse" id="filterContent">
                <form id="hub-filters" method="get" action="/aulametrics/dashboard">
                    <div class="row g-3">
                        <!-- Métricas -->
                        <div class="col-md-6">
                            <div class="filter-section">
                                <label class="form-label">
                                    <i class="fa-solid fa-chart-line me-2"></i>Métricas
                                    <div>
                                        <button type="button" class="btn btn-link btn-sm" onclick="selectAllMetrics()">Todas</button>
                                        <button type="button" class="btn btn-link btn-sm" onclick="selectNoneMetrics()">Ninguna</button>
                                    </div>
                                </label>
                                <div class="checkbox-grid">
                                    {metric_checks}
                                </div>
                            </div>
                        </div>
                        
                        <!-- Grupos -->
                        <div class="col-md-6">
                            <div class="filter-section">
                                <label class="form-label">
                                    <i class="fa-solid fa-user-group me-2"></i>Grupos
                                    <div>
                                        <button type="button" class="btn btn-link btn-sm" onclick="selectAllGroups()">Todos</button>
                                        <button type="button" class="btn btn-link btn-sm" onclick="selectNoneGroups()">Ninguno</button>
                                    </div>
                                </label>
                                <div class="checkbox-grid">
                                    {groups_checks}
                                </div>
                            </div>
                        </div>
                        
                        <!-- Evaluaciones -->
                        <div class="col-12">
                            <div class="filter-section">
                                <label class="form-label">
                                    <i class="fa-solid fa-clipboard-check me-2"></i>Evaluaciones
                                    <div>
                                        <button type="button" class="btn btn-link btn-sm" onclick="selectAllEvals()">Todas</button>
                                        <button type="button" class="btn btn-link btn-sm" onclick="selectNoneEvals()">Ninguna</button>
                                    </div>
                                </label>
                                <div class="checkbox-grid">
                                    {eval_checks}
                                </div>
                            </div>
                        </div>
                        
                        <!-- Fechas -->
                        <div class="col-12">
                            <div class="filter-section">
                                <label class="form-label">
                                    <i class="fa-solid fa-calendar me-2"></i>Rango de fechas
                                    <button type="button" class="btn btn-link btn-sm" onclick="clearDates()">
                                        <i class="fa-solid fa-xmark"></i> Limpiar
                                    </button>
                                </label>
                                <div class="row g-2">
                                    <div class="col-md-6">
                                        <input type="date" class="form-control" id="date_from" name="date_from" value="{date_from}" placeholder="Desde">
                                    </div>
                                    <div class="col-md-6">
                                        <input type="date" class="form-control" id="date_to" name="date_to" value="{date_to}" placeholder="Hasta">
                                    </div>
                                </div>
                            </div>
                        </div>
                        
                        <!-- Botón Aplicar -->
                        <div class="col-12">
                            <button type="submit" class="btn btn-primary btn-lg w-100">
                                <i class="fa-solid fa-magnifying-glass me-2"></i>Aplicar Filtros
                            </button>
                        </div>
                    </div>
                    
                    <!-- Hidden inputs para enviar datos -->
                    <input type="hidden" name="metric_names" id="metric_names_input">
                    <input type="hidden" name="group_ids" id="group_ids_input">
                    <input type="hidden" name="evaluation_ids" id="evaluation_ids_input">
                </form>
            </div>
        </div>
        """

    def _styles(self):
        """Estilos CSS del dashboard."""
        return """
    <style>
        body { background: #f1f5f9; font-family: 'Inter', sans-serif; padding-bottom: 60px; color: #1e293b; }
        .dashboard-header { background: white; padding: 1.5rem 2rem; border-bottom: 1px solid #e2e8f0; margin-bottom: 2rem; display: flex; justify-content: space-between; align-items: center; box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.05); }
        .header-title h1 { font-size: 1.5rem; font-weight: 700; margin: 0; color: #0f172a; }
        .header-meta { color: #64748b; font-size: 0.875rem; margin-top: 4px; }
        
        .filter-panel { background: white; border-radius: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); overflow: hidden; }
        .filter-header { 
            padding: 1.25rem 1.5rem; 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-weight: 600;
        }
        .filter-header .badge { font-size: 0.75rem; font-weight: 600; }
        .filter-header .btn-outline-secondary { 
            color: white; 
            border-color: rgba(255,255,255,0.5); 
            background: rgba(255,255,255,0.1);
        }
        .filter-header .btn-outline-secondary:hover { 
            background: rgba(255,255,255,0.2); 
            border-color: white; 
        }
        
        .filter-content { 
            padding: 1.5rem; 
            background: #f8fafc;
            animation: slideDown 0.3s ease-out;
        }
        
        @keyframes slideDown {
            from { opacity: 0; transform: translateY(-10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        
        .filter-section {
            background: white;
            padding: 1.25rem;
            border-radius: 8px;
            border: 1px solid #e2e8f0;
            height: 100%;
        }
        
        .filter-section .form-label {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 0.75rem;
            font-size: 0.95rem;
        }
        
        .filter-section .btn-link {
            padding: 0 0.5rem;
            text-decoration: none;
            color: #6366f1;
            font-size: 0.8rem;
        }
        .filter-section .btn-link:hover {
            color: #4f46e5;
            text-decoration: underline;
        }
        
        .checkbox-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
            gap: 0.5rem;
        }
        
        .filter-checkbox {
            padding: 0.5rem;
            border-radius: 6px;
            transition: background 0.2s;
        }
        
        .filter-checkbox:hover {
            background: #f1f5f9;
        }
        
        .filter-checkbox input[type="checkbox"] {
            width: 18px;
            height: 18px;
            cursor: pointer;
        }
        
        .filter-checkbox label {
            cursor: pointer;
            margin-left: 0.5rem;
            margin-bottom: 0;
            font-size: 0.9rem;
            user-select: none;
        }
        
        .form-control, .form-select {
            border-radius: 6px;
            border: 1px solid #e2e8f0;
        }
        
        .form-control:focus, .form-select:focus {
            border-color: #6366f1;
            box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.1);
        }
        
        .kpi-container { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin-bottom: 30px; }
        .kpi-card { background: white; border-radius: 16px; padding: 1.25rem; border: 1px solid #f1f5f9; box-shadow: 0 2px 4px rgba(0,0,0,0.05); position: relative; overflow: hidden; transition: transform 0.2s; }
        .kpi-card:hover { transform: translateY(-2px); box-shadow: 0 4px 8px rgba(0,0,0,0.1); }
        .kpi-icon-bg { position: absolute; right: -5px; top: -5px; font-size: 4rem; opacity: 0.05; transform: rotate(15deg); }
        .kpi-label { font-size: 0.8rem; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; }
        .kpi-number { font-size: 2rem; font-weight: 700; color: #0f172a; margin: 0.25rem 0; }
        
        .charts-container { display: grid; gap: 1.5rem; }
        .card { border-radius: 12px; border: 1px solid #e2e8f0; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
        .card-header { background: white; border-bottom: 1px solid #e2e8f0; font-weight: 600; }
    </style>
        """

    def _header(self, role_badge, role_info=None):
        """Encabezado del dashboard."""
        # Botón de perfiles solo para counselor/admin
        profiles_btn = ''
        if role_info and role_info.get('role') in ['admin', 'counselor']:
            profiles_btn = '''
            <a href="/aulametrics/students" class="btn btn-primary btn-sm ms-2">
                <i class="fa-solid fa-users"></i> Perfiles de Alumnos
            </a>
            '''
        
        return f"""
    <header class="dashboard-header">
        <div>
            <div class="header-title">
                <h1><i class="fa-solid fa-gauge-high me-2 text-primary"></i>Dashboard de Métricas</h1>
            </div>
            <div class="header-meta">
                Análisis global con filtros dinámicos &bull; {fields.Date.today().strftime('%d/%m/%Y')}
            </div>
        </div>
        <div>
            {role_badge}
            {profiles_btn}
            <a href="/web" class="btn btn-outline-secondary btn-sm ms-2">
                <i class="fa-solid fa-arrow-left"></i> Volver
            </a>
        </div>
    </header>
        """

    def _scripts(self):
        """Scripts JavaScript del dashboard."""
        return """
    <script>
        function toggleFilters() {
            const content = document.getElementById('filterContent');
            const icon = document.getElementById('toggleIcon');
            if (content.classList.contains('show')) {
                content.classList.remove('show');
                icon.classList.remove('fa-chevron-up');
                icon.classList.add('fa-chevron-down');
            } else {
                content.classList.add('show');
                icon.classList.remove('fa-chevron-down');
                icon.classList.add('fa-chevron-up');
            }
        }
        
        function selectAllMetrics() {
            document.querySelectorAll('.metric-check').forEach(cb => cb.checked = true);
        }
        
        function selectNoneMetrics() {
            document.querySelectorAll('.metric-check').forEach(cb => cb.checked = false);
        }
        
        function selectAllGroups() {
            document.querySelectorAll('.group-check').forEach(cb => cb.checked = true);
        }
        
        function selectNoneGroups() {
            document.querySelectorAll('.group-check').forEach(cb => cb.checked = false);
        }
        
        function selectAllEvals() {
            document.querySelectorAll('.eval-check').forEach(cb => cb.checked = true);
        }
        
        function selectNoneEvals() {
            document.querySelectorAll('.eval-check').forEach(cb => cb.checked = false);
        }
        
        function clearDates() {
            document.getElementById('date_from').value = '';
            document.getElementById('date_to').value = '';
        }
        
        document.getElementById('hub-filters').addEventListener('submit', function(e) {
            // Consolidar checkboxes en hidden inputs
            const metricChecks = document.querySelectorAll('.metric-check:checked');
            const metricValues = Array.from(metricChecks).map(c => c.value);
            document.getElementById('metric_names_input').value = metricValues.join(',');
            
            const groupChecks = document.querySelectorAll('.group-check:checked');
            const groupValues = Array.from(groupChecks).map(c => c.value);
            document.getElementById('group_ids_input').value = groupValues.join(',');
            
            const evalChecks = document.querySelectorAll('.eval-check:checked');
            const evalValues = Array.from(evalChecks).map(c => c.value);
            document.getElementById('evaluation_ids_input').value = evalValues.join(',');
        });
    </script>
        """
