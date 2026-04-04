# -*- coding: utf-8 -*-
"""
Gráficos del perfil de alumno: evolución longitudinal de métricas del centro
y resumen comparativo (barras horizontales con marcadores de grupo/centro).

Métodos de datos puros + delegación de presentación a QWeb.
"""
from odoo import models
import json
from markupsafe import Markup
from ...utils import palette


def _qweb(env, template_id, values):
    result = env['ir.qweb']._render(template_id, values)
    if isinstance(result, bytes):
        return Markup(result.decode('utf-8'))
    return Markup(result)


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
        chart_items = []

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
            change_html  = Markup(
                f"<span style='color:{change_color};font-weight:600;'>"
                f"{change_icon} {abs(pct_change):.1f}%</span>"
            )

            # Media de grupo alineada a los timestamps del alumno (±7 días)
            group_means = []
            if metric_name in group_data:
                group_vals = group_data[metric_name].get('values', [])
                for timestamp in df_metric['timestamp']:
                    matching = [v for t, v in group_vals if abs((t - timestamp).days) <= 7]
                    group_means.append(sum(matching) / len(matching) if matching else None)

            canvas_id = f'evolution_{student.id}_{idx}'

            all_vals        = values + [v for v in group_means if v is not None]
            y_suggested_max = round(max(all_vals) * 1.20, 1) if all_vals else 100

            datasets = [{
                'label':           student.name,
                'data':            values,
                'backgroundColor': palette.UI_PRIMARY,
                'borderColor':     palette.UI_PRIMARY,
                'borderRadius':    6,
                'borderSkipped':   False,
                'order':           2,
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

            config = {
                'type': 'bar',
                'data': {'labels': labels, 'datasets': datasets},
                'options': {
                    'responsive':          True,
                    'maintainAspectRatio': True,
                    'plugins': {
                        'legend': {
                            'display': True, 'position': 'bottom',
                            'labels': {'usePointStyle': True, 'padding': 12, 'font': {'size': 11}},
                        },
                        'tooltip': {
                            'padding': 12, 'cornerRadius': 6,
                        },
                    },
                    'scales': {
                        'x': {'grid': {'display': False}, 'ticks': {'font': {'size': 11}}},
                        'y': {
                            'beginAtZero':  True,
                            'suggestedMax': y_suggested_max,
                            'grid':  {'drawBorder': False},
                            'ticks': {'font': {'size': 11}},
                        },
                    },
                    'animation': {'duration': 600, 'easing': 'easeInOutCubic'},
                },
            }

            # Pre-build the <script> as Markup — avoids XML escaping issues in the template
            init_script = Markup(
                f'<script>new Chart(document.getElementById("{canvas_id}"), '
                f'{json.dumps(config)});</script>'
            )

            chart_items.append({
                'canvas_id':    canvas_id,
                'metric_label': metric,
                'change_html':  change_html,
                'init_script':  init_script,
            })

        return _qweb(self.env, 'aula_metrics.student_evolution_charts_section', {
            'chart_items': chart_items,
        })

    def _get_group_context_data(self, student, df_student):
        """Obtiene datos del grupo para contextualizar el perfil individual."""
        if not student.academic_group_id:
            return {}

        group_id    = student.academic_group_id.id
        group_data  = {}
        MetricValue = self.env['aula_metrics.metric_value']

        for metric_name in df_student['metric_name'].unique():
            group_metrics = MetricValue.search([
                ('metric_name',       '=', metric_name),
                ('academic_group_id', '=', group_id),
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
        Resumen de Métricas: barra horizontal por métrica con marcadores
        de media de grupo/centro — renderizado via QWeb.
        """
        if df.empty:
            return ''

        df_numeric = df[df['metric_type'] == 'numeric'].copy()
        if df_numeric.empty:
            return ''

        group_data  = self._get_group_context_data(student, df_numeric)
        center_data = self._get_center_context_data(student, df_numeric)
        MetricValue = self.env['aula_metrics.metric_value']

        metric_rows = []
        for metric_name in df_numeric['metric_name'].unique():
            df_m = df_numeric[df_numeric['metric_name'] == metric_name].sort_values('timestamp')
            if df_m.empty:
                continue

            label     = df_m.iloc[-1]['metric_label']
            last_val  = float(df_m.iloc[-1]['value'])
            last_date = df_m.iloc[-1]['timestamp'].strftime('%d/%m/%Y')

            # Trend icon
            trend_icon = ''
            if len(df_m) >= 2:
                prev_val = float(df_m.iloc[-2]['value'])
                diff     = last_val - prev_val
                if abs(diff) < 0.5:
                    trend_icon = Markup('<i class="fa-solid fa-minus" style="color:var(--am-muted);font-size:10px;"></i>')
                elif diff > 0:
                    trend_icon = Markup('<i class="fa-solid fa-arrow-up" style="color:var(--am-primary);font-size:10px;"></i>')
                else:
                    trend_icon = Markup('<i class="fa-solid fa-arrow-down" style="color:var(--am-danger,#ef4444);font-size:10px;"></i>')

            # Normalisation range
            all_vals_raw = MetricValue.search_read(
                [('metric_name', '=', metric_name), ('value_float', '!=', None)],
                ['value_float'],
            )
            all_floats   = [r['value_float'] for r in all_vals_raw if r['value_float'] is not None]
            observed_max = max(all_floats) if all_floats else max(last_val, 1)
            if observed_max <= 0:
                observed_max = 1

            def to_pct(v, mx=observed_max):
                return min(int(v / mx * 100), 100)

            row = {
                'label':        label,
                'last_date':    last_date,
                'trend_icon':   trend_icon,
                'student_pct':  to_pct(last_val),
                'last_val_str': f'{last_val:.0f}',
                'max_val_str':  f'{observed_max:.0f}',
            }

            if metric_name in group_data:
                gm = group_data[metric_name]['mean']
                gp = to_pct(gm)
                row['group_mean']         = f'{gm:.1f}'
                row['group_marker_style'] = (
                    f'position:absolute;left:{gp}%;top:50%;transform:translate(-50%,-50%);'
                    f'width:3px;height:20px;background:#94a3b8;border-radius:2px;z-index:2;'
                )

            if metric_name in center_data:
                cm = center_data[metric_name]['mean']
                cp = to_pct(cm)
                row['center_mean']         = f'{cm:.1f}'
                row['center_marker_style'] = (
                    f'position:absolute;left:{cp}%;top:50%;transform:translate(-50%,-50%);'
                    f'width:3px;height:20px;background:{palette.UI_SUCCESS};border-radius:2px;z-index:2;'
                )

            metric_rows.append(row)

        if not metric_rows:
            return ''

        return _qweb(self.env, 'aula_metrics.student_metrics_summary_section', {
            'metric_rows': metric_rows,
            'ui_primary':  palette.UI_PRIMARY,
            'ui_success':  palette.UI_SUCCESS,
        })
