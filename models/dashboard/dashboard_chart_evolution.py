# -*- coding: utf-8 -*-
"""
Dashboard Chart Evolution - Gráficos de evolución temporal de métricas.
"""
import json
from odoo import models
from ...utils import palette, dashboard_helpers, chart_defaults
from ...utils.constants import COURSE_LEVEL_MAP


class DashboardChartsEvolution(models.TransientModel):
    _inherit = 'aula_metrics.dashboard.charts'

    def _chart_numeric_evolution_by_course(self, df, label, y_max=100, y_min=0):
        """Evolución temporal de la métrica por curso (Management)."""
        # Agrupar por evaluación (no por timestamp individual)
        evaluations = df.groupby('evaluation_name')['completed_at'].min().sort_values()
        
        if len(evaluations) < 2:
            return f'''<div class="card"><div class="card-body" style="text-align:center;padding:40px 24px;color:var(--am-muted);"><i class="fa-solid fa-chart-line" aria-hidden="true" style="font-size:2rem;opacity:.35;margin-bottom:12px;display:block;"></i><p style="margin:0;font-size:14px;">Se necesitan al menos <strong>2 evaluaciones</strong> para mostrar la evolución de <strong>{label}</strong>.</p></div></div>'''
        
        cursos = sorted(df['curso'].unique())
        
        # Etiquetas del eje X = nombre de las evaluaciones en orden cronológico
        eval_labels = list(evaluations.index)
        
        # Preparar datasets por curso
        datasets = []
        for curso in cursos:
            df_curso = df[df['curso'] == curso]
            y_values = []
            for eval_name in eval_labels:
                df_eval = df_curso[df_curso['evaluation_name'] == eval_name]['value_numeric'].dropna()
                y_values.append(float(df_eval.mean()) if len(df_eval) > 0 else None)
            
            color = palette.get_color_for_course(curso)
            if any(v is not None for v in y_values):
                datasets.append({
                    'label': palette.get_label_for_course(curso),
                    'data': y_values,
                    'borderColor': color,
                    'backgroundColor': color + '20',
                    'tension': 0.3,
                    'spanGaps': True
                })
        
        if not datasets:
            return ''
        
        chart_id = f'evolution_{dashboard_helpers.sanitize_id(label)}'
        
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
                labels: {json.dumps(eval_labels)},
                datasets: {json.dumps(datasets)}
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: true,
                plugins: {{
                    legend: {json.dumps(chart_defaults.get_legend_series())},
                    tooltip: {chart_defaults.tooltip_js(chart_defaults.CALLBACKS_SCORE_LABEL)}
                }},
                scales: {{
                    x: {json.dumps(chart_defaults.get_scale_x_categorical())},
                    y: {json.dumps(chart_defaults.get_scale_y_score(y_min, y_max))}
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
            return f'''<div class="card"><div class="card-body" style="text-align:center;padding:40px 24px;color:var(--am-muted);"><i class="fa-solid fa-chart-line" aria-hidden="true" style="font-size:2rem;opacity:.35;margin-bottom:12px;display:block;"></i><p style="margin:0;font-size:14px;">Se necesitan al menos <strong>2 evaluaciones</strong> para mostrar la evolución de <strong>{label}</strong>.</p></div></div>'''
        
        # Etiquetas del eje X = nombre de las evaluaciones en orden cronológico
        eval_labels = list(evaluations.index)
        
        # Dataset 1: Media del grupo en cada evaluación
        group_y_values = [None] * len(eval_labels)
        for i, eval_name in enumerate(eval_labels):
            df_eval = df[df['evaluation_name'] == eval_name]['value_numeric'].dropna()
            if len(df_eval) > 0:
                group_y_values[i] = float(df_eval.mean())
        
        if all(v is None for v in group_y_values):
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
            y_values = [None] * len(eval_labels)
            for i, eval_name in enumerate(eval_labels):
                df_student_eval = df_student[df_student['evaluation_name'] == eval_name]['value_numeric'].dropna()
                if len(df_student_eval) > 0:
                    y_values[i] = float(df_student_eval.iloc[0])
            
            # Solo agregar si tiene al menos 2 puntos (no-None)
            if sum(1 for v in y_values if v is not None) >= 2:
                # Color + trazo + punto únicos por alumno (accesible en blanco/negro)
                hue = (idx * 360 / total_students) % 360
                individual_datasets.append({
                    'label': f'Alumno {idx}',
                    'data': y_values,
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
            'data': group_y_values,
            'borderColor': palette.UI_CHART_EMPHASIS,
            'backgroundColor': palette.UI_CHART_EMPHASIS + '20',
            'borderWidth': 4,
            'borderDash': [],
            'tension': 0.3,
            'fill': True,
            'pointRadius': 5,
            'pointHoverRadius': 7,
            'pointBackgroundColor': palette.UI_CHART_EMPHASIS,
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
                labels: {json.dumps(eval_labels)},
                datasets: {json.dumps(all_datasets)}
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: true,
                plugins: {{
                    legend: {json.dumps(chart_defaults.get_legend_series())},
                    tooltip: {chart_defaults.tooltip_js(chart_defaults.CALLBACKS_SCORE_LABEL_WITH_GROUP_MEAN)}
                }},
                interaction: {{
                    mode: 'nearest',
                    axis: 'x',
                    intersect: false
                }},
                scales: {{
                    x: {json.dumps(chart_defaults.get_scale_x_categorical())},
                    y: {json.dumps(chart_defaults.get_scale_y_score(y_min, y_max))}
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
            return f'''<div class="card"><div class="card-body" style="text-align:center;padding:40px 24px;color:var(--am-muted);"><i class="fa-solid fa-chart-line" aria-hidden="true" style="font-size:2rem;opacity:.35;margin-bottom:12px;display:block;"></i><p style="margin:0;font-size:14px;">Se necesitan al menos <strong>2 evaluaciones</strong> para mostrar la evolución de <strong>{label}</strong>.</p></div></div>'''
        
        grupos = sorted(df['group_name'].unique())
        
        # Etiquetas del eje X = nombre de las evaluaciones en orden cronológico
        eval_labels = list(evaluations.index)
        
        # Preparar datasets por grupo
        datasets = []
        for grupo in grupos:
            df_grupo = df[df['group_name'] == grupo]
            y_values = []
            for eval_name in eval_labels:
                df_eval = df_grupo[df_grupo['evaluation_name'] == eval_name]['value_numeric'].dropna()
                y_values.append(float(df_eval.mean()) if len(df_eval) > 0 else None)
            
            color = palette.get_color_for_label(grupo)
            if any(v is not None for v in y_values):
                datasets.append({
                    'label': grupo,
                    'data': y_values,
                    'borderColor': color,
                    'backgroundColor': color + '20',
                    'tension': 0.3,
                    'spanGaps': True
                })
        
        if not datasets:
            return ''
        
        chart_id = f'evolution_{dashboard_helpers.sanitize_id(label)}'
        
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
                labels: {json.dumps(eval_labels)},
                datasets: {json.dumps(datasets)}
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: true,
                plugins: {{
                    legend: {json.dumps(chart_defaults.get_legend_series())},
                    tooltip: {chart_defaults.tooltip_js(chart_defaults.CALLBACKS_SCORE_LABEL)}
                }},
                scales: {{
                    x: {json.dumps(chart_defaults.get_scale_x_categorical())},
                    y: {json.dumps(chart_defaults.get_scale_y_score(y_min, y_max))}
                }}
            }}
        }});
        </script>
        '''

    def _chart_numeric_evolution_by_tutor_group(self, df, label, segmentation_vars, y_max=100, y_min=0):
        """Evolución temporal: media del grupo del tutor vs centro vs nivel educativo.

        Tres series: Mi grupo (sólida) | Centro (discontinua 6-3) | Mi nivel (discontinua 3-3).
        Usa sudo() en las queries de MetricValue para superar las restricciones de ACL
        del tutor (que solo ve los registros de su propio grupo académico).
        El parámetro segmentation_vars se acepta por uniformidad con la firma del resto
        de métodos de evolución, pero la evolución siempre muestra las 3 series globales.
        """
        evaluations = df.groupby('evaluation_name')['completed_at'].min().sort_values()
        if len(evaluations) < 2:
            return (
                f'<div class="card"><div class="card-body" style="text-align:center;padding:40px 24px;'
                f'color:var(--am-muted);"><i class="fa-solid fa-chart-line" aria-hidden="true" '
                f'style="font-size:2rem;opacity:.35;margin-bottom:12px;display:block;"></i>'
                f'<p style="margin:0;font-size:14px;">Se necesitan al menos <strong>2 evaluaciones</strong>'
                f' para mostrar la evolución de <strong>{label}</strong>.</p></div></div>'
            )

        eval_labels = list(evaluations.index)
        metric_name = df['metric_name'].iloc[0]
        course_keys = [c for c in df['curso'].dropna().unique().tolist() if c]

        MetricValue = self.env['aula_metrics.metric_value']

        group_y  = []
        center_y = []
        level_y  = []

        for eval_name in eval_labels:
            # Mi grupo (df ya filtrado por ACL del tutor)
            df_eval = df[df['evaluation_name'] == eval_name]['value_numeric'].dropna()
            group_y.append(round(float(df_eval.mean()), 1) if len(df_eval) > 0 else None)

            # Centro — sudo para superar ACL del tutor
            mvs  = MetricValue.sudo().search([
                ('metric_name',        '=', metric_name),
                ('evaluation_id.name', '=', eval_name),
                ('value_float',        '!=', False),
            ])
            vals = [mv.value_float for mv in mvs if mv.value_float is not False]
            center_y.append(round(float(sum(vals) / len(vals)), 1) if vals else None)

            # Nivel educativo — sudo para superar ACL del tutor
            if course_keys:
                mvs_l  = MetricValue.sudo().search([
                    ('metric_name',                    '=',  metric_name),
                    ('evaluation_id.name',             '=',  eval_name),
                    ('academic_group_id.course_level', 'in', course_keys),
                    ('value_float',                    '!=', False),
                ])
                vals_l = [mv.value_float for mv in mvs_l if mv.value_float is not False]
                level_y.append(round(float(sum(vals_l) / len(vals_l)), 1) if vals_l else None)
            else:
                level_y.append(None)

        level_labels_list = [COURSE_LEVEL_MAP.get(k, k) for k in course_keys]
        level_label_str   = ' / '.join(level_labels_list) or 'Mi nivel'

        _COLOR_GROUP  = palette.METRICS_PALETTE[0]   # Academic Navy
        _COLOR_CENTER = palette.METRICS_PALETTE[5]   # Cyan/Teal
        _COLOR_LEVEL  = palette.METRICS_PALETTE[1]   # Chalkboard Green

        datasets = [{
            'label':           'Mi grupo',
            'data':            group_y,
            'borderColor':     _COLOR_GROUP,
            'backgroundColor': _COLOR_GROUP + '20',
            'borderWidth':     3,
            'tension':         0.3,
            'spanGaps':        True,
            'fill':            False,
        }]

        if any(v is not None for v in center_y):
            datasets.append({
                'label':           'Centro',
                'data':            center_y,
                'borderColor':     _COLOR_CENTER,
                'backgroundColor': 'transparent',
                'borderWidth':     2,
                'borderDash':      [6, 3],
                'tension':         0.3,
                'spanGaps':        True,
                'fill':            False,
            })

        if any(v is not None for v in level_y):
            datasets.append({
                'label':           level_label_str,
                'data':            level_y,
                'borderColor':     _COLOR_LEVEL,
                'backgroundColor': 'transparent',
                'borderWidth':     2,
                'borderDash':      [3, 3],
                'tension':         0.3,
                'spanGaps':        True,
                'fill':            False,
            })

        chart_id = f'evolution_tutor_{dashboard_helpers.sanitize_id(label)}'

        return f'''
        <div class="card">
            <div class="card-header">
                <h5 class="card-title">Evolución: {label}</h5>
                <p class="card-subtitle">Mi grupo vs centro vs mi nivel educativo</p>
            </div>
            <div class="card-body">
                <canvas id="{chart_id}" height="260"></canvas>
            </div>
        </div>

        <script>
        new Chart(document.getElementById('{chart_id}'), {{
            type: 'line',
            data: {{
                labels:   {json.dumps(eval_labels)},
                datasets: {json.dumps(datasets)}
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: true,
                plugins: {{
                    legend:  {json.dumps(chart_defaults.get_legend_series())},
                    tooltip: {chart_defaults.tooltip_js(chart_defaults.CALLBACKS_SCORE_LABEL)}
                }},
                scales: {{
                    x: {json.dumps(chart_defaults.get_scale_x_categorical())},
                    y: {json.dumps(chart_defaults.get_scale_y_score(y_min, y_max))}
                }}
            }}
        }});
        </script>
        '''
