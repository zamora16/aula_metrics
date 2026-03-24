# -*- coding: utf-8 -*-
"""
Dashboard Chart Evolution - Gráficos de evolución temporal de métricas.
"""
import json
from odoo import models
from ...utils import palette


class DashboardChartsEvolution(models.TransientModel):
    _inherit = 'aula_metrics.dashboard.charts'

    def _chart_numeric_evolution_by_course(self, df, label, y_max=100, y_min=0):
        """Evolución temporal de la métrica por curso (Management)."""
        # Agrupar por evaluación (no por timestamp individual)
        evaluations = df.groupby('evaluation_name')['completed_at'].min().sort_values()
        
        if len(evaluations) < 2:
            return ''
        
        cursos = sorted(df['curso'].unique())
        color_palette = palette.METRICS_PALETTE
        
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
                <figure class="mb-0">
                    <figcaption class="visually-hidden">Evolución de {label} por curso académico. Gráfico de líneas con la tendencia temporal de la métrica para cada curso.</figcaption>
                    <canvas id="{chart_id}" height="260" role="img" aria-label="Evolución: {label} por curso académico"></canvas>
                </figure>
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
                        min: {y_min},
                        max: {y_max},
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

    def _chart_numeric_evolution_distribution(self, df, label, y_max=100, y_min=0):
        """Evolución temporal: trayectorias individuales + media del grupo (Tutor - anónimo)."""
        # Agrupar por evaluación (no por timestamp individual)
        evaluations = df.groupby('evaluation_name')['completed_at'].min().sort_values()
        
        if len(evaluations) < 2:
            return ''
        
        # Dataset 1: Media del grupo en cada evaluación
        group_data_points = []
        for eval_name, eval_date in evaluations.items():
            df_eval = df[df['evaluation_name'] == eval_name]['value_numeric'].dropna()
            if len(df_eval) > 0:
                group_data_points.append({
                    'x': eval_date.isoformat() if hasattr(eval_date, 'isoformat') else str(eval_date),
                    'y': float(df_eval.mean())
                })
        
        if not group_data_points:
            return ''
        
        # Dataset 2: Trayectorias individuales de cada alumno (anonimizado)
        # Diferenciación accesible: color + patrón de trazo + forma de punto
        _DASH_PATTERNS = [[5, 5], [10, 4], [15, 5, 5, 5], [3, 3], [8, 3, 2, 3], [12, 3, 3, 3]]
        _POINT_STYLES  = ['circle', 'rect', 'triangle', 'cross', 'star', 'rectRot']

        individual_datasets = []
        students = df['student_id'].unique()
        total_students = len(students)
        
        for idx, student_id in enumerate(students, 1):
            df_student = df[df['student_id'] == student_id]
            student_data_points = []
            
            for eval_name, eval_date in evaluations.items():
                df_student_eval = df_student[df_student['evaluation_name'] == eval_name]['value_numeric'].dropna()
                if len(df_student_eval) > 0:
                    student_data_points.append({
                        'x': eval_date.isoformat() if hasattr(eval_date, 'isoformat') else str(eval_date),
                        'y': float(df_student_eval.iloc[0])
                    })
            
            # Solo agregar si tiene al menos 2 puntos temporales
            if len(student_data_points) >= 2:
                # Color + trazo + punto únicos por alumno (accesible en blanco/negro)
                hue = (idx * 360 / total_students) % 360
                individual_datasets.append({
                    'label': f'Alumno {idx}',
                    'data': student_data_points,
                    'borderColor': f'hsl({hue}, 70%, 45%)',
                    'backgroundColor': 'transparent',
                    'borderWidth': 2,
                    'borderDash': _DASH_PATTERNS[(idx - 1) % len(_DASH_PATTERNS)],
                    'tension': 0.2,
                    'pointRadius': 4,
                    'pointHoverRadius': 6,
                    'pointStyle': _POINT_STYLES[(idx - 1) % len(_POINT_STYLES)],
                    'pointBackgroundColor': f'hsl({hue}, 70%, 45%)',
                    'pointBorderColor': '#ffffff',
                    'pointBorderWidth': 1
                })
        
        # Dataset de media grupal (destacado con línea negra gruesa)
        group_dataset = {
            'label': 'Media del grupo',
            'data': group_data_points,
            'borderColor': '#1e293b',
            'backgroundColor': '#1e293b20',
            'borderWidth': 4,
            'borderDash': [],
            'tension': 0.3,
            'fill': True,
            'pointRadius': 5,
            'pointHoverRadius': 7,
            'pointBackgroundColor': '#1e293b',
            'pointBorderColor': '#ffffff',
            'pointBorderWidth': 2,
            'order': 0  # Dibujarse encima
        }
        
        # Combinar: primero individuales (fondo), luego media (destacada)
        all_datasets = individual_datasets + [group_dataset]
        
        chart_id = f'evolution_{label.replace(" ", "_").replace("/", "_").replace(".", "_")}'
        
        return f'''
        <div class="card">
            <div class="card-header">
                <h5 class="card-title">Evolución: {label}</h5>
                <p class="card-subtitle">Trayectorias individuales (coloreadas) y media del grupo (negro)</p>
            </div>
            <div class="card-body">
                <figure class="mb-0">
                    <figcaption class="visually-hidden">Evolución de {label}: trayectorias individuales y media del grupo. Línea gruesa negra = media del grupo; líneas delgadas con diferentes trazos = trayectorias individuales anónimas.</figcaption>
                    <canvas id="{chart_id}" height="260" role="img" aria-label="Evolución: {label} — trayectorias individuales y media del grupo"></canvas>
                </figure>
            </div>
        </div>
        
        <script>
        new Chart(document.getElementById('{chart_id}'), {{
            type: 'line',
            data: {{
                datasets: {json.dumps(all_datasets)}
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
                                if (context.dataset.label === 'Media del grupo') {{
                                    return 'Media: ' + context.parsed.y.toFixed(1) + ' pts';
                                }} else {{
                                    return context.dataset.label + ': ' + context.parsed.y.toFixed(1) + ' pts';
                                }}
                            }}
                        }}
                    }}
                }},
                interaction: {{
                    mode: 'nearest',
                    axis: 'x',
                    intersect: false
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
                        min: {y_min},
                        max: {y_max},
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

    def _chart_numeric_evolution_by_groups(self, df, label, y_max=100, y_min=0):
        """Evolución temporal de la métrica por grupo (Counselor)."""
        # Agrupar por evaluación (no por timestamp individual)
        evaluations = df.groupby('evaluation_name')['completed_at'].min().sort_values()
        
        if len(evaluations) < 2:
            return ''
        
        grupos = sorted(df['group_name'].unique())
        color_palette = palette.METRICS_PALETTE
        
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
                <figure class="mb-0">
                    <figcaption class="visually-hidden">Evolución de {label} por grupo. Gráfico de líneas con la tendencia temporal de la métrica para cada grupo académico.</figcaption>
                    <canvas id="{chart_id}" height="260" role="img" aria-label="Evolución: {label} por grupo"></canvas>
                </figure>
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
                        min: {y_min},
                        max: {y_max},
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

