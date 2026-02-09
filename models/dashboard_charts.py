# -*- coding: utf-8 -*-
"""
Dashboard Charts - Generación de dashboard con métricas filtradas
"""
from odoo import models, api, fields
import pandas as pd
import json

# Importar utilidades compartidas
from ..utils import dashboard_styles, dashboard_layout, dashboard_helpers

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
        charts = self._generate_charts(df, filters, available_metrics, role_info)
        
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
                # Buscar un registro con datos para obtener el label y detectar tipo
                # Priorizar registros que realmente tienen valores
                sample = MetricValue.search([
                    ('metric_name', '=', name),
                    '|', '|',
                    ('value_float', '!=', False),
                    ('value_json', '!=', False),
                    ('value_text', '!=', False)
                ] + domain, limit=1)
                
                # Si no hay registro con datos, buscar cualquiera
                if not sample:
                    sample = MetricValue.search([
                        ('metric_name', '=', name)
                    ] + domain, limit=1)
                
                if not sample:
                    continue
                
                # Detectar tipo según qué campo tiene valor
                if sample.value_float:
                    metric_type = 'numeric'
                elif sample.value_json:
                    metric_type = 'json'
                elif sample.value_text:
                    metric_type = 'text'
                else:
                    continue  # Saltar si no tiene ningún valor
                
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
        
        return [{'id': g.id, 'name': g.name, 'course': g.course_level, 'student_count': g.student_count} for g in groups]

    def _get_available_evaluations(self, role_info):
        """Obtiene las evaluaciones disponibles según el rol."""
        Evaluation = self.env['aulametrics.evaluation']
        
        # Las record rules ya aplican filtros, simplemente buscamos todas
        evaluations = Evaluation.search([], order='date_start desc')
        
        return [{'id': e.id, 'name': e.name, 'state': e.state, 'date_start': e.date_start} for e in evaluations]

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

    def _generate_charts(self, df, filters, available_metrics, role_info):
        """Genera gráficos según las métricas presentes en el DataFrame y rol del usuario."""
        charts = []
        
        # Obtener métricas únicas en el DataFrame
        grouped = df.groupby(['metric_name', 'metric_label', 'metric_type']).size().reset_index(name='count')
        
        for _, row in grouped.iterrows():
            metric_info = {
                'name': row['metric_name'],
                'label': row['metric_label'],
                'type': row['metric_type']
            }
            
            chart_html = self._generate_chart_by_metric_type(metric_info, df, role_info)
            if chart_html:
                charts.append(chart_html)
        
        return charts

    def _generate_chart_by_metric_type(self, metric_info, df, role_info):
        """Genera el gráfico apropiado según el tipo de métrica y rol."""
        metric_name = metric_info['name']
        metric_label = metric_info['label']
        metric_type = metric_info['type']
        
        df_metric = df[df['metric_name'] == metric_name].copy()
        
        if metric_type == 'numeric':
            return self._chart_numeric_metric(df_metric, metric_label, role_info)
        elif metric_type == 'json':
            return self._chart_json_metric(df_metric, metric_label)
        # Las métricas de texto no se muestran aquí, se gestionan en la pestaña cualitativa
        
        return ''

    def _chart_numeric_metric(self, df, label, role_info):
        """Gráfico adaptado según rol del usuario con colores semáforo."""
        if df.empty or df['value_numeric'].isna().all():
            return ''
        
        role = role_info.get('role', 'counselor')
        charts_html = ''
        
        # Detectar si hay múltiples mediciones temporales
        evaluations = df['evaluation_name'].dropna().unique()
        has_evolution = len(evaluations) >= 2
        
        # Gráfico principal según rol
        if role == 'management':
            charts_html += self._chart_numeric_by_course(df, label)
            if has_evolution:
                charts_html += self._chart_numeric_evolution_by_course(df, label)
        elif role == 'tutor':
            charts_html += self._chart_numeric_distribution(df, label)
            if has_evolution:
                charts_html += self._chart_numeric_evolution_distribution(df, label)
        else:  # counselor/admin
            charts_html += self._chart_numeric_by_groups(df, label)
            if has_evolution:
                charts_html += self._chart_numeric_evolution_by_groups(df, label)
        
        return charts_html
    
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
    
    def _get_thresholds_for_metric(self, metric_name):
        """Obtiene umbrales activos configurados para una métrica.
        
        Args:
            metric_name (str): Nombre de la métrica (ej: 'who5_score', 'asq14_total')
        
        Returns:
            list: Lista de dicts con {value, operator, label, severity}
        """
        Threshold = self.env['aulametrics.threshold']
        thresholds = Threshold.search([
            ('active', '=', True),
            ('score_field', '=', metric_name)
        ])
        
        result = []
        for t in thresholds:
            result.append({
                'value': t.threshold_value,
                'operator': t.operator,
                'label': t.name,
                'severity': t.severity
            })
        
        return result
    
    def _chart_numeric_evolution_by_course(self, df, label):
        """Evolución temporal de la métrica por curso (Management)."""
        # Agrupar por evaluación (no por timestamp individual)
        evaluations = df.groupby('evaluation_name')['completed_at'].min().sort_values()
        
        if len(evaluations) < 2:
            return ''
        
        cursos = sorted(df['curso'].unique())
        color_palette = ['#3b82f6', '#10b981', '#f59e0b', '#8b5cf6', '#ec4899', '#06b6d4', '#f97316', '#84cc16']
        
        # Preparar datasets por curso
        datasets = []
        for idx, curso in enumerate(cursos):
            df_curso = df[df['curso'] == curso]
            data_points = []
            
            for eval_name, eval_date in evaluations.items():
                df_eval = df_curso[df_curso['evaluation_name'] == eval_name]['value_numeric'].dropna()
                if len(df_eval) > 0:
                    data_points.append({
                        'x': eval_date.isoformat() if hasattr(eval_date, 'isoformat') else str(eval_date),
                        'y': float(df_eval.mean())
                    })
            
            if data_points:
                datasets.append({
                    'label': curso,
                    'data': data_points,
                    'borderColor': color_palette[idx % len(color_palette)],
                    'backgroundColor': color_palette[idx % len(color_palette)] + '20',
                    'tension': 0.3
                })
        
        if not datasets:
            return ''
        
        chart_id = f'evolution_{label.replace(" ", "_").replace("/", "_").replace(".", "_")}'
        
        return f'''
        <div class="card">
            <div class="card-header">
                <h5 class="card-title">Evolución: {label}</h5>
                <p class="card-subtitle">Tendencia temporal por curso académico</p>
            </div>
            <div class="card-body">
                <canvas id="{chart_id}" height="240"></canvas>
            </div>
        </div>
        
        <script>
        new Chart(document.getElementById('{chart_id}'), {{
            type: 'line',
            data: {{
                datasets: {json.dumps(datasets)}
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: true,
                plugins: {{
                    legend: {{
                        display: true,
                        position: 'top',
                        labels: {{
                            usePointStyle: true,
                            padding: 12,
                            font: {{ size: 11, family: "'Inter', sans-serif" }},
                            color: '#64748b'
                        }}
                    }},
                    tooltip: {{
                        backgroundColor: '#1e293b',
                        padding: 14,
                        cornerRadius: 8,
                        titleFont: {{ family: "'Inter', sans-serif", size: 14, weight: '600' }},
                        bodyFont: {{ family: "'Inter', sans-serif", size: 13 }},
                        callbacks: {{
                            title: function(context) {{
                                return new Date(context[0].parsed.x).toLocaleDateString('es-ES');
                            }},
                            label: function(context) {{
                                return context.dataset.label + ': ' + context.parsed.y.toFixed(1) + ' pts';
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
                                day: 'dd/MM/yyyy'
                            }}
                        }},
                        grid: {{ display: false, drawBorder: false }},
                        ticks: {{
                            font: {{ size: 11, family: "'Inter', sans-serif" }},
                            color: '#64748b'
                        }}
                    }},
                    y: {{
                        beginAtZero: true,
                        max: 100,
                        grid: {{ color: '#f1f5f9', drawBorder: false }},
                        ticks: {{
                            font: {{ size: 11, family: "'Inter', sans-serif" }},
                            color: '#94a3b8'
                        }}
                    }}
                }}
            }}
        }});
        </script>
        '''
    
    def _chart_numeric_evolution_distribution(self, df, label):
        """Evolución temporal de la media del grupo (Tutor - anónimo)."""
        # Agrupar por evaluación (no por timestamp individual)
        evaluations = df.groupby('evaluation_name')['completed_at'].min().sort_values()
        
        if len(evaluations) < 2:
            return ''
        
        # Calcular media del grupo en cada evaluación
        data_points = []
        for eval_name, eval_date in evaluations.items():
            df_eval = df[df['evaluation_name'] == eval_name]['value_numeric'].dropna()
            if len(df_eval) > 0:
                data_points.append({
                    'x': eval_date.isoformat() if hasattr(eval_date, 'isoformat') else str(eval_date),
                    'y': float(df_eval.mean())
                })
        
        if not data_points:
            return ''
        
        chart_id = f'evolution_{label.replace(" ", "_").replace("/", "_").replace(".", "_")}'
        
        datasets = [{
            'label': 'Media del grupo',
            'data': data_points,
            'borderColor': '#3b82f6',
            'backgroundColor': '#3b82f620',
            'tension': 0.3,
            'fill': True
        }]
        
        return f'''
        <div class="card">
            <div class="card-header">
                <h5 class="card-title">Evolución: {label}</h5>
                <p class="card-subtitle">Tendencia temporal de la media del grupo</p>
            </div>
            <div class="card-body">
                <canvas id="{chart_id}" height="240"></canvas>
            </div>
        </div>
        
        <script>
        new Chart(document.getElementById('{chart_id}'), {{
            type: 'line',
            data: {{
                datasets: {json.dumps(datasets)}
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: true,
                plugins: {{
                    legend: {{ display: false }},
                    tooltip: {{
                        backgroundColor: '#1e293b',
                        padding: 14,
                        cornerRadius: 8,
                        titleFont: {{ family: "'Inter', sans-serif", size: 14, weight: '600' }},
                        bodyFont: {{ family: "'Inter', sans-serif", size: 13 }},
                        callbacks: {{
                            title: function(context) {{
                                return new Date(context[0].parsed.x).toLocaleDateString('es-ES');
                            }},
                            label: function(context) {{
                                return 'Media: ' + context.parsed.y.toFixed(1) + ' pts';
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
                                day: 'dd/MM/yyyy'
                            }}
                        }},
                        grid: {{ display: false, drawBorder: false }},
                        ticks: {{
                            font: {{ size: 11, family: "'Inter', sans-serif" }},
                            color: '#64748b'
                        }}
                    }},
                    y: {{
                        beginAtZero: true,
                        max: 100,
                        grid: {{ color: '#f1f5f9', drawBorder: false }},
                        ticks: {{
                            font: {{ size: 11, family: "'Inter', sans-serif" }},
                            color: '#94a3b8'
                        }}
                    }}
                }}
            }}
        }});
        </script>
        '''
    
    def _chart_numeric_evolution_by_groups(self, df, label):
        """Evolución temporal de la métrica por grupo (Counselor)."""
        # Agrupar por evaluación (no por timestamp individual)
        evaluations = df.groupby('evaluation_name')['completed_at'].min().sort_values()
        
        if len(evaluations) < 2:
            return ''
        
        grupos = sorted(df['group_name'].unique())
        color_palette = ['#3b82f6', '#10b981', '#f59e0b', '#8b5cf6', '#ec4899', '#06b6d4', '#f97316', '#84cc16', '#f43f5e', '#14b8a6']
        
        # Preparar datasets por grupo
        datasets = []
        for idx, grupo in enumerate(grupos):
            df_grupo = df[df['group_name'] == grupo]
            data_points = []
            
            for eval_name, eval_date in evaluations.items():
                df_eval = df_grupo[df_grupo['evaluation_name'] == eval_name]['value_numeric'].dropna()
                if len(df_eval) > 0:
                    data_points.append({
                        'x': eval_date.isoformat() if hasattr(eval_date, 'isoformat') else str(eval_date),
                        'y': float(df_eval.mean())
                    })
            
            if data_points:
                datasets.append({
                    'label': grupo,
                    'data': data_points,
                    'borderColor': color_palette[idx % len(color_palette)],
                    'backgroundColor': color_palette[idx % len(color_palette)] + '20',
                    'tension': 0.3
                })
        
        if not datasets:
            return ''
        
        chart_id = f'evolution_{label.replace(" ", "_").replace("/", "_").replace(".", "_")}'
        
        return f'''
        <div class="card">
            <div class="card-header">
                <h5 class="card-title">Evolución: {label}</h5>
                <p class="card-subtitle">Tendencia temporal por grupo</p>
            </div>
            <div class="card-body">
                <canvas id="{chart_id}" height="260"></canvas>
            </div>
        </div>
        
        <script>
        new Chart(document.getElementById('{chart_id}'), {{
            type: 'line',
            data: {{
                datasets: {json.dumps(datasets)}
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: true,
                plugins: {{
                    legend: {{
                        display: true,
                        position: 'top',
                        labels: {{
                            usePointStyle: true,
                            padding: 10,
                            font: {{ size: 10, family: "'Inter', sans-serif" }},
                            color: '#64748b',
                            boxWidth: 8
                        }}
                    }},
                    tooltip: {{
                        backgroundColor: '#1e293b',
                        padding: 12,
                        cornerRadius: 6,
                        titleFont: {{ family: "'Inter', sans-serif", size: 13, weight: '600' }},
                        bodyFont: {{ family: "'Inter', sans-serif", size: 12 }},
                        callbacks: {{
                            title: function(context) {{
                                return new Date(context[0].parsed.x).toLocaleDateString('es-ES');
                            }},
                            label: function(context) {{
                                return context.dataset.label + ': ' + context.parsed.y.toFixed(1) + ' pts';
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
                                day: 'dd/MM/yyyy'
                            }}
                        }},
                        grid: {{ display: false, drawBorder: false }},
                        ticks: {{
                            font: {{ size: 11, family: "'Inter', sans-serif" }},
                            color: '#64748b'
                        }}
                    }},
                    y: {{
                        beginAtZero: true,
                        max: 100,
                        grid: {{ color: '#f1f5f9', drawBorder: false }},
                        ticks: {{
                            font: {{ size: 11, family: "'Inter', sans-serif" }},
                            color: '#94a3b8'
                        }}
                    }}
                }}
            }}
        }});
        </script>
        '''
    
    def _chart_numeric_by_course(self, df, label):
        """Vista Management: Agregado por curso académico (barras compactas)."""
        cursos = sorted(df['curso'].unique())
        stats = []
        
        # Paleta de colores consistente para cursos
        color_palette = ['#3b82f6', '#10b981', '#f59e0b', '#8b5cf6', '#ec4899', '#06b6d4', '#f97316', '#84cc16']
        
        # Preparar datos generales
        for idx, curso in enumerate(cursos):
            df_curso = df[df['curso'] == curso]['value_numeric'].dropna()
            if len(df_curso) > 0:
                mean_val = float(df_curso.mean())
                n_alumnos = len(df_curso['student_id'].unique())
                n_grupos = len(df_curso['group_id'].unique())
                stats.append({
                    'curso': curso,
                    'mean': mean_val,
                    'n_alumnos': n_alumnos,
                    'n_grupos': n_grupos,
                    'color': color_palette[idx % len(color_palette)]
                })
        
        if not stats:
            return ''
        
        # Preparar datos por género
        stats_by_gender = {}
        gender_map = {'male': 'Masculino', 'female': 'Femenino', 'other': 'Otro', 'prefer_not_say': 'Prefiere no decir'}
        for curso in cursos:
            df_curso = df[df['curso'] == curso]
            stats_by_gender[curso] = {}
            for gender_key, gender_label in gender_map.items():
                df_gender = df_curso[df_curso['student_gender'] == gender_key]
                if len(df_gender) > 0:
                    values = df_gender['value_numeric'].dropna()
                    if len(values) > 0:
                        stats_by_gender[curso][gender_label] = {
                            'mean': float(values.mean()),
                            'count': int(len(values))
                        }
        
        chart_id = f'chart_{label.replace(" ", "_").replace("/", "_").replace(".", "_")}'
        labels = [s['curso'] for s in stats]
        means = [s['mean'] for s in stats]
        colors = [s['color'] for s in stats]
        
        # Obtener umbrales configurados para esta métrica
        metric_name = df.iloc[0]['metric_name'] if not df.empty else None
        thresholds = self._get_thresholds_for_metric(metric_name) if metric_name else []
        
        return f'''
        <div class="card">
            <div class="card-header" style="display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <h5 class="card-title">{label}</h5>
                    <p class="card-subtitle">Media por curso académico</p>
                </div>
                <div style="display: flex; gap: 12px; align-items: center;">
                    <label style="display: flex; align-items: center; gap: 6px; font-size: 13px; color: #64748b; cursor: pointer;">
                        <input type="checkbox" id="gender_{chart_id}" style="cursor: pointer;">
                        <span>⚧️ Dividir por género</span>
                    </label>
                    <button id="sort_{chart_id}" style="padding: 6px 12px; background: white; border: 1px solid #e5e7eb; border-radius: 6px; cursor: pointer; font-size: 13px; color: #64748b;" title="Cambiar orden">
                        ↕️ Orden
                    </button>
                </div>
            </div>
            <div class="card-body">
                <canvas id="{chart_id}" height="220"></canvas>
            </div>
        </div>
        
        <script>
        (function() {{
            const chartData = {{
                labels: {json.dumps(labels)},
                means: {json.dumps(means)},
                colors: {json.dumps(colors)},
                statsByGender: {json.dumps(stats_by_gender)},
                thresholds: {json.dumps(thresholds)}
            }};
            
            let ascending = true;
            let byGender = false;
            
            // Crear datasets de umbrales
            function createThresholdDatasets(labelCount) {{
                const thresholdDatasets = [];
                chartData.thresholds.forEach((threshold, idx) => {{
                    const thresholdData = Array(labelCount).fill(threshold.value);
                    thresholdDatasets.push({{
                        type: 'line',
                        label: threshold.label + ' (' + threshold.operator + ' ' + threshold.value + ')',
                        data: thresholdData,
                        borderColor: '#ef4444',
                        borderWidth: 2,
                        borderDash: [5, 5],
                        pointRadius: 0,
                        fill: false,
                        order: 0
                    }});
                }});
                return thresholdDatasets;
            }}
            
            const chart = new Chart(document.getElementById('{chart_id}'), {{
                type: 'bar',
                data: {{
                    labels: chartData.labels,
                    datasets: [
                        {{
                            label: 'Media',
                            data: chartData.means,
                            backgroundColor: chartData.colors,
                            borderRadius: 6,
                            borderSkipped: false,
                            order: 1
                        }},
                        ...createThresholdDatasets(chartData.labels.length)
                    ]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: true,
                    plugins: {{
                        legend: {{ display: false }},
                        tooltip: {{
                            backgroundColor: '#1e293b',
                            padding: 14,
                            cornerRadius: 8,
                            titleFont: {{ family: "'Inter', sans-serif", size: 14, weight: '600' }},
                            bodyFont: {{ family: "'Inter', sans-serif", size: 13 }}
                        }}
                    }},
                    scales: {{
                        x: {{
                            grid: {{ display: false, drawBorder: false }},
                            ticks: {{
                                font: {{ size: 12, family: "'Inter', sans-serif" }},
                                color: '#64748b'
                            }}
                        }},
                        y: {{
                            beginAtZero: true,
                            max: 100,
                            grid: {{ color: '#f1f5f9', drawBorder: false }},
                            ticks: {{
                                font: {{ size: 11, family: "'Inter', sans-serif" }},
                                color: '#94a3b8'
                            }}
                        }}
                    }}
                }}
            }});
            
            function updateChart() {{
                let data = [];
                let labels = [];
                let colors = [];
                
                const entries = chartData.labels.map((label, i) => ({{
                    label: label,
                    value: chartData.means[i],
                    color: chartData.colors[i]
                }}));
                
                // Ordenar
                entries.sort((a, b) => ascending ? a.value - b.value : b.value - a.value);
                
                if (byGender) {{
                    // Dividir por género
                    const genderColors = {{
                        'Masculino': '#3b82f6',
                        'Femenino': '#ec4899',
                        'Otro': '#94a3b8',
                        'Prefiere no decir': '#64748b'
                    }};
                    
                    chart.data.labels = entries.map(e => e.label);
                    chart.data.datasets = [];
                    
                    ['Masculino', 'Femenino', 'Otro', 'Prefiere no decir'].forEach(gender => {{
                        const genderData = entries.map(e => {{
                            const stats = chartData.statsByGender[e.label];
                            return stats && stats[gender] ? stats[gender].mean : null;
                        }});
                        
                        if (genderData.some(v => v !== null)) {{
                            chart.data.datasets.push({{
                                label: gender,
                                data: genderData,
                                backgroundColor: genderColors[gender],
                                borderRadius: 6,
                                borderSkipped: false
                            }});
                        }}
                    }});
                    chart.options.plugins.legend.display = true;
                    // Añadir umbrales
                    chart.data.datasets.push(...createThresholdDatasets(chart.data.labels.length));
                }} else {{
                    // Vista normal
                    chart.data.labels = entries.map(e => e.label);
                    chart.data.datasets = [
                        {{
                            label: 'Media',
                            data: entries.map(e => e.value),
                            backgroundColor: entries.map(e => e.color),
                            borderRadius: 6,
                            borderSkipped: false,
                            order: 1
                        }},
                        ...createThresholdDatasets(entries.length)
                    ];
                    chart.options.plugins.legend.display = false;
                }}
                
                chart.update();
            }}
            
            document.getElementById('gender_{chart_id}').addEventListener('change', function(e) {{
                byGender = e.target.checked;
                updateChart();
            }});
            
            document.getElementById('sort_{chart_id}').addEventListener('click', function() {{
                ascending = !ascending;
                this.innerHTML = ascending ? 'Orden: Ascendente' : 'Orden: Descendente';
                updateChart();
            }});
        }})();
        </script>
        '''

    def _chart_numeric_distribution(self, df, label):
        """Vista Tutor: Distribución anónima del grupo (histogram)."""
        values = df['value_numeric'].dropna()
        if len(values) == 0:
            return ''
        
        # Crear bins (rangos) para el histograma
        bins = [0, 40, 60, 80, 100]
        bin_labels = ['0-40 (Crítico)', '40-60 (Atención)', '60-80 (Normal)', '80-100 (Excelente)']
        bin_colors = ['#ef4444', '#f59e0b', '#3b82f6', '#10b981']
        
        # Contar cuántos alumnos en cada rango
        counts = []
        for i in range(len(bins) - 1):
            count = ((values >= bins[i]) & (values < bins[i+1])).sum()
            # Para el último bin, incluir el límite superior
            if i == len(bins) - 2:
                count = ((values >= bins[i]) & (values <= bins[i+1])).sum()
            counts.append(int(count))
        
        chart_id = f'chart_dist_{label.replace(" ", "_").replace("/", "_").replace(".", "_")}'
        total_alumnos = len(values)
        mean_val = float(values.mean())
        
        # Texto descriptivo
        desc_texts = []
        if counts[0] > 0:
            desc_texts.append(f"🔴 {counts[0]} alumno{'s' if counts[0] > 1 else ''} en situación crítica")
        if counts[1] > 0:
            desc_texts.append(f"🟡 {counts[1]} alumno{'s' if counts[1] > 1 else ''} requieren atención")
        if counts[2] > 0:
            desc_texts.append(f"🔵 {counts[2]} alumno{'s' if counts[2] > 1 else ''} en nivel aceptable")
        if counts[3] > 0:
            desc_texts.append(f"🟢 {counts[3]} alumno{'s' if counts[3] > 1 else ''} con nivel excelente")
        
        description = " · ".join(desc_texts) if desc_texts else "Sin datos suficientes"
        
        return f'''
        <div class="card">
            <div class="card-header">
                <h5 class="card-title">{label}</h5>
                <p class="card-subtitle">Distribución anónima del grupo · Media: {mean_val:.1f} pts</p>
            </div>
            <div class="card-body">
                <canvas id="{chart_id}" height="280"></canvas>
                <div style="margin-top: 16px; padding: 12px; background: #f8fafc; border-radius: 8px; font-size: 13px; color: #475569;">
                    <strong>Interpretación:</strong> {description}
                </div>
            </div>
        </div>
        
        <script>
        new Chart(document.getElementById('{chart_id}'), {{
            type: 'bar',
            data: {{
                labels: {json.dumps(bin_labels)},
                datasets: [{{
                    label: 'Número de alumnos',
                    data: {json.dumps(counts)},
                    backgroundColor: {json.dumps(bin_colors)},
                    borderRadius: 8,
                    borderSkipped: false
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: true,
                plugins: {{
                    legend: {{ display: false }},
                    tooltip: {{
                        backgroundColor: '#1e293b',
                        padding: 14,
                        cornerRadius: 8,
                        titleFont: {{ family: "'Inter', sans-serif", size: 14, weight: '600' }},
                        bodyFont: {{ family: "'Inter', sans-serif", size: 13 }},
                        callbacks: {{
                            label: function(context) {{
                                let percentage = ({total_alumnos} > 0) ? ((context.parsed.y / {total_alumnos}) * 100).toFixed(1) : 0;
                                return context.parsed.y + ' alumnos (' + percentage + '%)';
                            }}
                        }}
                    }}
                }},
                scales: {{
                    x: {{
                        grid: {{ display: false, drawBorder: false }},
                        ticks: {{
                            font: {{ size: 11, family: "'Inter', sans-serif" }},
                            color: '#64748b'
                        }}
                    }},
                    y: {{
                        beginAtZero: true,
                        grid: {{ color: '#f1f5f9', drawBorder: false }},
                        ticks: {{
                            stepSize: 1,
                            font: {{ size: 12, family: "'Inter', sans-serif" }},
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
    
    def _chart_numeric_by_groups(self, df, label):
        """Vista Counselor: Comparativa de grupos (barras horizontales compactas)."""
        grupos = sorted(df['group_name'].unique())
        stats = []
        
        # Paleta de colores para grupos
        color_palette = ['#3b82f6', '#10b981', '#f59e0b', '#8b5cf6', '#ec4899', '#06b6d4', '#f97316', '#84cc16', '#f43f5e', '#14b8a6']
        
        for idx, grupo in enumerate(grupos):
            df_grupo = df[df['group_name'] == grupo]['value_numeric'].dropna()
            if len(df_grupo) > 0:
                mean_val = float(df_grupo.mean())
                n_alumnos = int(len(df_grupo))
                
                stats.append({
                    'grupo': grupo,
                    'mean': mean_val,
                    'n_alumnos': n_alumnos,
                    'color': color_palette[idx % len(color_palette)]
                })
        
        if not stats:
            return ''
        
        # Preparar datos por género
        stats_by_gender = {}
        gender_map = {'male': 'Masculino', 'female': 'Femenino', 'other': 'Otro', 'prefer_not_say': 'Prefiere no decir'}
        for grupo in grupos:
            df_grupo = df[df['group_name'] == grupo]
            stats_by_gender[grupo] = {}
            for gender_key, gender_label in gender_map.items():
                df_gender = df_grupo[df_grupo['student_gender'] == gender_key]
                if len(df_gender) > 0:
                    values = df_gender['value_numeric'].dropna()
                    if len(values) > 0:
                        stats_by_gender[grupo][gender_label] = {
                            'mean': float(values.mean()),
                            'count': int(len(values))
                        }
        
        # Ordenar por puntuación inicialmente
        stats_sorted = sorted(stats, key=lambda x: x['mean'])
        
        chart_id = f'chart_grupos_{label.replace(" ", "_").replace("/", "_").replace(".", "_")}'
        labels = [s['grupo'] for s in stats_sorted]
        means = [s['mean'] for s in stats_sorted]
        colors = [s['color'] for s in stats_sorted]
        
        # Obtener umbrales configurados para esta métrica
        metric_name = df.iloc[0]['metric_name'] if not df.empty else None
        thresholds = self._get_thresholds_for_metric(metric_name) if metric_name else []
        
        # Altura dinámica pero controlada
        chart_height = min(350, max(200, len(stats) * 25))
        
        return f'''
        <div class="card">
            <div class="card-header" style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px;">
                <div>
                    <h5 class="card-title">{label}</h5>
                    <p class="card-subtitle">Comparativa por grupo</p>
                </div>
                <div style="display: flex; gap: 8px; align-items: center;">
                    <label style="display: flex; align-items: center; gap: 6px; font-size: 12px; color: #475569; cursor: pointer; background: #f8fafc; padding: 6px 12px; border: 1px solid #e2e8f0; border-radius: 6px; transition: all 0.2s;">
                        <input type="checkbox" id="gender_{chart_id}" style="cursor: pointer;">
                        <span style="font-weight: 500;">Dividir por género</span>
                    </label>
                    <button id="sort_{chart_id}" style="padding: 6px 12px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; cursor: pointer; font-size: 12px; color: #475569; font-weight: 500; transition: all 0.2s;" onmouseover="this.style.background='#f1f5f9'" onmouseout="this.style.background='#f8fafc'">
                        Ordenar
                    </button>
                </div>
            </div>
            <div class="card-body" style="max-height: 400px; overflow-y: auto;">
                <canvas id="{chart_id}" height="{chart_height}"></canvas>
            </div>
        </div>
        
        <script>
        (function() {{
            const chartData = {{
                groups: {json.dumps([s['grupo'] for s in stats_sorted])},
                means: {json.dumps([s['mean'] for s in stats_sorted])},
                colors: {json.dumps([s['color'] for s in stats_sorted])},
                statsByGender: {json.dumps(stats_by_gender)},
                allGroups: {json.dumps([s['grupo'] for s in stats])},
                allColors: {json.dumps({s['grupo']: s['color'] for s in stats})},
                thresholds: {json.dumps(thresholds)}
            }};
            
            let ascending = true;
            let byGender = false;
            
            // Crear datasets de umbrales
            function createThresholdDatasets(labelCount) {{
                const thresholdDatasets = [];
                chartData.thresholds.forEach((threshold, idx) => {{
                    const thresholdData = Array(labelCount).fill(threshold.value);
                    thresholdDatasets.push({{
                        type: 'line',
                        label: threshold.label + ' (' + threshold.operator + ' ' + threshold.value + ')',
                        data: thresholdData,
                        borderColor: '#ef4444',
                        borderWidth: 2,
                        borderDash: [5, 5],
                        pointRadius: 0,
                        fill: false,
                        order: 0
                    }});
                }});
                return thresholdDatasets;
            }}
            
            const chart = new Chart(document.getElementById('{chart_id}'), {{
                type: 'bar',
                data: {{
                    labels: chartData.groups,
                    datasets: [
                        {{
                            label: 'Media',
                            data: chartData.means,
                            backgroundColor: chartData.colors,
                            borderRadius: 6,
                            borderSkipped: false,
                            order: 1
                        }},
                        ...createThresholdDatasets(chartData.groups.length)
                    ]
                }},
                options: {{
                    indexAxis: 'y',
                    responsive: true,
                    maintainAspectRatio: true,
                    plugins: {{
                        legend: {{ display: false }},
                        tooltip: {{
                            backgroundColor: '#1e293b',
                            padding: 12,
                            cornerRadius: 6,
                            titleFont: {{ family: "'Inter', sans-serif", size: 13, weight: '600' }},
                            bodyFont: {{ family: "'Inter', sans-serif", size: 12 }}
                        }}
                    }},
                    scales: {{
                        x: {{
                            beginAtZero: true,
                            max: 100,
                            grid: {{ color: '#f1f5f9', drawBorder: false }},
                            ticks: {{
                                font: {{ size: 11, family: "'Inter', sans-serif" }},
                                color: '#94a3b8'
                            }}
                        }},
                        y: {{
                            grid: {{ display: false, drawBorder: false }},
                            ticks: {{
                                font: {{ size: 11, family: "'Inter', sans-serif", weight: '500' }},
                                color: '#0f172a'
                            }}
                        }}
                    }}
                }}
            }});
            
            function updateChart() {{
                let entries = chartData.allGroups.map(group => {{
                    const stats = chartData.statsByGender[group] || {{}};
                    let totalMean = 0;
                    let count = 0;
                    Object.values(stats).forEach(s => {{
                        totalMean += s.mean * s.count;
                        count += s.count;
                    }});
                    return {{
                        group: group,
                        mean: count > 0 ? totalMean / count : 0,
                        color: chartData.allColors[group]
                    }};
                }});
                
                // Ordenar
                entries.sort((a, b) => ascending ? a.mean - b.mean : b.mean - a.mean);
                
                if (byGender) {{
                    // Dividir por género
                    const genderColors = {{
                        'Masculino': '#3b82f6',
                        'Femenino': '#ec4899',
                        'Otro': '#94a3b8',
                        'Prefiere no decir': '#64748b'
                    }};
                    
                    chart.data.labels = entries.map(e => e.group);
                    chart.data.datasets = [];
                    
                    ['Masculino', 'Femenino', 'Otro', 'Prefiere no decir'].forEach(gender => {{
                        const genderData = entries.map(e => {{
                            const stats = chartData.statsByGender[e.group];
                            return stats && stats[gender] ? stats[gender].mean : null;
                        }});
                        
                        if (genderData.some(v => v !== null)) {{
                            chart.data.datasets.push({{
                                label: gender,
                                data: genderData,
                                backgroundColor: genderColors[gender],
                                borderRadius: 6,
                                borderSkipped: false
                            }});
                        }}
                    }});
                    chart.options.plugins.legend.display = true;
                    chart.options.plugins.legend.position = 'top';
                    // Añadir umbrales
                    chart.data.datasets.push(...createThresholdDatasets(chart.data.labels.length));
                }} else {{
                    // Vista normal
                    chart.data.labels = entries.map(e => e.group);
                    chart.data.datasets = [
                        {{
                            label: 'Media',
                            data: entries.map(e => e.mean),
                            backgroundColor: entries.map(e => e.color),
                            borderRadius: 6,
                            borderSkipped: false,
                            order: 1
                        }},
                        ...createThresholdDatasets(entries.length)
                    ];
                    chart.options.plugins.legend.display = false;
                }}
                
                chart.update();
            }}
            
            document.getElementById('gender_{chart_id}').addEventListener('change', function(e) {{
                byGender = e.target.checked;
                updateChart();
            }});
            
            document.getElementById('sort_{chart_id}').addEventListener('click', function() {{
                ascending = !ascending;
                this.innerHTML = ascending ? 'Orden: Ascendente' : 'Orden: Descendente';
                updateChart();
            }});
        }})();
        </script>
        '''

    def _chart_json_metric(self, df, label):
        """Gráfico de barras horizontales para métricas JSON (opciones múltiples)."""
        if df.empty:
            return ''
        
        # Contar frecuencias de respuestas
        responses = []
        total_respondents = 0
        
        for val in df['value_json'].dropna():
            total_respondents += 1
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
        
        # Ordenar por frecuencia descendente
        sorted_items = sorted(counts.items(), key=lambda x: x[1], reverse=True)
        labels_list = [item[0] for item in sorted_items[:15]]  # Top 15 opciones
        values = [item[1] for item in sorted_items[:15]]
        
        # Calcular porcentajes
        percentages = [round((v / total_respondents * 100), 1) for v in values]
        
        chart_id = f'chart_{label.replace(" ", "_").replace("/", "_").replace(".", "_").replace("?", "").replace("¿", "")}'
        
        return f'''
        <div class="card">
            <div class="card-header">
                <h5 class="card-title">{label}</h5>
                <p class="card-subtitle">Distribución de respuestas • {total_respondents} estudiante{'s' if total_respondents != 1 else ''}</p>
            </div>
            <div class="card-body">
                <canvas id="{chart_id}" height="350"></canvas>
            </div>
        </div>
        
        <script>
        new Chart(document.getElementById('{chart_id}'), {{
            type: 'bar',
            data: {{
                labels: {json.dumps(labels_list)},
                datasets: [{{
                    label: 'Respuestas',
                    data: {json.dumps(values)},
                    backgroundColor: '#3b82f6',
                    borderRadius: 6,
                    borderSkipped: false
                }}]
            }},
            options: {{
                indexAxis: 'y',
                responsive: true,
                maintainAspectRatio: true,
                plugins: {{
                    legend: {{ display: false }},
                    tooltip: {{
                        backgroundColor: '#1e293b',
                        padding: 12,
                        cornerRadius: 6,
                        titleFont: {{ family: "'Inter', sans-serif", size: 13 }},
                        bodyFont: {{ family: "'Inter', sans-serif", size: 13 }},
                        callbacks: {{
                            label: function(context) {{
                                const value = context.parsed.x;
                                const percent = {json.dumps(percentages)}[context.dataIndex];
                                return 'Respuestas: ' + value + ' (' + percent + '%)';
                            }}
                        }}
                    }}
                }},
                scales: {{
                    x: {{
                        beginAtZero: true,
                        grid: {{ color: '#f1f5f9', drawBorder: false }},
                        ticks: {{
                            font: {{ size: 12, family: "'Inter', sans-serif" }},
                            color: '#94a3b8',
                            precision: 0
                        }}
                    }},
                    y: {{
                        grid: {{ display: false, drawBorder: false }},
                        ticks: {{
                            font: {{ size: 12, family: "'Inter', sans-serif" }},
                            color: '#475569',
                            crossAlign: 'far'
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

    def _generate_kpis(self, df, filters, role_info):
        """Genera tarjetas KPI con diseño profesional."""
        kpis = []
        
        # Total de estudiantes
        total_students = df['student_id'].nunique()
        kpis.append(f"""
        <div class="kpi-card">
            <div class="kpi-label">Estudiantes</div>
            <div class="kpi-value">{total_students}</div>
            <div class="kpi-description">Total analizados</div>
        </div>
        """)
        
        # Total de grupos
        total_groups = df['group_id'].nunique()
        kpis.append(f"""
        <div class="kpi-card">
            <div class="kpi-label">Grupos</div>
            <div class="kpi-value">{total_groups}</div>
            <div class="kpi-description">Académicos</div>
        </div>
        """)
        
        # Total de evaluaciones
        total_evals = df['evaluation_id'].nunique()
        kpis.append(f"""
        <div class="kpi-card">
            <div class="kpi-label">Evaluaciones</div>
            <div class="kpi-value">{total_evals}</div>
            <div class="kpi-description">Completadas</div>
        </div>
        """)
        
        # Total de métricas
        total_metrics = len(df)
        kpis.append(f"""
        <div class="kpi-card">
            <div class="kpi-label">Métricas</div>
            <div class="kpi-value">{total_metrics}</div>
            <div class="kpi-description">Registradas</div>
        </div>
        """)
        
        return '\n'.join(kpis)

    def _build_html_empty(self, metrics, groups, evaluations, filters, role_info):
        """HTML cuando no hay datos disponibles."""
        # Usar utilidades compartidas
        role_badge = dashboard_helpers.get_role_badge(role_info)
        filter_controls = self._build_filter_controls(metrics, groups, evaluations, filters)
        sidebar_html = dashboard_layout.get_sidebar(role_info, active_section='home')
        
        # Topbar con fecha
        date_str = dashboard_helpers.format_date(fields.Date.today())
        topbar_html = dashboard_layout.get_topbar(
            title='Inicio',
            subtitle=f'<i class="fa-regular fa-calendar me-2"></i>{date_str}',
            role_badge=role_badge
        )
        
        home_html = self._home_section(metrics, groups, evaluations, filters, role_info)
        
        # Construir contenido de las secciones
        content = f"""
            <!-- Sección Home -->
            <div class="content-section active" id="section-home">
                {home_html}
            </div>
            
            <!-- Sección Datos Cuantitativos -->
            <div class="content-section" id="section-quantitative">
                <div class="container-fluid">
                    {filter_controls}
                    {dashboard_layout.get_empty_state('chart-line', 'No hay datos disponibles', 'Ajusta los filtros para ver resultados')}
                </div>
            </div>
            
            <!-- Sección Datos Cualitativos -->
            <div class="content-section" id="section-qualitative">
                <div id="qualitativeContent">
                    <div style="text-align: center; padding: 60px 20px;">
                        <i class="fa-solid fa-spinner fa-spin" style="font-size: 48px; color: #3b82f6;"></i>
                        <p style="margin-top: 20px; color: #64748b;">Cargando datos cualitativos...</p>
                    </div>
                </div>
            </div>
        """
        
        # Usar wrapper para estructura completa
        bootstrap_js = '<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>'
        
        return dashboard_layout.get_html_wrapper(
            title='Dashboard de Métricas',
            content=content,
            sidebar_html=sidebar_html,
            topbar_html=topbar_html,
            styles=dashboard_styles.get_common_styles(),
            scripts=self._scripts(),
            head_extra=bootstrap_js
        )

    def _build_html(self, metrics, groups, evaluations, filters, role_info, kpi_html, charts):
        """Construye el HTML completo del dashboard."""
        # Usar utilidades compartidas
        role_badge = dashboard_helpers.get_role_badge(role_info)
        filter_controls = self._build_filter_controls(metrics, groups, evaluations, filters)
        sidebar_html = dashboard_layout.get_sidebar(role_info, active_section='home')
        
        # Topbar con fecha
        date_str = dashboard_helpers.format_date(fields.Date.today())
        topbar_html = dashboard_layout.get_topbar(
            title='Inicio',
            subtitle=f'<i class="fa-regular fa-calendar me-2"></i>{date_str}',
            role_badge=role_badge
        )
        
        home_html = self._home_section(metrics, groups, evaluations, filters, role_info)
        
        charts_html = '\n'.join(charts) if charts else '<p class="text-muted">No hay gráficos para mostrar</p>'
        
        # Construir contenido de las secciones
        content = f"""
            <!-- Sección Home -->
            <div class="content-section active" id="section-home">
                {home_html}
            </div>
            
            <!-- Sección Datos Cuantitativos -->
            <div class="content-section" id="section-quantitative">
                <div class="container-fluid">
                    {filter_controls}
                    
                    <div class="kpi-container my-4">
                        {kpi_html}
                    </div>
                    
                    <div class="charts-container">
                        {charts_html}
                    </div>
                </div>
            </div>
            
            <!-- Sección Datos Cualitativos -->
            <div class="content-section" id="section-qualitative">
                <div id="qualitativeContent">
                    <div style="text-align: center; padding: 60px 20px;">
                        <i class="fa-solid fa-spinner fa-spin" style="font-size: 48px; color: #3b82f6;"></i>
                        <p style="margin-top: 20px; color: #64748b;">Cargando datos cualitativos...</p>
                    </div>
                </div>
            </div>
        """
        
        # Usar wrapper con Chart.js incluido
        chart_libs = '<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>\n' + \
                     '<script src="https://cdn.jsdelivr.net/npm/chartjs-adapter-date-fns@3.0.0/dist/chartjs-adapter-date-fns.bundle.min.js"></script>'
        
        return dashboard_layout.get_html_wrapper(
            title='Dashboard de Métricas',
            content=content,
            sidebar_html=sidebar_html,
            topbar_html=topbar_html,
            styles=dashboard_styles.get_common_styles(),
            scripts=self._scripts(),
            head_extra=chart_libs
        )

    # Método obsoleto - usar dashboard_helpers.get_role_badge() en su lugar
    # def _get_role_badge(self, role_info):
    #     ...

    def _build_filter_controls(self, metrics, groups, evaluations, filters):
        """Construye los controles de filtrado."""
        # Pills de métricas
        metric_checks = ''
        selected_metrics = filters.get('metric_names', [])
        for m in metrics:
            active = 'active' if m['name'] in selected_metrics or not selected_metrics else ''
            metric_checks += f"""
            <span class="filter-pill metric-pill {active}" data-type="metric" data-value="{m['name']}" onclick="togglePill(this)">
                {m['label']}
            </span>
            <input type="hidden" class="metric-input" name="metric_{m['name']}" value="{m['name']}" {'disabled' if not active else ''}>
            """

        # Pills de grupos
        groups_checks = ''
        selected_groups = filters.get('group_ids', [])
        for g in groups:
            active = 'active' if g['id'] in selected_groups or not selected_groups else ''
            
            groups_checks += f"""
            <span class="filter-pill group-pill {active}" data-type="group" data-value="{g['id']}" onclick="togglePill(this)">
                {g['name']}
            </span>
            <input type="hidden" class="group-input" name="group_{g['id']}" value="{g['id']}" {'disabled' if not active else ''}>
            """

        # Pills de evaluaciones
        eval_checks = ''
        selected_evals = filters.get('evaluation_ids', [])
        for e in evaluations:
            active = 'active' if e['id'] in selected_evals or not selected_evals else ''
            
            eval_checks += f"""
            <span class="filter-pill eval-pill {active}" data-type="eval" data-value="{e['id']}" onclick="togglePill(this)">
                {e['name']}
            </span>
            <input type="hidden" class="eval-input" name="eval_{e['id']}" value="{e['id']}" {'disabled' if not active else ''}>
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
                                <div class="filter-pills-container">
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
                                <div class="filter-pills-container">
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
                                <div class="filter-pills-container">
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
                    <input type="hidden" name="section" id="section_input" value="quantitative">
                </form>
            </div>
        </div>
        """

    # Método obsoleto - usar dashboard_styles.get_common_styles() en su lugar
    # def _styles(self):
    #     ...
    
    def _home_section(self, metrics, groups, evaluations, filters, role_info):
        """Sección Home simplificada."""
        return f"""
    <div class="home-section">
        <div class="welcome-banner">
            <h2>
                <i class="fa-solid fa-hand-wave me-3" style="color: #f59e0b;"></i>
                Bienvenido al Dashboard
            </h2>
            <p>Utiliza el menú lateral para navegar entre las diferentes secciones</p>
        </div>
    </div>
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
        
        function togglePill(pill) {
            pill.classList.toggle('active');
            // Encontrar el input hidden asociado
            const input = pill.nextElementSibling;
            if (input && input.tagName === 'INPUT') {
                input.disabled = !pill.classList.contains('active');
            }
        }
        
        function selectAllMetrics() {
            document.querySelectorAll('.metric-pill').forEach(pill => {
                pill.classList.add('active');
                const input = pill.nextElementSibling;
                if (input && input.tagName === 'INPUT') input.disabled = false;
            });
        }
        
        function selectNoneMetrics() {
            document.querySelectorAll('.metric-pill').forEach(pill => {
                pill.classList.remove('active');
                const input = pill.nextElementSibling;
                if (input && input.tagName === 'INPUT') input.disabled = true;
            });
        }
        
        function selectAllGroups() {
            document.querySelectorAll('.group-pill').forEach(pill => {
                pill.classList.add('active');
                const input = pill.nextElementSibling;
                if (input && input.tagName === 'INPUT') input.disabled = false;
            });
        }
        
        function selectNoneGroups() {
            document.querySelectorAll('.group-pill').forEach(pill => {
                pill.classList.remove('active');
                const input = pill.nextElementSibling;
                if (input && input.tagName === 'INPUT') input.disabled = true;
            });
        }
        
        function selectAllEvals() {
            document.querySelectorAll('.eval-pill').forEach(pill => {
                pill.classList.add('active');
                const input = pill.nextElementSibling;
                if (input && input.tagName === 'INPUT') input.disabled = false;
            });
        }
        
        function selectNoneEvals() {
            document.querySelectorAll('.eval-pill').forEach(pill => {
                pill.classList.remove('active');
                const input = pill.nextElementSibling;
                if (input && input.tagName === 'INPUT') input.disabled = true;
            });
        }
        
        function clearDates() {
            document.getElementById('date_from').value = '';
            document.getElementById('date_to').value = '';
        }
        
        document.getElementById('hub-filters').addEventListener('submit', function(e) {
            // Consolidar pills activas en hidden inputs
            const metricPills = document.querySelectorAll('.metric-pill.active');
            const metricValues = Array.from(metricPills).map(p => p.dataset.value);
            document.getElementById('metric_names_input').value = metricValues.join(',');
            
            const groupPills = document.querySelectorAll('.group-pill.active');
            const groupValues = Array.from(groupPills).map(p => p.dataset.value);
            document.getElementById('group_ids_input').value = groupValues.join(',');
            
            const evalPills = document.querySelectorAll('.eval-pill.active');
            const evalValues = Array.from(evalPills).map(p => p.dataset.value);
            document.getElementById('evaluation_ids_input').value = evalValues.join(',');
            
            // Guardar la sección actual
            const activeSection = document.querySelector('.sidebar-item.active')?.dataset.section || 'quantitative';
            document.getElementById('section_input').value = activeSection;
        });
        
        // Navegación entre secciones
        function navigateTo(section) {
            // Actualizar items del sidebar
            document.querySelectorAll('.sidebar-item').forEach(item => {
                item.classList.remove('active');
            });
            document.querySelector(`[data-section="${section}"]`).classList.add('active');
            
            // Actualizar secciones de contenido
            document.querySelectorAll('.content-section').forEach(sec => {
                sec.classList.remove('active');
            });
            document.getElementById(`section-${section}`).classList.add('active');
            
            // Actualizar título
            const titles = {
                'home': 'Inicio',
                'quantitative': 'Datos Cuantitativos',
                'qualitative': 'Datos Cualitativos'
            };
            document.getElementById('sectionTitle').textContent = titles[section] || section;
            
            // Cargar contenido cualitativo si es necesario
            if (section === 'qualitative' && !window.qualitativeLoaded) {
                loadQualitativeContent();
            }
        }
        
        // Cargar contenido cualitativo
        function loadQualitativeContent() {
            window.qualitativeLoaded = true;
            const contentDiv = document.getElementById('qualitativeContent');
            
            fetch('/aulametrics/qualitative/dashboard?embedded=true')
                .then(response => response.text())
                .then(html => {
                    contentDiv.innerHTML = html;
                    
                    // Ejecutar scripts si los hay
                    const scripts = contentDiv.querySelectorAll('script');
                    scripts.forEach(oldScript => {
                        const newScript = document.createElement('script');
                        if (oldScript.src) {
                            newScript.src = oldScript.src;
                            if (oldScript.src.includes('d3')) {
                                newScript.onload = function() {
                                    console.log('D3 cargado:', oldScript.src);
                                };
                            }
                        } else {
                            newScript.textContent = oldScript.textContent;
                        }
                        oldScript.parentNode.replaceChild(newScript, oldScript);
                    });
                    
                    // Inicializar wordclouds
                    setTimeout(() => {
                        console.log('Intentando inicializar wordclouds...');
                        if (typeof initWordcloudCounselor !== 'undefined') {
                            console.log('Llamando a initWordcloudCounselor');
                            initWordcloudCounselor();
                        } else if (typeof initWordcloudTutor !== 'undefined') {
                            console.log('Llamando a initWordcloudTutor');
                            initWordcloudTutor();
                        } else {
                            console.log('No se encontraron funciones de inicialización de wordcloud');
                        }
                    }, 500);
                })
                .catch(error => {
                    contentDiv.innerHTML = '<div style="text-align: center; padding: 60px 20px;"><i class="fa-solid fa-exclamation-triangle" style="font-size: 48px; color: #ef4444;"></i><p style="margin-top: 20px; color: #64748b;">Error al cargar datos cualitativos</p></div>';
                    console.error('Error cargando datos cualitativos:', error);
                });
        }
        
        // Al cargar la página, navegar a la sección indicada en la URL
        document.addEventListener('DOMContentLoaded', function() {
            const urlParams = new URLSearchParams(window.location.search);
            const section = urlParams.get('section');
            if (section && ['home', 'quantitative', 'qualitative'].includes(section)) {
                navigateTo(section);
            }
            
            // Event delegation para formulario cualitativo (interceptar submit)
            document.addEventListener('submit', function(e) {
                const form = e.target;
                
                // Solo interceptar si es el formulario cualitativo embebido
                if (form.id === 'qualitativeFiltersForm') {
                    e.preventDefault();
                    
                    const formData = new FormData(form);
                    const params = new URLSearchParams();
                    
                    for (const [key, value] of formData.entries()) {
                        if (value) params.append(key, value);
                    }
                    params.append('embedded', 'true');
                    
                    const url = '/aulametrics/qualitative/dashboard?' + params.toString();
                    
                    fetch(url)
                        .then(response => response.text())
                        .then(html => {
                            const contentDiv = document.getElementById('qualitativeContent');
                            if (contentDiv) {
                                contentDiv.innerHTML = html;
                                
                                // Re-ejecutar scripts
                                const scripts = contentDiv.querySelectorAll('script');
                                scripts.forEach(oldScript => {
                                    const newScript = document.createElement('script');
                                    if (oldScript.src) {
                                        newScript.src = oldScript.src;
                                    } else {
                                        newScript.textContent = oldScript.textContent;
                                    }
                                    oldScript.parentNode.replaceChild(newScript, oldScript);
                                });
                                
                                // Reinicializar wordclouds
                                setTimeout(() => {
                                    if (typeof initWordcloudCounselor !== 'undefined') {
                                        initWordcloudCounselor();
                                    } else if (typeof initWordcloudTutor !== 'undefined') {
                                        initWordcloudTutor();
                                    }
                                }, 300);
                            }
                        })
                        .catch(error => {
                            console.error('Error al filtrar datos cualitativos:', error);
                            alert('Error al aplicar filtros');
                        });
                }
            });
        });
    </script>
        """
