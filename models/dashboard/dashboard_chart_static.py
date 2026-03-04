# -*- coding: utf-8 -*-
"""
Dashboard Chart Static - Gráficos comparativos estáticos de métricas.
"""
import json
from collections import Counter
import pandas as pd
from odoo import models
from ...utils import palette, dashboard_helpers


class DashboardChartsStatic(models.TransientModel):
    _inherit = 'aula_metrics.dashboard.charts'

    def _chart_numeric_by_course(self, df, label, segmentation_vars):
        """Vista Management: Agregado por curso académico (barras compactas)."""
        cursos = sorted(df['curso'].unique())
        stats = []
        
        # Paleta de colores consistente para cursos
        color_palette = palette.METRICS_PALETTE
        
        # Preparar datos generales
        for idx, curso in enumerate(cursos):
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
                    'color': color_palette[idx % len(color_palette)]
                })
        
        if not stats:
            return ''
        
        # Preparar datos de segmentación para TODAS las variables disponibles
        stats_by_segmentation = {}
        MetricValue = self.env['aula_metrics.metric_value']
        
        for seg_var in segmentation_vars:
            var_value = seg_var['value']
            var_type = seg_var['type']
            var_options = seg_var['options']
            
            stats_by_segmentation[var_value] = {}
            
            for curso in cursos:
                df_curso = df[df['curso'] == curso]
                stats_by_segmentation[var_value][curso] = {}
                
                if var_type == 'partner_field' and var_value == 'gender':
                    # Género desde res.partner
                    gender_map = {'male': 'Masculino', 'female': 'Femenino', 'other': 'Otro', 'prefer_not_say': 'Prefiere no decir'}
                    for gender_key, gender_label in gender_map.items():
                        df_segment = df_curso[df_curso['student_gender'] == gender_key]
                        values = df_segment['value_numeric'].dropna()
                        if len(values) > 0:
                            stats_by_segmentation[var_value][curso][gender_label] = {
                                'mean': float(values.mean()),
                                'count': int(len(values))
                            }
                
                elif var_type == 'metric_json':
                    # Variable de opciones múltiples desde metric_value
                    for student_id in df_curso['student_id'].unique():
                        if student_id == "***":  # Skip anonymized
                            continue
                        
                        # Buscar el valor de la variable de segmentación para este estudiante
                        seg_records = MetricValue.search([
                            ('student_id', '=', int(student_id)),
                            ('metric_name', '=', var_value),
                            ('value_json', '!=', False)
                        ], limit=1)
                        
                        if seg_records and seg_records.value_json:
                            selected_options = seg_records.value_json
                            student_value = df_curso[df_curso['student_id'] == student_id]['value_numeric'].iloc[0]
                            
                            if pd.notna(student_value):
                                for option in selected_options:
                                    if option not in stats_by_segmentation[var_value][curso]:
                                        stats_by_segmentation[var_value][curso][option] = {
                                            'sum': 0.0,
                                            'count': 0
                                        }
                                    stats_by_segmentation[var_value][curso][option]['sum'] += float(student_value)
                                    stats_by_segmentation[var_value][curso][option]['count'] += 1
                    
                    # Calcular medias
                    for option in stats_by_segmentation[var_value][curso]:
                        data = stats_by_segmentation[var_value][curso][option]
                        if data['count'] > 0:
                            data['mean'] = data['sum'] / data['count']
                            del data['sum']
        
        chart_id = f'chart_cursos_{dashboard_helpers.sanitize_id(label)}'
        labels = [s['curso'] for s in stats]
        means = [s['mean'] for s in stats]
        colors = [s['color'] for s in stats]
        
        # Obtener umbrales configurados para esta métrica
        metric_name = df.iloc[0]['metric_name'] if not df.empty else None
        thresholds = self._get_thresholds_for_metric(metric_name) if metric_name else []
        
        chart_height = min(350, max(200, len(stats) * 25))
        segment_options_html = self._build_segment_options_html(segmentation_vars)
        
        styles = dashboard_helpers.get_chart_card_styles()
        
        return f'''
        <div class="card">
            <div class="card-header" style="{styles['chart-card-header']}">
                <div>
                    <h5 class="card-title">{label}</h5>
                    <p class="card-subtitle">Comparativa por curso</p>
                </div>
                <div style="display: flex; gap: 8px; align-items: center;">
                    <select id="segment_{chart_id}" style="{styles['chart-segment-selector']}">
                        {segment_options_html}
                    </select>
                    <button id="sort_{chart_id}" style="padding: 6px 12px; background: var(--am-bg); border: 1px solid var(--am-border); border-radius: 6px; cursor: pointer; font-size: 12px; color: var(--am-muted); font-weight: 500; transition: all 0.2s;" onmouseover="this.style.background=getComputedStyle(document.documentElement).getPropertyValue('--am-primary-100')" onmouseout="this.style.background=getComputedStyle(document.documentElement).getPropertyValue('--am-bg')">
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
            
            document.getElementById('segment_{chart_id}').addEventListener('change', function(e) {{
                currentSegmentation = e.target.value;
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

    def _chart_numeric_distribution(self, df, label, segmentation_vars):
        """Vista Tutor: Distribución anónima del grupo - SOLO evaluación más reciente."""
        if df.empty:
            return ''
        
        # FILTRAR: Solo la evaluación más reciente
        latest_evaluation = df.sort_values('completed_at')['evaluation_name'].iloc[-1]
        df_latest = df[df['evaluation_name'] == latest_evaluation]
        
        values = df_latest['value_numeric'].dropna()
        if len(values) == 0:
            return ''
        
        # Crear bins (rangos) para el histograma
        bins = [0, 40, 60, 80, 100]
        bin_labels = ['0-40 (Bajo)', '40-60 (Medio-Bajo)', '60-80 (Medio-Alto)', '80-100 (Alto)']
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
                # Variable de opciones múltiples desde metric_value
                student_segments = {}
                
                for student_id in df_latest['student_id'].unique():
                    if student_id == "***":  # Skip anonymized
                        continue
                    
                    seg_records = MetricValue.search([
                        ('student_id', '=', int(student_id)),
                        ('metric_name', '=', var_value),
                        ('value_json', '!=', False)
                    ], limit=1)
                    
                    if seg_records and seg_records.value_json:
                        for option in seg_records.value_json:
                            student_segments[student_id] = option
                            break  # Tomar solo la primera opción si hay múltiples
                
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
                        tooltip: {{
                            backgroundColor: '#1e293b',
                            padding: 12,
                            cornerRadius: 6,
                            titleFont: {{ family: "'Inter', sans-serif", size: 13, weight: '600' }},
                            bodyFont: {{ family: "'Inter', sans-serif", size: 12 }},
                            callbacks: {{
                                label: function(context) {{
                                    let percentage = (chartData.totalAlumnos > 0) ? ((context.parsed.y / chartData.totalAlumnos) * 100).toFixed(1) : 0;
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
                                font: {{ size: 11, family: "'Inter', sans-serif" }},
                                color: '#94a3b8'
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
    
    def _chart_numeric_by_groups(self, df, label, segmentation_vars):
        """Vista Counselor: Comparativa de grupos (barras horizontales compactas)."""
        grupos = sorted(df['group_name'].unique())
        stats = []
        
        # Paleta de colores para grupos
        color_palette = palette.METRICS_PALETTE
        
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
        
        # Preparar datos de segmentación para TODAS las variables disponibles
        stats_by_segmentation = {}
        MetricValue = self.env['aula_metrics.metric_value']
        
        for seg_var in segmentation_vars:
            var_value = seg_var['value']  # 'gender' o 'question_116_choices'
            var_type = seg_var['type']    # 'partner_field' o 'metric_json'
            var_options = seg_var['options']
            
            stats_by_segmentation[var_value] = {}
            
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
                    # Variable de opciones múltiples desde metric_value
                    # Necesitamos cruzar con metric_value para obtener las opciones elegidas
                    for student_id in df_grupo['student_id'].unique():
                        if student_id == "***":  # Skip anonymized
                            continue
                        
                        # Buscar el valor de la variable de segmentación para este estudiante
                        seg_records = MetricValue.search([
                            ('student_id', '=', int(student_id)),
                            ('metric_name', '=', var_value),
                            ('value_json', '!=', False)
                        ], limit=1)
                        
                        if seg_records and seg_records.value_json:
                            # value_json es una lista como ['Bajo'] o ['Urbano']
                            selected_options = seg_records.value_json
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
        
        return f'''
        <div class="card">
            <div class="card-header" style="{styles['chart-card-header']}">
                <div>
                    <h5 class="card-title">{label}</h5>
                    <p class="card-subtitle">Comparativa por grupo</p>
                </div>
                <div style="display: flex; gap: 8px; align-items: center;">
                    <select id="segment_{chart_id}" style="{styles['chart-segment-selector']}">
                        {segment_options_html}
                    </select>
                    <button id="sort_{chart_id}" style="padding: 6px 12px; background: var(--am-bg); border: 1px solid var(--am-border); border-radius: 6px; cursor: pointer; font-size: 12px; color: var(--am-muted); font-weight: 500; transition: all 0.2s;" onmouseover="this.style.background=getComputedStyle(document.documentElement).getPropertyValue('--am-primary-100')" onmouseout="this.style.background=getComputedStyle(document.documentElement).getPropertyValue('--am-bg')">
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
            
            document.getElementById('segment_{chart_id}').addEventListener('change', function(e) {{
                currentSegmentation = e.target.value;
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

