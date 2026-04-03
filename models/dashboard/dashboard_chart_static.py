# -*- coding: utf-8 -*-
"""
Dashboard Chart Static - Gráficos comparativos estáticos de métricas.
"""
import json
import pandas as pd
from odoo import models
from ...utils import palette, dashboard_helpers, chart_defaults
from ...utils.constants import COURSE_LEVEL_MAP


class DashboardChartsStatic(models.TransientModel):
    _inherit = 'aula_metrics.dashboard.charts'

    def _chart_numeric_by_course(self, df, label, segmentation_vars, y_max=100, y_min=0):
        """Vista Management: Agregado por curso académico (barras compactas)."""
        cursos = sorted(df['curso'].unique())
        stats = []
        
        # Preparar datos generales
        for curso in cursos:
            df_curso = df[df['curso'] == curso]
            df_curso_values = df_curso['value_numeric'].dropna()
            if len(df_curso_values) > 0:
                mean_val = float(df_curso_values.mean())
                n_alumnos = len(df_curso['student_id'].unique())
                n_grupos = len(df_curso['group_id'].unique())
                stats.append({
                    'curso': curso,
                    'mean': mean_val,
                    'n_alumnos': n_alumnos,
                    'n_grupos': n_grupos,
                    'color': palette.get_color_for_course(curso)
                })
        
        if not stats:
            return ''
        
        # Preparar datos de segmentación para TODAS las variables disponibles
        stats_by_segmentation = {}
        MetricValue = self.env['aula_metrics.metric_value']
        
        for seg_var in segmentation_vars:
            var_value = seg_var['value']
            var_type = seg_var['type']
            
            stats_by_segmentation[var_value] = {}
            
            # Pre-fetch para metric_json: una sola query para todos los alumnos
            seg_map = {}
            if var_type == 'metric_json':
                all_student_ids = [int(sid) for sid in df['student_id'].unique() if sid != "***"]
                all_seg_records = MetricValue.search([
                    ('student_id', 'in', all_student_ids),
                    ('metric_name', '=', var_value),
                    ('value_json', '!=', False)
                ])
                seg_map = {rec.student_id.id: rec.value_json for rec in all_seg_records}
            
            for curso in cursos:
                df_curso = df[df['curso'] == curso]
                display_label = palette.get_label_for_course(curso)
                stats_by_segmentation[var_value][display_label] = {}
                
                if var_type == 'partner_field' and var_value == 'gender':
                    # Género desde res.partner
                    gender_map = {'male': 'Masculino', 'female': 'Femenino', 'other': 'Otro', 'prefer_not_say': 'Prefiere no decir'}
                    for gender_key, gender_label in gender_map.items():
                        df_segment = df_curso[df_curso['student_gender'] == gender_key]
                        values = df_segment['value_numeric'].dropna()
                        if len(values) > 0:
                            stats_by_segmentation[var_value][display_label][gender_label] = {
                                'mean': float(values.mean()),
                                'count': int(len(values))
                            }
                
                elif var_type == 'metric_json':
                    # Variable de opciones múltiples — datos pre-cargados en seg_map
                    for student_id in df_curso['student_id'].unique():
                        if student_id == "***":  # Skip anonymized
                            continue
                        
                        selected_options = seg_map.get(int(student_id))
                        if not selected_options:
                            continue
                        
                        student_value = df_curso[df_curso['student_id'] == student_id]['value_numeric'].iloc[0]
                        
                        if pd.notna(student_value):
                            for option in selected_options:
                                if option not in stats_by_segmentation[var_value][display_label]:
                                    stats_by_segmentation[var_value][display_label][option] = {
                                        'sum': 0.0,
                                        'count': 0
                                    }
                                stats_by_segmentation[var_value][display_label][option]['sum'] += float(student_value)
                                stats_by_segmentation[var_value][display_label][option]['count'] += 1
                    
                    # Calcular medias
                    for option in stats_by_segmentation[var_value][display_label]:
                        data = stats_by_segmentation[var_value][display_label][option]
                        if data['count'] > 0:
                            data['mean'] = data['sum'] / data['count']
                            del data['sum']
        
        chart_id = f'chart_cursos_{dashboard_helpers.sanitize_id(label)}'
        labels = [palette.get_label_for_course(s['curso']) for s in stats]
        means = [s['mean'] for s in stats]
        colors = [s['color'] for s in stats]
        
        # Obtener umbrales configurados para esta métrica
        metric_name = df.iloc[0]['metric_name'] if not df.empty else None
        thresholds = self._get_thresholds_for_metric(metric_name) if metric_name else []
        
        chart_height = min(350, max(200, len(stats) * 25))
        segment_options_html = self._build_segment_options_html(segmentation_vars)
        wide_class = ' card--wide' if len(stats) > 12 else ''
        
        styles = dashboard_helpers.get_chart_card_styles()
        _tooltip = chart_defaults.tooltip_js()
        
        return f'''
        <div class="card{wide_class}">
            <div class="card-header am-card-header--controls">
                <div class="am-card-header__info">
                    <h5 class="card-title">{label}</h5>
                    <p class="card-subtitle">Comparativa por curso</p>
                </div>
                <div class="am-card-header__controls">
                    <select id="segment_{chart_id}" class="am-segment-select" title="Segmentar datos">
                        {segment_options_html}
                    </select>
                    <button id="sort_{chart_id}" class="am-icon-btn" title="Descendente">
                        <i class="fa-solid fa-arrow-down-wide-short"></i>
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
                labels: {json.dumps(labels)},
                means: {json.dumps(means)},
                colors: {json.dumps(colors)},
                statsBySegmentation: {json.dumps(stats_by_segmentation)},
                segmentationVars: {json.dumps(segmentation_vars)},
                thresholds: {json.dumps(thresholds)}
            }};
            
            let ascending = true;
            let currentSegmentation = '';
            
            // Paleta de colores para segmentos
            {dashboard_helpers.get_segment_colors_js()}
            
            // Crear datasets de umbrales
            function createThresholdDatasets(labelCount) {{
                const thresholdDatasets = [];
                chartData.thresholds.forEach((threshold, idx) => {{
                    const thresholdData = Array(labelCount).fill(threshold.value);
                    thresholdDatasets.push({{
                        type: 'line',
                        label: threshold.label + ' (' + threshold.operator + ' ' + threshold.value + ')',
                        data: thresholdData,
                        borderColor: '{palette.UI_DANGER}',
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
                            label: '',
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
                    indexAxis: 'y',
                    responsive: true,
                    maintainAspectRatio: true,
                    plugins: {{
                        legend: {{ display: chartData.thresholds.length > 0, position: 'top', labels: {{ filter: (item) => item.text !== '', font: {{ size: 11, family: "{palette.CHART_FONT}" }}, color: '{palette.CHART_TICK_COLOR}' }} }},
                        tooltip: {_tooltip}
                    }},
                    scales: {{
                        x: {{
                            min: {y_min},
                            max: {y_max},
                            title: {{
                                display: true,
                                text: 'Puntuaci\u00f3n',
                                font: {{ size: 11, family: "{palette.CHART_FONT}" }},
                                color: '{palette.CHART_TICK_COLOR}'
                            }},
                            grid: {{ color: '{palette.UI_GRID_LINE}', drawBorder: false }},
                            ticks: {{
                                font: {{ size: 11, family: "{palette.CHART_FONT}" }},
                                color: '{palette.CHART_TICK_COLOR}'
                            }}
                        }},
                        y: {{
                            grid: {{ display: false, drawBorder: false }},
                            ticks: {{
                                font: {{ size: 11, family: "{palette.CHART_FONT}", weight: '500' }},
                                color: '#0f172a'
                            }}
                        }}
                    }}
                }}
            }});
            
            function updateChart() {{
                const entries = chartData.labels.map((label, i) => ({{
                    label: label,
                    value: chartData.means[i],
                    color: chartData.colors[i]
                }}));
                
                // Ordenar
                entries.sort((a, b) => ascending ? a.value - b.value : b.value - a.value);
                
                if (currentSegmentation && chartData.statsBySegmentation[currentSegmentation]) {{
                    // Dividir por segmento seleccionado
                    chart.data.labels = entries.map(e => e.label);
                    chart.data.datasets = [];
                    
                    // Obtener todas las opciones únicas del segmento
                    const allOptions = new Set();
                    entries.forEach(e => {{
                        const stats = chartData.statsBySegmentation[currentSegmentation][e.label] || {{}};
                        Object.keys(stats).forEach(opt => allOptions.add(opt));
                    }});
                    
                    // Crear dataset para cada opción
                    const optionsArray = Array.from(allOptions);
                    optionsArray.forEach((option, idx) => {{
                        const segmentData = entries.map(e => {{
                            const stats = chartData.statsBySegmentation[currentSegmentation][e.label];
                            return stats && stats[option] ? stats[option].mean : null;
                        }});
                        
                        if (segmentData.some(v => v !== null)) {{
                            const color = segmentColors[option] || segmentColors.default[idx % segmentColors.default.length];
                            
                            chart.data.datasets.push({{
                                label: option,
                                data: segmentData,
                                backgroundColor: color,
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
                    // Vista normal sin segmentación
                    chart.data.labels = entries.map(e => e.label);
                    chart.data.datasets = [
                        {{
                            label: '',
                            data: entries.map(e => e.value),
                            backgroundColor: entries.map(e => e.color),
                            borderRadius: 6,
                            borderSkipped: false,
                            order: 1
                        }},
                        ...createThresholdDatasets(entries.length)
                    ];
                    chart.options.plugins.legend.display = chartData.thresholds.length > 0;
                }}
                
                chart.update();
            }}
            
            document.getElementById('segment_{chart_id}').addEventListener('change', function(e) {{
                currentSegmentation = e.target.value;
                updateChart();
            }});
            
            document.getElementById('sort_{chart_id}').addEventListener('click', function() {{
                ascending = !ascending;
                var icon = this.querySelector('i');
                icon.className = ascending ? 'fa-solid fa-arrow-up-short-wide' : 'fa-solid fa-arrow-down-wide-short';
                this.title = ascending ? 'Ascendente' : 'Descendente';
                updateChart();
            }});
        }})();
        </script>
        '''

    def _chart_numeric_distribution(self, df, label, segmentation_vars, y_max=100, y_min=0):
        """Vista Tutor: Distribución anónima del grupo - SOLO evaluación más reciente."""
        if df.empty:
            return ''
        
        # FILTRAR: Solo la evaluación más reciente
        latest_evaluation = df.sort_values('completed_at')['evaluation_name'].iloc[-1]
        df_latest = df[df['evaluation_name'] == latest_evaluation]
        
        values = df_latest['value_numeric'].dropna()
        if len(values) == 0:
            return ''
        
        # Crear bins dinámicos a partir del rango real de la métrica
        n_bins = 4
        step = (y_max - y_min) / n_bins
        bins = [round(y_min + i * step, 1) for i in range(n_bins + 1)]
        bin_labels = [f'{bins[i]:.0f}–{bins[i+1]:.0f}' for i in range(n_bins)]
        bin_colors = palette.BIN_COLORS
        
        # Contar cuántos alumnos en cada rango
        counts = []
        for i in range(len(bins) - 1):
            count = ((values >= bins[i]) & (values < bins[i+1])).sum()
            # Para el último bin, incluir el límite superior
            if i == len(bins) - 2:
                count = ((values >= bins[i]) & (values <= bins[i+1])).sum()
            counts.append(int(count))
        
        # Preparar datos de segmentación (también filtrados a evaluación más reciente)
        distribution_by_segmentation = {}
        MetricValue = self.env['aula_metrics.metric_value']
        
        for seg_var in segmentation_vars:
            var_value = seg_var['value']
            var_type = seg_var['type']
            
            distribution_by_segmentation[var_value] = {}
            
            if var_type == 'partner_field' and var_value == 'gender':
                # Género desde res.partner
                gender_map = {'male': 'Masculino', 'female': 'Femenino', 'other': 'Otro', 'prefer_not_say': 'Prefiere no decir'}
                for gender_key, gender_label in gender_map.items():
                    df_segment = df_latest[df_latest['student_gender'] == gender_key]
                    seg_values = df_segment['value_numeric'].dropna()
                    
                    if len(seg_values) > 0:
                        seg_counts = []
                        for i in range(len(bins) - 1):
                            count = ((seg_values >= bins[i]) & (seg_values < bins[i+1])).sum()
                            if i == len(bins) - 2:
                                count = ((seg_values >= bins[i]) & (seg_values <= bins[i+1])).sum()
                            seg_counts.append(int(count))
                        distribution_by_segmentation[var_value][gender_label] = seg_counts
            
            elif var_type == 'metric_json':
                # Batch query para evitar N+1: una sola búsqueda para todos los alumnos
                all_student_ids = [int(sid) for sid in df_latest['student_id'].unique() if sid != "***"]
                all_seg_records = MetricValue.search([
                    ('student_id', 'in', all_student_ids),
                    ('metric_name', '=', var_value),
                    ('value_json', '!=', False)
                ])
                # student_id (int) → primera opción elegida
                student_segments = {
                    rec.student_id.id: rec.value_json[0]
                    for rec in all_seg_records
                    if rec.value_json
                }
                
                # Calcular distribución por cada opción
                for option in seg_var['options']:
                    df_segment = df_latest[df_latest['student_id'].isin([sid for sid, opt in student_segments.items() if opt == option])]
                    seg_values = df_segment['value_numeric'].dropna()
                    
                    if len(seg_values) > 0:
                        seg_counts = []
                        for i in range(len(bins) - 1):
                            count = ((seg_values >= bins[i]) & (seg_values < bins[i+1])).sum()
                            if i == len(bins) - 2:
                                count = ((seg_values >= bins[i]) & (seg_values <= bins[i+1])).sum()
                            seg_counts.append(int(count))
                        distribution_by_segmentation[var_value][option] = seg_counts
        
        chart_id = f'chart_dist_{dashboard_helpers.sanitize_id(label)}'
        total_alumnos = len(values)
        mean_val = float(values.mean())
        
        segment_options_html = self._build_segment_options_html(segmentation_vars)
        styles = dashboard_helpers.get_chart_card_styles()
        _tooltip = chart_defaults.tooltip_js(
            "label: function(context) {"
            " let percentage = (chartData.totalAlumnos > 0)"
            "   ? ((context.parsed.y / chartData.totalAlumnos) * 100).toFixed(1) : 0;"
            " return context.parsed.y + ' alumnos (' + percentage + '%)'; }"
        )
        
        return f'''
        <div class="card">
            <div class="card-header" style="{styles['chart-card-header']}">
                <div>
                    <h5 class="card-title">{label}</h5>
                    <p class="card-subtitle">Distribución actual del grupo ({latest_evaluation}) · Media: {mean_val:.1f} pts</p>
                </div>
                <select id="segment_{chart_id}" style="{styles['chart-segment-selector']}">
                    {segment_options_html}
                </select>
            </div>
            <div class="card-body">
                <canvas id="{chart_id}" height="260"></canvas>
            </div>
        </div>
        
        <script>
        (function() {{
            const chartData = {{
                labels: {json.dumps(bin_labels)},
                counts: {json.dumps(counts)},
                bin_colors: {json.dumps(bin_colors)},
                distributionBySegmentation: {json.dumps(distribution_by_segmentation)},
                totalAlumnos: {total_alumnos}
            }};
            
            let currentSegmentation = '';
            
            // Paleta de colores para segmentos
            {dashboard_helpers.get_segment_colors_js()}
            
            const chart = new Chart(document.getElementById('{chart_id}'), {{
                type: 'bar',
                data: {{
                    labels: chartData.labels,
                    datasets: [{{
                        label: 'Número de alumnos',
                        data: chartData.counts,
                        backgroundColor: chartData.bin_colors,
                        borderRadius: 6,
                        borderSkipped: false
                    }}]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: true,
                    plugins: {{
                        legend: {{ display: false }},
                        tooltip: {_tooltip}
                    }},
                    scales: {{
                        x: {{
                            grid: {{ display: false, drawBorder: false }},
                            ticks: {{
                                font: {{ size: 11, family: "{palette.CHART_FONT}" }},
                                color: '{palette.CHART_TICK_COLOR}'
                            }}
                        }},
                        y: {{
                            beginAtZero: true,
                            title: {{
                                display: true,
                                text: 'N\u00ba alumnos',
                                font: {{ size: 11, family: "{palette.CHART_FONT}" }},
                                color: '{palette.CHART_TICK_COLOR}'
                            }},
                            grid: {{ color: '{palette.UI_GRID_LINE}', drawBorder: false }},
                            ticks: {{
                                stepSize: 1,
                                font: {{ size: 11, family: "{palette.CHART_FONT}" }},
                                color: '{palette.CHART_TICK_COLOR}'
                            }}
                        }}
                    }}
                }}
            }});
            
            function updateChart() {{
                if (currentSegmentation && chartData.distributionBySegmentation[currentSegmentation]) {{
                    // Mostrar distribución segmentada
                    const segments = chartData.distributionBySegmentation[currentSegmentation];
                    chart.data.datasets = [];
                    
                    const segmentKeys = Object.keys(segments);
                    segmentKeys.forEach((segment, idx) => {{
                        const color = segmentColors[segment] || segmentColors.default[idx % segmentColors.default.length];
                        chart.data.datasets.push({{
                            label: segment,
                            data: segments[segment],
                            backgroundColor: color,
                            borderRadius: 8,
                            borderSkipped: false
                        }});
                    }});
                    
                    chart.options.plugins.legend.display = true;
                    chart.options.plugins.legend.position = 'top';
                }} else {{
                    // Vista normal sin segmentación
                    chart.data.datasets = [{{
                        label: 'Número de alumnos',
                        data: chartData.counts,
                        backgroundColor: chartData.bin_colors,
                        borderRadius: 6,
                        borderSkipped: false
                    }}];
                    chart.options.plugins.legend.display = false;
                }}
                
                chart.update();
            }}
            
            document.getElementById('segment_{chart_id}').addEventListener('change', function(e) {{
                currentSegmentation = e.target.value;
                updateChart();
            }});
        }})();
        </script>
        '''
    
    def _chart_numeric_by_groups(self, df, label, segmentation_vars, y_max=100, y_min=0):
        """Vista Counselor: Comparativa de grupos (barras horizontales compactas)."""
        grupos = sorted(df['group_name'].unique())
        stats = []
        
        for grupo in grupos:
            df_grupo = df[df['group_name'] == grupo]['value_numeric'].dropna()
            if len(df_grupo) > 0:
                mean_val = float(df_grupo.mean())
                n_alumnos = int(len(df_grupo))
                
                stats.append({
                    'grupo': grupo,
                    'mean': mean_val,
                    'n_alumnos': n_alumnos,
                    'color': palette.get_color_for_label(grupo)
                })
        
        if not stats:
            return ''
        
        # Preparar datos de segmentación para TODAS las variables disponibles
        stats_by_segmentation = {}
        MetricValue = self.env['aula_metrics.metric_value']
        
        for seg_var in segmentation_vars:
            var_value = seg_var['value']  # 'gender' o 'question_116_choices'
            var_type = seg_var['type']    # 'partner_field' o 'metric_json'
            
            stats_by_segmentation[var_value] = {}
            
            # Pre-fetch para metric_json: una sola query para todos los alumnos
            seg_map = {}
            if var_type == 'metric_json':
                all_student_ids = [int(sid) for sid in df['student_id'].unique() if sid != "***"]
                all_seg_records = MetricValue.search([
                    ('student_id', 'in', all_student_ids),
                    ('metric_name', '=', var_value),
                    ('value_json', '!=', False)
                ])
                seg_map = {rec.student_id.id: rec.value_json for rec in all_seg_records}
            
            for grupo in grupos:
                df_grupo = df[df['group_name'] == grupo]
                stats_by_segmentation[var_value][grupo] = {}
                
                if var_type == 'partner_field' and var_value == 'gender':
                    # Género desde res.partner
                    gender_map = {'male': 'Masculino', 'female': 'Femenino', 'other': 'Otro', 'prefer_not_say': 'Prefiere no decir'}
                    for gender_key, gender_label in gender_map.items():
                        df_segment = df_grupo[df_grupo['student_gender'] == gender_key]
                        values = df_segment['value_numeric'].dropna()
                        if len(values) > 0:
                            stats_by_segmentation[var_value][grupo][gender_label] = {
                                'mean': float(values.mean()),
                                'count': int(len(values))
                            }
                
                elif var_type == 'metric_json':
                    # Variable de opciones múltiples — datos pre-cargados en seg_map
                    for student_id in df_grupo['student_id'].unique():
                        if student_id == "***":  # Skip anonymized
                            continue
                        
                        selected_options = seg_map.get(int(student_id))
                        if not selected_options:
                            continue
                        
                        student_value = df_grupo[df_grupo['student_id'] == student_id]['value_numeric'].iloc[0]
                        
                        if pd.notna(student_value):
                            for option in selected_options:
                                if option not in stats_by_segmentation[var_value][grupo]:
                                    stats_by_segmentation[var_value][grupo][option] = {
                                        'sum': 0.0,
                                        'count': 0
                                    }
                                stats_by_segmentation[var_value][grupo][option]['sum'] += float(student_value)
                                stats_by_segmentation[var_value][grupo][option]['count'] += 1
                    
                    # Calcular medias
                    for option in stats_by_segmentation[var_value][grupo]:
                        data = stats_by_segmentation[var_value][grupo][option]
                        if data['count'] > 0:
                            data['mean'] = data['sum'] / data['count']
                            del data['sum']  # Limpiar campo temporal
        
        # Ordenar por puntuación inicialmente
        stats_sorted = sorted(stats, key=lambda x: x['mean'])
        
        chart_id = f'chart_grupos_{dashboard_helpers.sanitize_id(label)}'
        labels = [s['grupo'] for s in stats_sorted]
        means = [s['mean'] for s in stats_sorted]
        colors = [s['color'] for s in stats_sorted]
        
        # Obtener umbrales configurados para esta métrica
        metric_name = df.iloc[0]['metric_name'] if not df.empty else None
        thresholds = self._get_thresholds_for_metric(metric_name) if metric_name else []
        
        chart_height = min(350, max(200, len(stats) * 25))
        segment_options_html = self._build_segment_options_html(segmentation_vars)
        styles = dashboard_helpers.get_chart_card_styles()
        wide_class = ' card--wide' if len(stats) > 12 else ''
        _tooltip = chart_defaults.tooltip_js()
        
        return f'''
        <div class="card{wide_class}">
            <div class="card-header am-card-header--controls">
                <div class="am-card-header__info">
                    <h5 class="card-title">{label}</h5>
                    <p class="card-subtitle">Comparativa por grupo</p>
                </div>
                <div class="am-card-header__controls">
                    <select id="segment_{chart_id}" class="am-segment-select" title="Segmentar datos">
                        {segment_options_html}
                    </select>
                    <button id="sort_{chart_id}" class="am-icon-btn" title="Descendente">
                        <i class="fa-solid fa-arrow-down-wide-short"></i>
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
                statsBySegmentation: {json.dumps(stats_by_segmentation)},
                segmentationVars: {json.dumps(segmentation_vars)},
                allGroups: {json.dumps([s['grupo'] for s in stats])},
                allColors: {json.dumps({s['grupo']: s['color'] for s in stats})},
                thresholds: {json.dumps(thresholds)}
            }};
            
            let ascending = true;
            let currentSegmentation = '';
            
            // Paleta de colores para segmentos
            {dashboard_helpers.get_segment_colors_js()}
            
            // Crear datasets de umbrales
            function createThresholdDatasets(labelCount) {{
                const thresholdDatasets = [];
                chartData.thresholds.forEach((threshold, idx) => {{
                    const thresholdData = Array(labelCount).fill(threshold.value);
                    thresholdDatasets.push({{
                        type: 'line',
                        label: threshold.label + ' (' + threshold.operator + ' ' + threshold.value + ')',
                        data: thresholdData,
                        borderColor: '{palette.UI_DANGER}',
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
                            label: '',
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
                        legend: {{ display: chartData.thresholds.length > 0, position: 'top', labels: {{ filter: (item) => item.text !== '', font: {{ size: 11, family: "{palette.CHART_FONT}" }}, color: '{palette.CHART_TICK_COLOR}' }} }},
                        tooltip: {_tooltip}
                    }},
                    scales: {{
                        x: {{
                            min: {y_min},
                            max: {y_max},
                            title: {{
                                display: true,
                                text: 'Puntuaci\u00f3n',
                                font: {{ size: 11, family: "{palette.CHART_FONT}" }},
                                color: '{palette.CHART_TICK_COLOR}'
                            }},
                            grid: {{ color: '{palette.UI_GRID_LINE}', drawBorder: false }},
                            ticks: {{
                                font: {{ size: 11, family: "{palette.CHART_FONT}" }},
                                color: '{palette.CHART_TICK_COLOR}'
                            }}
                        }},
                        y: {{
                            grid: {{ display: false, drawBorder: false }},
                            ticks: {{
                                font: {{ size: 11, family: "{palette.CHART_FONT}", weight: '500' }},
                                color: '#0f172a'
                            }}
                        }}
                    }}
                }}
            }});
            
            function updateChart() {{
                // Calcular medias totales por grupo
                let entries = chartData.allGroups.map(group => {{
                    // Si hay segmentación seleccionada, calcular media ponderada
                    let totalMean = 0;
                    let count = 0;
                    
                    if (currentSegmentation && chartData.statsBySegmentation[currentSegmentation]) {{
                        const stats = chartData.statsBySegmentation[currentSegmentation][group] || {{}};
                        Object.values(stats).forEach(s => {{
                            if (s.mean !== undefined && s.count !== undefined) {{
                                totalMean += s.mean * s.count;
                                count += s.count;
                            }}
                        }});
                    }} else {{
                        // Sin segmentación, usar media total
                        const originalStat = chartData.allGroups.indexOf(group);
                        totalMean = chartData.means[originalStat] || 0;
                        count = 1;
                    }}
                    
                    return {{
                        group: group,
                        mean: count > 0 ? totalMean / count : chartData.allColors[group] ? chartData.means[chartData.groups.indexOf(group)] : 0,
                        color: chartData.allColors[group]
                    }};
                }});
                
                // Ordenar
                entries.sort((a, b) => ascending ? a.mean - b.mean : b.mean - a.mean);
                
                if (currentSegmentation && chartData.statsBySegmentation[currentSegmentation]) {{
                    // Dividir por segmento seleccionado
                    chart.data.labels = entries.map(e => e.group);
                    chart.data.datasets = [];
                    
                    // Obtener todas las opciones únicas del segmento
                    const allOptions = new Set();
                    entries.forEach(e => {{
                        const stats = chartData.statsBySegmentation[currentSegmentation][e.group] || {{}};
                        Object.keys(stats).forEach(opt => allOptions.add(opt));
                    }});
                    
                    // Crear dataset para cada opción
                    const optionsArray = Array.from(allOptions);
                    optionsArray.forEach((option, idx) => {{
                        const segmentData = entries.map(e => {{
                            const stats = chartData.statsBySegmentation[currentSegmentation][e.group];
                            return stats && stats[option] ? stats[option].mean : null;
                        }});
                        
                        if (segmentData.some(v => v !== null)) {{
                            // Elegir color
                            const color = segmentColors[option] || segmentColors.default[idx % segmentColors.default.length];
                            
                            chart.data.datasets.push({{
                                label: option,
                                data: segmentData,
                                backgroundColor: color,
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
                    // Vista normal sin segmentación
                    chart.data.labels = entries.map(e => e.group);
                    chart.data.datasets = [
                        {{
                            label: '',
                            data: entries.map(e => e.mean),
                            backgroundColor: entries.map(e => e.color),
                            borderRadius: 6,
                            borderSkipped: false,
                            order: 1
                        }},
                        ...createThresholdDatasets(entries.length)
                    ];
                    chart.options.plugins.legend.display = chartData.thresholds.length > 0;
                }}
                
                chart.update();
            }}
            
            document.getElementById('segment_{chart_id}').addEventListener('change', function(e) {{
                currentSegmentation = e.target.value;
                updateChart();
            }});
            
            document.getElementById('sort_{chart_id}').addEventListener('click', function() {{
                ascending = !ascending;
                var icon = this.querySelector('i');
                icon.className = ascending ? 'fa-solid fa-arrow-up-short-wide' : 'fa-solid fa-arrow-down-wide-short';
                this.title = ascending ? 'Ascendente' : 'Descendente';
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
        
        chart_id = f'chart_{dashboard_helpers.sanitize_id(label)}'
        
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
                    backgroundColor: '{palette.BIN_COLORS[0]}',
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
                        backgroundColor: '{palette.UI_TOOLTIP_BG}',
                        padding: 12,
                        cornerRadius: 6,
                        titleFont: {{ family: "{palette.CHART_FONT}", size: 13 }},
                        bodyFont: {{ family: "{palette.CHART_FONT}", size: 13 }},
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
                        grid: {{ color: '{palette.UI_GRID_LINE}', drawBorder: false }},
                        ticks: {{
                            font: {{ size: 12, family: "{palette.CHART_FONT}" }},
                            color: '{palette.CHART_TICK_COLOR}',
                            precision: 0
                        }}
                    }},
                    y: {{
                        grid: {{ display: false, drawBorder: false }},
                        ticks: {{
                            font: {{ size: 12, family: "{palette.CHART_FONT}" }},
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

    def _chart_numeric_by_tutor_group(self, df, label, segmentation_vars, y_max=100, y_min=0):
        """Vista Tutor: Comparativa media del grupo vs centro vs nivel educativo.

        Barras base: Mi grupo | Centro | Mi nivel (colores de METRICS_PALETTE).
        Con segmentación: barras de Mi grupo segmentadas (género u otro) + Centro + Mi nivel
        como referencia sin segmentar.

        Usa sudo() en las queries de MetricValue para superar las restricciones de ACL
        del tutor (que solo ve los registros de su propio grupo académico).
        """
        if df.empty:
            return ''

        # ── Solo la evaluación más reciente ──────────────────────────────────
        latest_eval = df.sort_values('completed_at')['evaluation_name'].iloc[-1]
        df_latest   = df[df['evaluation_name'] == latest_eval]
        values      = df_latest['value_numeric'].dropna()
        if len(values) == 0:
            return ''

        group_mean  = round(float(values.mean()), 1)
        metric_name = df['metric_name'].iloc[0]
        course_keys = [c for c in df['curso'].dropna().unique().tolist() if c]

        MetricValue = self.env['aula_metrics.metric_value']

        # ── Media del centro — sudo para superar ACL del tutor ───────────────
        center_mvs  = MetricValue.sudo().search([
            ('metric_name',        '=', metric_name),
            ('evaluation_id.name', '=', latest_eval),
            ('value_float',        '!=', False),
        ])
        center_vals = [mv.value_float for mv in center_mvs if mv.value_float is not False]
        center_mean = round(float(sum(center_vals) / len(center_vals)), 1) if center_vals else None

        # ── Media del nivel educativo — sudo para superar ACL del tutor ──────
        level_mean      = None
        level_label_str = 'Mi nivel'
        if course_keys:
            level_labels_list = [COURSE_LEVEL_MAP.get(k, k) for k in course_keys]
            level_label_str   = ' / '.join(level_labels_list)
            level_mvs  = MetricValue.sudo().search([
                ('metric_name',                    '=',  metric_name),
                ('evaluation_id.name',             '=',  latest_eval),
                ('academic_group_id.course_level', 'in', course_keys),
                ('value_float',                    '!=', False),
            ])
            level_vals = [mv.value_float for mv in level_mvs if mv.value_float is not False]
            level_mean = round(float(sum(level_vals) / len(level_vals)), 1) if level_vals else None

        # ── Colores de paleta oficial ─────────────────────────────────────────
        _COLOR_GROUP  = palette.METRICS_PALETTE[0]   # Academic Navy
        _COLOR_CENTER = palette.METRICS_PALETTE[5]   # Cyan/Teal
        _COLOR_LEVEL  = palette.METRICS_PALETTE[1]   # Chalkboard Green

        # Barras de referencia base (vista sin segmentación)
        ref_bars = [{'label': 'Mi grupo', 'mean': group_mean, 'color': _COLOR_GROUP}]
        if center_mean is not None:
            ref_bars.append({'label': 'Centro', 'mean': center_mean, 'color': _COLOR_CENTER})
        if level_mean is not None:
            ref_bars.append({'label': level_label_str, 'mean': level_mean, 'color': _COLOR_LEVEL})

        # ── Preparar datos de segmentación para MI GRUPO ─────────────────────
        # Centro y Mi nivel siempre aparecen sin segmentar (referencia).
        stats_by_segmentation = {}
        for seg_var in segmentation_vars:
            var_value = seg_var['value']
            var_type  = seg_var['type']
            stats_by_segmentation[var_value] = {}

            if var_type == 'partner_field' and var_value == 'gender':
                gender_map = {
                    'male':           'Masculino',
                    'female':         'Femenino',
                    'other':          'Otro',
                    'prefer_not_say': 'Prefiere no decir',
                }
                for gender_key, gender_label in gender_map.items():
                    df_seg  = df_latest[df_latest['student_gender'] == gender_key]
                    seg_vals = df_seg['value_numeric'].dropna()
                    if len(seg_vals) > 0:
                        stats_by_segmentation[var_value][gender_label] = {
                            'mean':  round(float(seg_vals.mean()), 1),
                            'count': int(len(seg_vals)),
                        }

            elif var_type == 'metric_json':
                all_student_ids = [int(sid) for sid in df_latest['student_id'].unique()
                                   if sid != '***']
                all_seg_records = MetricValue.search([
                    ('student_id',  'in', all_student_ids),
                    ('metric_name', '=',  var_value),
                    ('value_json',  '!=', False),
                ])
                seg_map = {rec.student_id.id: rec.value_json for rec in all_seg_records}
                for student_id in df_latest['student_id'].unique():
                    if student_id == '***':
                        continue
                    selected_options = seg_map.get(int(student_id))
                    if not selected_options:
                        continue
                    sv_series = df_latest[df_latest['student_id'] == student_id]['value_numeric'].dropna()
                    if sv_series.empty:
                        continue
                    sv = float(sv_series.iloc[0])
                    for option in selected_options:
                        if option not in stats_by_segmentation[var_value]:
                            stats_by_segmentation[var_value][option] = {'sum': 0.0, 'count': 0}
                        stats_by_segmentation[var_value][option]['sum']   += sv
                        stats_by_segmentation[var_value][option]['count'] += 1
                for option in stats_by_segmentation[var_value]:
                    data = stats_by_segmentation[var_value][option]
                    if data['count'] > 0:
                        data['mean'] = round(data['sum'] / data['count'], 1)
                        del data['sum']

        chart_id             = f'chart_tutor_{dashboard_helpers.sanitize_id(label)}'
        chart_height         = max(180, len(ref_bars) * 55)
        segment_options_html = self._build_segment_options_html(segmentation_vars)
        _tooltip             = chart_defaults.tooltip_js(chart_defaults.CALLBACKS_SCORE_LABEL_HORIZONTAL)

        return f'''
        <div class="card">
            <div class="card-header am-card-header--controls">
                <div class="am-card-header__info">
                    <h5 class="card-title">{label}</h5>
                    <p class="card-subtitle">Mi grupo vs centro vs mi nivel ({latest_eval})</p>
                </div>
                <div class="am-card-header__controls">
                    <select id="segment_{chart_id}" class="am-segment-select" title="Segmentar datos">
                        {segment_options_html}
                    </select>
                </div>
            </div>
            <div class="card-body">
                <div id="wrap_{chart_id}" style="position:relative;height:{chart_height}px;">
                    <canvas id="{chart_id}"></canvas>
                </div>
            </div>
        </div>

        <script>
        (function() {{
            const chartData = {{
                refBars:             {json.dumps(ref_bars)},
                statsBySegmentation: {json.dumps(stats_by_segmentation)},
            }};
            const BAR_HEIGHT = 52;
            const MIN_HEIGHT = 80;
            let currentSegmentation = '';
            {dashboard_helpers.get_segment_colors_js()}

            const chart = new Chart(document.getElementById('{chart_id}'), {{
                type: 'bar',
                data: {{
                    labels:   chartData.refBars.map(b => b.label),
                    datasets: [{{
                        label:           '',
                        data:            chartData.refBars.map(b => b.mean),
                        backgroundColor: chartData.refBars.map(b => b.color),
                        borderRadius:    6,
                        borderSkipped:   false,
                    }}],
                }},
                options: {{
                    indexAxis:           'y',
                    responsive:          true,
                    maintainAspectRatio: false,
                    plugins: {{
                        legend:  {{ display: false }},
                        tooltip: {_tooltip},
                    }},
                    scales: {{
                        x: {{
                            min: {y_min},
                            max: {y_max},
                            grid:  {{ color: '{palette.UI_GRID_LINE}', drawBorder: false }},
                            ticks: {{ font: {{ size: 11, family: "{palette.CHART_FONT}" }}, color: '{palette.CHART_TICK_COLOR}' }},
                        }},
                        y: {{
                            grid:  {{ display: false, drawBorder: false }},
                            ticks: {{ font: {{ size: 13, family: "{palette.CHART_FONT}" }}, color: '#334155', crossAlign: 'far' }},
                        }},
                    }},
                    animation: {{ duration: 500, easing: 'easeInOutCubic' }},
                }},
            }});

            function updateChart() {{
                const seg = currentSegmentation;
                if (seg && chartData.statsBySegmentation[seg] &&
                    Object.keys(chartData.statsBySegmentation[seg]).length > 0) {{
                    // Con segmentación: solo barras de Mi grupo por segmento.
                    // Centro y Mi nivel se ocultan ya que el contexto cambia.
                    const segments = chartData.statsBySegmentation[seg];
                    const segKeys  = Object.keys(segments);
                    chart.data.labels   = segKeys;
                    chart.data.datasets = [{{
                        label:           '',
                        data:            segKeys.map(k => segments[k].mean),
                        backgroundColor: segKeys.map((k, i) => segmentColors[k] || segmentColors.default[i % segmentColors.default.length]),
                        borderRadius:    6,
                        borderSkipped:   false,
                    }}];
                }} else {{
                    // Sin segmentación: Mi grupo + Centro + Mi nivel
                    chart.data.labels   = chartData.refBars.map(b => b.label);
                    chart.data.datasets = [{{
                        label:           '',
                        data:            chartData.refBars.map(b => b.mean),
                        backgroundColor: chartData.refBars.map(b => b.color),
                        borderRadius:    6,
                        borderSkipped:   false,
                    }}];
                }}
                chart.options.plugins.legend.display = false;
                // Actualizar altura del wrapper según número de barras
                const wrap = document.getElementById('wrap_{chart_id}');
                if (wrap) {{
                    wrap.style.height = Math.max(MIN_HEIGHT, chart.data.labels.length * BAR_HEIGHT) + 'px';
                }}
                chart.update();
            }}

            document.getElementById('segment_{chart_id}').addEventListener('change', function(e) {{
                currentSegmentation = e.target.value;
                updateChart();
            }});
        }})();
        </script>
        '''

