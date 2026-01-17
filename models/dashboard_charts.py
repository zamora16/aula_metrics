# -*- coding: utf-8 -*-
"""
Dashboard Charts - Generación de gráficos interactivos con Plotly
Versión Ejecutiva/Orientación - Enero 2026
"""
from odoo import models, fields, api

# =============================================================================
# CONFIGURACIÓN DE MÉTRICAS
# =============================================================================
SURVEY_METRICS = {
    'WHO5': {
        'fields': ['who5_score'],
        'labels': {'who5_score': 'Bienestar (WHO-5)'},
        'colors': {'who5_score': '#28a745'},
        'default_threshold': 50, 'default_op': '<'
    },
    'BULLYING_VA': {
        'fields': ['bullying_score', 'victimization_score', 'aggression_score'],
        'labels': {
            'bullying_score': 'Bullying Global',
            'victimization_score': 'Victimización',
            'aggression_score': 'Agresión',
        },
        'colors': {
            'bullying_score': '#dc3545',
            'victimization_score': '#e83e8c', 
            'aggression_score': '#6f42c1',
        },
        'default_threshold': 40, 'default_op': '>'
    },
    'ASQ14': {
        'fields': ['stress_score'],
        'labels': {'stress_score': 'Estrés (ASQ-14)'},
        'colors': {'stress_score': '#fd7e14'},
        'default_threshold': 60, 'default_op': '>'
    },
}

class DashboardCharts(models.TransientModel):
    _name = 'aulametrics.dashboard.charts'
    _description = 'Generador de Dashboard Ejecutivo'

    evaluation_id = fields.Many2one('aulametrics.evaluation', string='Evaluación')

    @staticmethod
    def _import_plotly():
        try:
            import plotly.graph_objects as go
            from plotly.subplots import make_subplots
            return go, make_subplots
        except ImportError:
            return None, None

    def _get_metrics(self, evaluation):
        """Obtiene configuración de métricas y sus umbrales activos."""
        metrics = {'fields': [], 'labels': {}, 'colors': {}, 'thresholds': {}}
        
        for survey in evaluation.survey_ids:
            if survey.survey_code in SURVEY_METRICS:
                cfg = SURVEY_METRICS[survey.survey_code]
                metrics['fields'].extend(cfg['fields'])
                metrics['labels'].update(cfg['labels'])
                metrics['colors'].update(cfg['colors'])
        
        Threshold = self.env['aulametrics.threshold']
        for field in metrics['fields']:
            thresh = Threshold.search([
                ('score_field', '=', field),
                ('active', '=', True)
            ], limit=1, order='severity desc')
            
            if thresh:
                metrics['thresholds'][field] = {
                    'val': thresh.threshold_value,
                    'op': thresh.operator,
                    'name': thresh.name
                }
            else:
                metrics['thresholds'][field] = None

        return metrics

    def _check_risk(self, value, threshold_cfg):
        if not threshold_cfg: return False
        if threshold_cfg['op'] == '>': return value > threshold_cfg['val']
        else: return value < threshold_cfg['val']

    @api.model
    def generate_dashboard(self, evaluation_id):
        go, make_subplots = self._import_plotly()
        if not go: return self._error_html("Plotly no instalado.")

        evaluation = self.env['aulametrics.evaluation'].browse(evaluation_id)
        if not evaluation.exists(): return self._error_html("Evaluación no encontrada")

        metrics = self._get_metrics(evaluation)
        participations = evaluation.participation_ids.filtered(lambda p: p.state == 'completed')
        
        if not participations: return self._error_html("Esperando datos... No hay participaciones completas aún.")

        # --- PRECESAMIENTO DE DATOS ---
        df = self._prepare_dataframe(participations, metrics)

        # --- GENERACIÓN DE VISTAS (Orden Coherente) ---
        # 1. Visión Global (Centro)
        kpi_html = self._generate_kpis_html(df, metrics, evaluation)
        
        # 2. Visión Estratégica (Centro -> Niveles)
        fig_heatmap = self._chart_heatmap(go, df, metrics)
        
        # 3. Análisis Demográfico (Comparación Edad y Género)
        fig_trend = self._chart_course_comparison(go, df, metrics)
        fig_gender = self._chart_gender_box(go, df, metrics)
        
        # 4. Análisis Detallado (Grupos)
        fig_ranking = self._chart_groups_ranking(go, df, metrics)

        return self._build_final_html(evaluation, kpi_html, fig_heatmap, fig_trend, fig_gender, fig_ranking)

    def _prepare_dataframe(self, participations, metrics):
        data = []
        for p in participations:
            item = {
                'id': p.student_id.id,
                'name': p.student_id.name,
                'group': p.academic_group_id.name or 'Sin grupo',
                'course': p.academic_group_id.course_level or 'N/A',
                'gender': p.student_gender or 'other',
                'tutor': p.academic_group_id.tutor_id.name or 'N/A'
            }
            for f in metrics['fields']:
                item[f] = getattr(p, f) or 0
            data.append(item)
        return data

    def _generate_kpis_html(self, data, metrics, evaluation):
        part_rate = evaluation.participation_rate
        p_color = '#28a745' if part_rate > 80 else '#ffc107' if part_rate > 50 else '#dc3545'

        return f"""
        <div class="kpi-container">
            <div class="kpi-card" style="border-left: 5px solid {p_color}">
                <div class="kpi-title">Participación</div>
                <div class="kpi-value">{part_rate:.1f}%</div>
                <div class="kpi-sub">{evaluation.completed_students}/{evaluation.total_students} alumnos</div>
            </div>
        </div>
        """

    def _chart_heatmap(self, go, data, metrics):
        courses = sorted(list(set(d['course'] for d in data)))
        fields_list = metrics['fields']
        z_values, text_values = [], []
        
        course_map = {
            'eso1': '1º ESO', 'eso2': '2º ESO', 'eso3': '3º ESO', 'eso4': '4º ESO',
            'bach1': '1º Bach', 'bach2': '2º Bach'
        }
        y_labels = [course_map.get(c, c) for c in courses]
        x_labels = [metrics['labels'][f] for f in fields_list]

        for course in courses:
            c_data = [d for d in data if d['course'] == course]
            row_z, row_text = [], []
            for f in fields_list:
                val = sum(d[f] for d in c_data) / len(c_data) if c_data else 0
                row_z.append(val)
                thresh = metrics['thresholds'].get(f)
                risk_marker = " ⚠️" if thresh and self._check_risk(val, thresh) else ""
                row_text.append(f"{val:.1f}{risk_marker}")
            z_values.append(row_z)
            text_values.append(row_text)

        fig = go.Figure(data=go.Heatmap(
            z=z_values, x=x_labels, y=y_labels,
            text=text_values, texttemplate="%{text}",
            colorscale='RdYlGn', zmin=0, zmax=100, hoverongaps=False
        ))
        
        fig.update_layout(
            title='Mapa Estratégico (Promedios por Curso)',
            height=300 + (len(courses) * 30),
            margin=dict(l=50, r=50, t=50, b=50), xaxis=dict(side='top'),
            template='plotly_white'
        )
        return fig

    def _chart_course_comparison(self, go, data, metrics):
        courses = sorted(list(set(d['course'] for d in data)))
        course_map = {
            'eso1': '1º ESO', 'eso2': '2º ESO', 'eso3': '3º ESO', 'eso4': '4º ESO',
            'bach1': '1º Bach', 'bach2': '2º Bach'
        }
        x_labels = [course_map.get(c, c) for c in courses]
        fig = go.Figure()
        
        for f in metrics['fields']:
            y_vals = []
            for c in courses:
                c_data = [d for d in data if d['course'] == c]
                avg = sum(d[f] for d in c_data) / len(c_data) if c_data else 0
                y_vals.append(avg)
            
            fig.add_trace(go.Bar(
                name=metrics['labels'][f], x=x_labels, y=y_vals,
                text=[f'{v:.1f}' for v in y_vals], textposition='auto',
                marker_color=metrics['colors'][f]
            ))

        fig.update_layout(
            title='Evolución por Nivel Educativo', barmode='group',
            yaxis=dict(range=[0, 100]), template='plotly_white',
            legend=dict(orientation="h", y=-0.15)
        )
        return fig

    def _chart_gender_box(self, go, data, metrics):
        fig = go.Figure()
        gender_map = {'male': 'Chicos', 'female': 'Chicas', 'other': 'Otro'}
        sorted_genders = sorted(list(set(d['gender'] for d in data)))
        
        for f in metrics['fields']:
            for g in sorted_genders:
                g_vals = [d[f] for d in data if d['gender'] == g]
                fig.add_trace(go.Box(
                    y=g_vals,
                    name=metrics['labels'][f],
                    x=[gender_map.get(g, g)] * len(g_vals),
                    marker_color=metrics['colors'][f],
                    showlegend=(g==sorted_genders[0])
                ))

        fig.update_layout(
            title='Distribución por Género (Box Plots)', boxmode='group',
            yaxis=dict(range=[0, 100]), template='plotly_white'
        )
        return fig

    def _chart_groups_ranking(self, go, data, metrics):
        """Ranking de grupos (Barras horizontales)."""
        groups = sorted(list(set(d['group'] for d in data)))
        fig = go.Figure()
        
        for f in metrics['fields']:
            vals = []
            for g in groups:
                 g_data = [d for d in data if d['group'] == g]
                 avg = sum(d[f] for d in g_data) / len(g_data) if g_data else 0
                 vals.append(avg)
            
            fig.add_trace(go.Bar(
                name=metrics['labels'][f], 
                y=groups, x=vals,
                orientation='h',
                marker_color=metrics['colors'][f],
                text=[f'{v:.1f}' for v in vals], textposition='auto'
            ))

        fig.update_layout(
            title='Ranking Detallado por Grupos', barmode='group',
            xaxis=dict(range=[0, 100], title='Puntuación Media'),
            yaxis=dict(title='Grupo', autorange="reversed"),
            height=max(400, len(groups) * 50),
            template='plotly_white',
            legend=dict(orientation="h", y=1.05)
        )
        return fig

    def _build_final_html(self, evaluation, kpi, heat, trend, gender, ranking):
        return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Dashboard AulaMetrics</title>
    <script src="https://cdn.plot.ly/plotly-2.26.0.min.js"></script>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body {{ background: #f4f6f9; font-family: 'Segoe UI', sans-serif; padding-bottom: 60px; }}
        .header {{ background: white; padding: 25px; border-bottom: 1px solid #e9ecef; margin-bottom: 30px; }}
        .kpi-container {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 25px; margin-bottom: 30px; }}
        .kpi-card {{ background: white; padding: 25px; border-radius: 12px; box-shadow: 0 2px 12px rgba(0,0,0,0.03); }}
        .kpi-title {{ font-size: 0.85rem; color: #6c757d; font-weight: 700; text-transform: uppercase; margin-bottom: 10px; }}
        .kpi-value {{ font-size: 2.8rem; font-weight: 700; color: #212529; line-height: 1.2; }}
        .kpi-sub {{ color: #adb5bd; font-size: 0.9rem; }}
        
        .section-title {{ font-size: 1.1rem; font-weight: 600; color: #343a40; margin-bottom: 15px; padding-left: 5px; border-left: 4px solid #0d6efd; line-height: 1.2; }}
        .chart-card {{ background: white; border-radius: 12px; padding: 20px; box-shadow: 0 2px 12px rgba(0,0,0,0.03); margin-bottom: 25px; height: 100%; }}
        
        .grid-split {{ display: grid; grid-template-columns: 1fr 1fr; gap: 25px; margin-bottom: 25px; }}
        
        @media (max-width: 992px) {{ .grid-split {{ grid-template-columns: 1fr; }} }}
    </style>
</head>
<body class="container-fluid px-0">
    <div class="header">
        <div class="container-fluid px-4">
            <h2 class="fw-bold mb-1">Resultados de Evaluación</h2>
            <p class="text-muted mb-0">{evaluation.name} | {fields.Date.today()}</p>
        </div>
    </div>

    <div class="container-fluid px-4">
        {kpi}

        <div class="row mb-4">
            <div class="col-12">
                <div class="section-title">Mapa Estratégico (Visión Centro)</div>
                <div class="chart-card">
                    {heat.to_html(include_plotlyjs=False, full_html=False, config={'displayModeBar': False})}
                </div>
            </div>
        </div>
        
        <div class="row">
            <div class="col-lg-6 mb-4">
                <div class="section-title">Tendencias por Edad</div>
                <div class="chart-card">
                    {trend.to_html(include_plotlyjs=False, full_html=False, config={'displayModeBar': False})}
                </div>
            </div>
            <div class="col-lg-6 mb-4">
                <div class="section-title">Distribución por Género</div>
                <div class="chart-card">
                    {gender.to_html(include_plotlyjs=False, full_html=False, config={'displayModeBar': False})}
                </div>
            </div>
        </div>

        <div class="row mb-4">
            <div class="col-12">
                <div class="section-title">Comparativa Detallada de Grupos</div>
                <div class="chart-card">
                    {ranking.to_html(include_plotlyjs=False, full_html=False, config={'displayModeBar': False})}
                    <div class="text-center text-muted mt-2 small">Ranking de puntuaciones promedio por grupo académico</div>
                </div>
            </div>
        </div>
        
    </div>
</body>
</html>"""

    def _error_html(self, message):
         return f"""<div style="text-align:center; padding:50px; font-family:sans-serif; color:#666;">
            <h3>🚧 {message}</h3></div>"""
