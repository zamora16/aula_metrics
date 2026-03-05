# -*- coding: utf-8 -*-
"""
Gráficos del perfil de alumno: evolución longitudinal de métricas del centro
y resumen comparativo (barras horizontales con marcadores de grupo/centro).
"""
from odoo import models, api
import json
from ...utils import palette


class DashboardStudentCharts(models.TransientModel):
    _inherit = 'aula_metrics.dashboard.student_profile'

    def _generate_evolution_chartjs(self, df, student):
        """Gráficos de barras + línea de media de grupo por métrica numérica."""
        if df.empty:
            return ''

        df_numeric = df[df['metric_type'] == 'numeric'].copy()
        if df_numeric.empty:
            return ''

        group_data  = self._get_group_context_data(student, df_numeric)
        charts_html = ''

        for idx, metric in enumerate(df_numeric['metric_label'].unique()[:4]):
            df_metric   = df_numeric[df_numeric['metric_label'] == metric].sort_values('timestamp')
            metric_name = df_metric.iloc[0]['metric_name']

            if len(df_metric) < 2:
                continue

            labels      = [row['timestamp'].strftime('%d/%m') for _, row in df_metric.iterrows()]
            values      = [float(row['value'])               for _, row in df_metric.iterrows()]
            first_value = values[0]
            last_value  = values[-1]
            pct_change  = ((last_value - first_value) / first_value * 100) if first_value != 0 else 0
            change_icon  = '↑' if pct_change > 0 else ('↓' if pct_change < 0 else '→')
            change_color = (palette.UI_SUCCESS if pct_change > 0
                            else (palette.UI_DANGER if pct_change < 0 else palette.UI_MUTED))
            change_text  = f"<span style='color:{change_color};font-weight:600;'>{change_icon} {abs(pct_change):.1f}%</span>"

            # Media de grupo alineada a los timestamps del alumno (±7 días)
            group_means = []
            if metric_name in group_data:
                group_vals = group_data[metric_name].get('values', [])
                for timestamp in df_metric['timestamp']:
                    matching = [v for t, v in group_vals if abs((t - timestamp).days) <= 7]
                    group_means.append(sum(matching) / len(matching) if matching else None)

            chart_id = f'evolution_{student.id}_{idx}'

            all_vals        = values + [v for v in group_means if v is not None]
            y_suggested_max = round(max(all_vals) * 1.20, 1) if all_vals else 100

            datasets = [{
                'label':            student.name,
                'data':             values,
                'backgroundColor':  palette.UI_PRIMARY,
                'borderColor':      palette.UI_PRIMARY,
                'borderRadius':     6,
                'borderSkipped':    False,
                'order':            2,
            }]
            if group_means and any(v is not None for v in group_means):
                datasets.append({
                    'label':              'Media grupo',
                    'data':               group_means,
                    'type':               'line',
                    'borderColor':        palette.UI_MUTED,
                    'backgroundColor':    'transparent',
                    'borderWidth':        2,
                    'borderDash':         [5, 5],
                    'pointRadius':        4,
                    'pointBackgroundColor': palette.UI_MUTED,
                    'pointBorderColor':   '#ffffff',
                    'pointBorderWidth':   2,
                    'order':              1,
                    'tension':            0.3,
                })

            charts_html += f'''
            <div class="col-lg-6 mb-4">
                <div class="card">
                    <div class="card-header">
                        <h6 class="card-title-sm">{metric}</h6>
                        <p style="font-size:11px;color:var(--am-muted);margin:4px 0 0 0;">
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
                data: {{ labels: {json.dumps(labels)}, datasets: {json.dumps(datasets)} }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: true,
                    plugins: {{
                        legend: {{
                            display: true, position: 'bottom',
                            labels: {{ usePointStyle: true, padding: 12, font: {{ size: 11 }} }}
                        }},
                        tooltip: {{
                            padding: 12, cornerRadius: 6,
                            callbacks: {{
                                label: function(ctx) {{
                                    let lbl = ctx.dataset.label ? ctx.dataset.label + ': ' : '';
                                    if (ctx.parsed.y !== null) lbl += ctx.parsed.y.toFixed(1) + ' pts';
                                    return lbl;
                                }}
                            }}
                        }}
                    }},
                    scales: {{
                        x: {{ grid: {{ display: false }}, ticks: {{ font: {{ size: 11 }} }} }},
                        y: {{
                            beginAtZero: true,
                            suggestedMax: {y_suggested_max},
                            grid: {{ drawBorder: false }},
                            ticks: {{ font: {{ size: 11 }} }}
                        }}
                    }},
                    animation: {{ duration: 600, easing: 'easeInOutCubic' }}
                }}
            }});
            </script>'''

        return f'<div class="row">{charts_html}</div>' if charts_html else ''

    def _get_group_context_data(self, student, df_student):
        """Obtiene datos del grupo para contextualizar el perfil individual."""
        if not student.academic_group_id:
            return {}

        group_id   = student.academic_group_id.id
        group_data = {}
        MetricValue = self.env['aula_metrics.metric_value']

        for metric_name in df_student['metric_name'].unique():
            group_metrics = MetricValue.search([
                ('metric_name',        '=', metric_name),
                ('academic_group_id',  '=', group_id),
            ])
            if group_metrics:
                values_with_ts = [
                    (m.timestamp, m.value_float)
                    for m in group_metrics if m.value_float is not None
                ]
                if values_with_ts:
                    group_data[metric_name] = {
                        'values': values_with_ts,
                        'mean':   sum(v for _, v in values_with_ts) / len(values_with_ts),
                    }
        return group_data

    def _get_center_context_data(self, student, df_student):
        """Obtiene medias del centro completo por métrica."""
        center_data = {}
        MetricValue = self.env['aula_metrics.metric_value']

        for metric_name in df_student['metric_name'].unique():
            center_metrics = MetricValue.search([('metric_name', '=', metric_name)])
            if center_metrics:
                values = [m.value_float for m in center_metrics if m.value_float is not None]
                if values:
                    center_data[metric_name] = {'mean': sum(values) / len(values)}
        return center_data

    def _generate_radar_chart(self, df, student):
        """
        Resumen de Métricas: barra horizontal por métrica numérica con marcadores
        de media de grupo (gris) y centro (verde).
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
        for metric_name in df_numeric['metric_name'].unique():
            df_m = df_numeric[df_numeric['metric_name'] == metric_name].sort_values('timestamp')
            if df_m.empty:
                continue

            label     = df_m.iloc[-1]['metric_label']
            last_val  = float(df_m.iloc[-1]['value'])
            last_date = df_m.iloc[-1]['timestamp'].strftime('%d/%m/%Y')

            # Tendencia
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

            # Rango de normalización
            all_vals = MetricValue.search_read(
                [('metric_name', '=', metric_name), ('value_float', '!=', False)],
                ['value_float'],
            )
            all_floats   = [r['value_float'] for r in all_vals if r['value_float'] is not None]
            observed_max = max(all_floats) if all_floats else max(last_val, 1)
            if observed_max <= 0:
                observed_max = 1

            def to_pct(v, mx=observed_max):
                return min(int(v / mx * 100), 100)

            student_pct = to_pct(last_val)
            bar_color   = palette.UI_PRIMARY

            # Marcadores grupo / centro
            group_marker_html  = ''
            center_marker_html = ''
            if metric_name in group_data:
                gm = group_data[metric_name]['mean']
                gp = to_pct(gm)
                group_marker_html = (
                    f'<div title="Media grupo: {gm:.1f}" '
                    f'style="position:absolute;left:{gp}%;top:50%;transform:translate(-50%,-50%);'
                    f'width:3px;height:20px;background:#94a3b8;border-radius:2px;z-index:2;"></div>'
                )
            if metric_name in center_data:
                cm = center_data[metric_name]['mean']
                cp = to_pct(cm)
                center_marker_html = (
                    f'<div title="Media centro: {cm:.1f}" '
                    f'style="position:absolute;left:{cp}%;top:50%;transform:translate(-50%,-50%);'
                    f'width:3px;height:20px;background:{palette.UI_SUCCESS};border-radius:2px;z-index:2;"></div>'
                )

            rows_html.append(f"""
            <div class="d-flex align-items-center gap-3 py-2"
                 style="border-bottom:1px solid var(--am-border);">
                <div style="width:180px;min-width:140px;flex-shrink:0;">
                    <div style="font-size:13px;font-weight:500;color:var(--am-text);
                                white-space:nowrap;overflow:hidden;text-overflow:ellipsis;"
                         title="{label}">{label}</div>
                    <div style="font-size:11px;color:var(--am-muted);">{last_date} {trend_icon}</div>
                </div>
                <div style="flex:1;position:relative;height:28px;display:flex;align-items:center;">
                    <div style="position:absolute;left:0;right:0;top:50%;transform:translateY(-50%);
                                height:8px;background:var(--am-border);border-radius:4px;overflow:visible;">
                        <div style="width:{student_pct}%;height:100%;background:{bar_color};
                                    border-radius:4px;transition:width 0.5s ease;"></div>
                    </div>
                    {group_marker_html}
                    {center_marker_html}
                </div>
                <div style="width:64px;flex-shrink:0;text-align:right;">
                    <span style="font-size:18px;font-weight:700;color:{bar_color};line-height:1;">{last_val:.0f}</span>
                    <div style="font-size:10px;color:var(--am-muted);">/ {observed_max:.0f}</div>
                </div>
            </div>""")

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
                        <div class="d-flex gap-4 pt-3" style="font-size:11px;color:var(--am-muted);">
                            <span><span style="display:inline-block;width:18px;height:7px;background:var(--am-primary);border-radius:3px;vertical-align:middle;"></span> Alumno</span>
                            <span><span style="display:inline-block;width:3px;height:14px;background:#94a3b8;border-radius:1px;vertical-align:middle;"></span> Media grupo</span>
                            <span><span style="display:inline-block;width:3px;height:14px;background:{palette.UI_SUCCESS};border-radius:1px;vertical-align:middle;"></span> Media centro</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>"""
