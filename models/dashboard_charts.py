# -*- coding: utf-8 -*-
"""
Dashboard Charts - Generación de dashboard con métricas filtradas
"""
from odoo import models, api, fields
import pandas as pd
import json


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
        elif metric_type == 'text':
            return self._chart_text_metric(df_metric, metric_label)
        
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
        """Gráfico de barras horizontales para métricas JSON."""
        if df.empty:
            return ''
        
        # Contar frecuencias de respuestas
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
        
        # Ordenar por frecuencia descendente
        sorted_items = sorted(counts.items(), key=lambda x: x[1], reverse=True)
        labels = [item[0] for item in sorted_items[:10]]  # Top 10
        values = [item[1] for item in sorted_items[:10]]
        
        chart_id = f'chart_{label.replace(" ", "_").replace("/", "_")}'
        
        return f'''
        <div class="card">
            <div class="card-header">
                <h5 class="card-title">{label}</h5>
                <p class="card-subtitle">Distribución de respuestas</p>
            </div>
            <div class="card-body">
                <canvas id="{chart_id}" height="300"></canvas>
            </div>
        </div>
        
        <script>
        new Chart(document.getElementById('{chart_id}'), {{
            type: 'bar',
            data: {{
                labels: {json.dumps(labels)},
                datasets: [{{
                    label: 'Frecuencia',
                    data: {json.dumps(values)},
                    backgroundColor: '#10b981',
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
                        bodyFont: {{ family: "'Inter', sans-serif", size: 13 }}
                    }}
                }},
                scales: {{
                    x: {{
                        beginAtZero: true,
                        grid: {{ color: '#f1f5f9', drawBorder: false }},
                        ticks: {{
                            font: {{ size: 12, family: "'Inter', sans-serif" }},
                            color: '#94a3b8'
                        }}
                    }},
                    y: {{
                        grid: {{ display: false, drawBorder: false }},
                        ticks: {{
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

    def _chart_text_metric(self, df, label):
        """Tabla profesional para métricas de texto."""
        if df.empty:
            return ''
        
        # Mostrar solo primeros 50 registros
        df_sample = df[['student_name', 'value_text']].head(50)
        
        rows_html = ''
        for _, row in df_sample.iterrows():
            rows_html += f'''
            <tr>
                <td>{row['student_name']}</td>
                <td>{row['value_text']}</td>
            </tr>
            '''
        
        return f"""
        <div class="card">
            <div class="card-header">
                <h5 class="card-title">{label}</h5>
                <p class="card-subtitle">Respuestas de texto</p>
            </div>
            <div class="card-body">
                <div style="max-height: 400px; overflow-y: auto;">
                    <table>
                        <thead>
                            <tr>
                                <th>Estudiante</th>
                                <th>Respuesta</th>
                            </tr>
                        </thead>
                        <tbody>
                            {rows_html}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
        """

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
        role_badge = self._get_role_badge(role_info)
        filter_controls = self._build_filter_controls(metrics, groups, evaluations, filters)
        
        return f"""
        <!DOCTYPE html>
        <html lang="es">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Dashboard de Métricas - AulaMetrics</title>
            <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
            <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
            <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
            {self._styles()}
        </head>
        <body>
            {self._header(role_badge, role_info)}
            
            <!-- Contenido de las pestañas -->
            <div class="tab-content" id="dashboardTabContent">
                <!-- Pestaña Datos Cuantitativos -->
                <div class="tab-pane fade show active" id="quantitative" role="tabpanel" aria-labelledby="quantitative-tab">
                    <div class="container-fluid mt-4">
                        {filter_controls}
                        <div class="empty-state">
                            <i class="fa-solid fa-chart-line fa-4x"></i>
                            <h3>No hay datos disponibles</h3>
                            <p>Ajusta los filtros para ver resultados</p>
                        </div>
                    </div>
                </div>
                
                <!-- Pestaña Datos Cualitativos -->
                <div class="tab-pane fade" id="qualitative" role="tabpanel" aria-labelledby="qualitative-tab">
                    <div id="qualitativeContent">
                        <div style="text-align: center; padding: 60px 20px;">
                            <i class="fa-solid fa-spinner fa-spin" style="font-size: 48px; color: #3b82f6;"></i>
                            <p style="margin-top: 20px; color: #64748b;">Cargando datos cualitativos...</p>
                        </div>
                    </div>
                </div>
            </div>
            
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
        <html lang="es">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Dashboard de Métricas - AulaMetrics</title>
            <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
            <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
            <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
            <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
            <script src="https://cdn.jsdelivr.net/npm/chartjs-adapter-date-fns@3.0.0/dist/chartjs-adapter-date-fns.bundle.min.js"></script>
            {self._styles()}
        </head>
        <body>
            {self._header(role_badge, role_info)}
            
            <!-- Contenido de las pestañas -->
            <div class="tab-content" id="dashboardTabContent">
                <!-- Pestaña Datos Cuantitativos -->
                <div class="tab-pane fade show active" id="quantitative" role="tabpanel" aria-labelledby="quantitative-tab">
                    <div class="container-fluid mt-4">
                        {filter_controls}
                        
                        <div class="kpi-container my-4">
                            {kpi_html}
                        </div>
                        
                        <div class="charts-container">
                            {charts_html}
                        </div>
                    </div>
                </div>
                
                <!-- Pestaña Datos Cualitativos -->
                <div class="tab-pane fade" id="qualitative" role="tabpanel" aria-labelledby="qualitative-tab">
                    <div id="qualitativeContent">
                        <div style="text-align: center; padding: 60px 20px;">
                            <i class="fa-solid fa-spinner fa-spin" style="font-size: 48px; color: #3b82f6;"></i>
                            <p style="margin-top: 20px; color: #64748b;">Cargando datos cualitativos...</p>
                        </div>
                    </div>
                </div>
            </div>
            
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
        """Estilos profesionales tipo Stripe/Linear/Notion."""
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
        
        .dashboard-header {
            background: white;
            padding: 24px 32px;
            border-bottom: 1px solid #e5e7eb;
            margin-bottom: 32px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
        }
        
        .header-title h1 {
            font-size: 24px;
            font-weight: 700;
            margin: 0;
            color: #0f172a;
            letter-spacing: -0.5px;
        }
        
        .header-meta {
            color: #64748b;
            font-size: 14px;
            margin-top: 4px;
        }
        
        .container-fluid {
            max-width: 1400px;
            margin: 0 auto;
            padding: 0 24px;
        }
        
        /* Filtros */
        .filter-panel {
            background: white;
            border: 1px solid #e5e7eb;
            border-radius: 10px;
            overflow: hidden;
            margin-bottom: 32px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.04);
        }
        
        .filter-header {
            padding: 16px 20px;
            background: white;
            border-bottom: 1px solid #e5e7eb;
            display: flex;
            justify-content: space-between;
            align-items: center;
            cursor: pointer;
            transition: background 0.2s;
        }
        
        .filter-header:hover {
            background: #fafbfc;
        }
        
        .filter-header h5 {
            font-size: 15px;
            font-weight: 600;
            color: #0f172a;
            margin: 0;
        }
        
        .filter-content {
            padding: 24px;
            background: white;
            display: none;
        }
        
        .filter-content.show {
            display: block;
        }
        
        .filter-section {
            background: #fafbfc;
            padding: 20px;
            border-radius: 8px;
            border: 1px solid #f1f5f9;
            height: 100%;
        }
        
        .filter-section .form-label {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 12px;
            font-size: 13px;
            font-weight: 600;
            color: #475569;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        .filter-section .btn-link {
            padding: 0 8px;
            text-decoration: none;
            color: #3b82f6;
            font-size: 12px;
            font-weight: 500;
            text-transform: none;
        }
        
        .filter-section .btn-link:hover {
            color: #2563eb;
            text-decoration: underline;
        }
        
        .checkbox-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
            gap: 8px;
        }
        
        .filter-checkbox {
            padding: 8px 12px;
            border-radius: 6px;
            transition: all 0.2s;
            background: white;
            border: 1px solid transparent;
        }
        
        .filter-checkbox:hover {
            background: white;
            border-color: #e5e7eb;
        }
        
        .filter-checkbox input[type=\"checkbox\"] {
            width: 16px;
            height: 16px;
            cursor: pointer;
            accent-color: #3b82f6;
        }
        
        .filter-checkbox label {
            cursor: pointer;
            margin-left: 8px;
            margin-bottom: 0;
            font-size: 14px;
            color: #334155;
            user-select: none;
        }
        
        .form-control, .form-select {
            border-radius: 6px;
            border: 1px solid #e5e7eb;
            padding: 8px 12px;
            font-size: 14px;
            font-family: 'Inter', sans-serif;
            transition: all 0.2s;
        }
        
        .form-control:focus, .form-select:focus {
            border-color: #3b82f6;
            box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
            outline: none;
        }
        
        /* KPIs */
        .kpi-container {
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
        
        /* Tarjetas de gráficos */
        .charts-container {
            display: grid;
            gap: 24px;
        }
        
        .card {
            background: white;
            border: 1px solid #e5e7eb;
            border-radius: 10px;
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
        
        .card-subtitle {
            font-size: 13px;
            color: #64748b;
            margin: 4px 0 0 0;
            font-weight: 400;
        }
        
        .card-body {
            padding: 24px;
        }
        
        /* Tablas */
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
        
        /* Botones */
        .btn {
            padding: 8px 16px;
            border-radius: 6px;
            font-size: 14px;
            font-weight: 500;
            font-family: 'Inter', sans-serif;
            border: 1px solid transparent;
            cursor: pointer;
            transition: all 0.2s;
            text-decoration: none;
            display: inline-block;
        }
        
        .btn-primary {
            background: #3b82f6;
            color: white;
            border-color: #3b82f6;
        }
        
        .btn-primary:hover {
            background: #2563eb;
            border-color: #2563eb;
        }
        
        .btn-outline-secondary {
            background: white;
            color: #64748b;
            border-color: #e5e7eb;
        }
        
        .btn-outline-secondary:hover {
            background: #fafbfc;
            border-color: #d1d5db;
            color: #475569;
        }
        
        .btn-sm {
            padding: 6px 12px;
            font-size: 13px;
        }
        
        .btn-lg {
            padding: 12px 20px;
            font-size: 15px;
        }
        
        /* Badges */
        .badge {
            display: inline-block;
            padding: 4px 10px;
            border-radius: 6px;
            font-size: 12px;
            font-weight: 500;
            letter-spacing: 0.3px;
        }
        
        .badge.bg-danger {
            background: #fee2e2;
            color: #991b1b;
        }
        
        .badge.bg-primary {
            background: #dbeafe;
            color: #1e40af;
        }
        
        .badge.bg-warning {
            background: #fef3c7;
            color: #92400e;
        }
        
        .badge.bg-success {
            background: #d1fae5;
            color: #065f46;
        }
        
        /* Empty state */
        .empty-state {
            text-align: center;
            padding: 80px 20px;
            color: #94a3b8;
        }
        
        .empty-state i {
            color: #cbd5e1;
            margin-bottom: 20px;
        }
        
        .empty-state h3 {
            font-size: 20px;
            font-weight: 600;
            color: #64748b;
            margin-bottom: 8px;
        }
        
        .empty-state p {
            font-size: 14px;
            color: #94a3b8;
        }
        
        /* Utilidades */
        .mt-4 { margin-top: 24px; }
        .my-4 { margin-top: 24px; margin-bottom: 24px; }
        .ms-2 { margin-left: 8px; }
        .me-2 { margin-right: 8px; }
        .mb-4 { margin-bottom: 24px; }
        .w-100 { width: 100%; }
        .text-primary { color: #3b82f6; }
        .text-muted { color: #94a3b8; }
        .row { display: flex; flex-wrap: wrap; margin: 0 -12px; }
        .col-12 { flex: 0 0 100%; max-width: 100%; padding: 0 12px; }
        .col-md-4 { flex: 0 0 33.333%; max-width: 33.333%; padding: 0 12px; }
        .col-md-6 { flex: 0 0 50%; max-width: 50%; padding: 0 12px; }
        .g-2 { gap: 8px; }
        
        @media (max-width: 768px) {
            .col-md-4, .col-md-6 { flex: 0 0 100%; max-width: 100%; }
        }
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
    
    <!-- Pestañas de navegación -->
    <div class="container-fluid mt-3">
        <ul class="nav nav-tabs" id="dashboardTabs" role="tablist">
            <li class="nav-item" role="presentation">
                <button class="nav-link active" id="quantitative-tab" data-bs-toggle="tab" data-bs-target="#quantitative" 
                        type="button" role="tab" aria-controls="quantitative" aria-selected="true">
                    <i class="fa-solid fa-chart-line me-2"></i>Datos Cuantitativos
                </button>
            </li>
            <li class="nav-item" role="presentation">
                <button class="nav-link" id="qualitative-tab" data-bs-toggle="tab" data-bs-target="#qualitative" 
                        type="button" role="tab" aria-controls="qualitative" aria-selected="false">
                    <i class="fa-solid fa-comments me-2"></i>Datos Cualitativos
                </button>
            </li>
        </ul>
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
        
        // Cargar contenido cualitativo cuando se activa la pestaña
        let qualitativeLoaded = false;
        document.getElementById('qualitative-tab').addEventListener('click', function() {
            if (!qualitativeLoaded) {
                qualitativeLoaded = true;
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
                                // Si es una librería externa, esperar a que cargue
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
                        
                        // Dar tiempo a que los scripts se ejecuten y luego inicializar wordclouds
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
        });
    </script>
        """
