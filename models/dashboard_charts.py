# -*- coding: utf-8 -*-
"""
Dashboard Charts - Generación de gráficos interactivos con Plotly
"""
from odoo import models, fields, api

# =============================================================================
# CONFIGURACIÓN DE MÉTRICAS POR CUESTIONARIO
# Para añadir un nuevo cuestionario:
# 1. Crear el XML del survey en data/surveys/ con survey_code único
# 2. Añadir el campo *_score en models/participation.py
# 3. Añadir entrada aquí: fields, labels, colors
# =============================================================================
SURVEY_METRICS = {
    'WHO5': {
        'fields': ['who5_score'],
        'labels': {'who5_score': 'WHO-5 (Bienestar)'},
        'colors': {'who5_score': '#28a745'},
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
    },
    'ASQ14': {
        'fields': ['stress_score'],
        'labels': {'stress_score': 'Estrés (ASQ-14)'},
        'colors': {'stress_score': '#fd7e14'},
    },
}


class DashboardCharts(models.TransientModel):
    """Modelo transient para generación de dashboard completo."""
    _name = 'aulametrics.dashboard.charts'
    _description = 'Generador de Dashboard'

    evaluation_id = fields.Many2one('aulametrics.evaluation', string='Evaluación')

    @staticmethod
    def _import_plotly():
        """Importa Plotly dinámicamente."""
        try:
            import plotly.graph_objects as go
            from plotly.subplots import make_subplots
            return go, make_subplots
        except ImportError:
            return None, None

    def _get_metrics(self, evaluation):
        """Obtiene métricas según cuestionarios de la evaluación."""
        metrics = {'fields': [], 'labels': {}, 'colors': {}}
        for survey in evaluation.survey_ids:
            if survey.survey_code in SURVEY_METRICS:
                cfg = SURVEY_METRICS[survey.survey_code]
                metrics['fields'].extend(cfg['fields'])
                metrics['labels'].update(cfg['labels'])
                metrics['colors'].update(cfg['colors'])
        return metrics

    def _group_data(self, participations, group_field, metrics):
        """Agrupa participaciones por campo."""
        data = {}
        for p in participations:
            key = getattr(p, group_field, None)
            key = key.name if hasattr(key, 'name') and key else (key or 'Otro')
            if not key:
                key = 'Sin grupo'
            if key not in data:
                data[key] = {f: [] for f in metrics['fields']}
            for f in metrics['fields']:
                data[key][f].append(getattr(p, f) or 0)
        return data

    @api.model
    def generate_dashboard(self, evaluation_id):
        """Genera dashboard completo con todos los gráficos."""
        go, make_subplots = self._import_plotly()
        if not go:
            return self._error_html("Plotly no instalado. Ejecuta: pip install plotly")

        evaluation = self.env['aulametrics.evaluation'].browse(evaluation_id)
        if not evaluation.exists():
            return self._error_html("Evaluación no encontrada")

        metrics = self._get_metrics(evaluation)
        if not metrics['fields']:
            return self._error_html("Sin cuestionarios configurados en esta evaluación")

        participations = evaluation.participation_ids.filtered(lambda p: p.state == 'completed')
        if not participations:
            return self._error_html("Sin participaciones completadas")

        # Generar cada gráfico
        fig1 = self._chart_overview(go, evaluation, metrics, participations)
        fig2 = self._chart_donut(go, evaluation)
        fig3 = self._chart_gender(go, metrics, participations)
        fig4 = self._chart_histogram(go, make_subplots, metrics, participations)

        # Combinar todo en un HTML
        return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Dashboard - {evaluation.name}</title>
    <script src="https://cdn.plot.ly/plotly-2.26.0.min.js"></script>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
               margin: 0; padding: 20px; background: #f5f5f5; }}
        .header {{ background: white; padding: 20px; margin-bottom: 20px; border-radius: 8px;
                  box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .header h1 {{ margin: 0 0 10px 0; color: #333; }}
        .stats {{ display: flex; gap: 20px; margin-top: 15px; }}
        .stat {{ background: #f8f9fa; padding: 10px 15px; border-radius: 5px; }}
        .stat-value {{ font-size: 24px; font-weight: bold; color: #7C3AED; }}
        .stat-label {{ font-size: 12px; color: #6c757d; text-transform: uppercase; }}
        .grid {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 20px; }}
        .chart {{ background: white; padding: 15px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .full {{ grid-column: span 2; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Dashboard de Resultados</h1>
        <div style="color: #6c757d;">{evaluation.name}</div>
        <div class="stats">
            <div class="stat">
                <div class="stat-value">{evaluation.completed_students}</div>
                <div class="stat-label">Completados</div>
            </div>
            <div class="stat">
                <div class="stat-value">{evaluation.total_students}</div>
                <div class="stat-label">Total Alumnos</div>
            </div>
            <div class="stat">
                <div class="stat-value">{evaluation.participation_rate:.1f}%</div>
                <div class="stat-label">Participación</div>
            </div>
        </div>
    </div>
    <div class="grid">
        <div class="chart full">{fig1.to_html(include_plotlyjs=False, div_id='chart1')}</div>
        <div class="chart">{fig2.to_html(include_plotlyjs=False, div_id='chart2')}</div>
        <div class="chart">{fig3.to_html(include_plotlyjs=False, div_id='chart3')}</div>
        <div class="chart full">{fig4.to_html(include_plotlyjs=False, div_id='chart4')}</div>
    </div>
</body>
</html>"""

    def _chart_overview(self, go, evaluation, metrics, participations):
        """Gráfico de barras: métricas por grupo."""
        groups_data = self._group_data(participations, 'academic_group_id', metrics)
        
        fig = go.Figure()
        for field in metrics['fields']:
            avgs = [sum(groups_data[g][field]) / len(groups_data[g][field]) 
                   if groups_data[g][field] else 0 for g in groups_data]
            fig.add_trace(go.Bar(
                name=metrics['labels'][field], x=list(groups_data.keys()), y=avgs,
                marker_color=metrics['colors'][field],
                text=[f'{v:.1f}' for v in avgs], textposition='auto'
            ))
        
        fig.update_layout(
            title=f'Métricas por Grupo - {evaluation.name}',
            barmode='group', xaxis_title='Grupo', yaxis_title='Puntuación (0-100)',
            yaxis=dict(range=[0, 100]), template='plotly_white', height=400,
            legend=dict(orientation="h", y=1.1, x=0.5, xanchor="center"),
        )
        return fig

    def _chart_donut(self, go, evaluation):
        """Gráfico de dona: estado de participación."""
        states = evaluation.participation_ids.mapped('state')
        completed = states.count('completed')
        pending = states.count('pending')
        expired = states.count('expired')
        
        fig = go.Figure(data=[go.Pie(
            labels=['Completadas', 'Pendientes', 'Expiradas'],
            values=[completed, pending, expired],
            hole=0.5, marker_colors=['#28a745', '#ffc107', '#6c757d'],
            textinfo='value+percent'
        )])
        fig.update_layout(
            title='Estado de Participación', template='plotly_white', height=350,
            annotations=[dict(text=f'{len(states)}<br>Total', x=0.5, y=0.5, showarrow=False)]
        )
        return fig

    def _chart_gender(self, go, metrics, participations):
        """Gráfico de barras: comparativa por género."""
        gender_data = self._group_data(participations, 'student_gender', metrics)
        gender_labels = {'male': 'Masculino', 'female': 'Femenino', 'other': 'Otro'}
        labels = [gender_labels.get(g, g) for g in gender_data.keys()]
        
        fig = go.Figure()
        for field in metrics['fields']:
            avgs = [sum(gender_data[g][field]) / len(gender_data[g][field]) 
                   if gender_data[g][field] else 0 for g in gender_data]
            fig.add_trace(go.Bar(
                name=metrics['labels'][field], x=labels, y=avgs,
                marker_color=metrics['colors'][field],
                text=[f'{v:.1f}' for v in avgs], textposition='auto'
            ))
        
        fig.update_layout(
            title='Comparativa por Género', barmode='group',
            xaxis_title='Género', yaxis_title='Puntuación (0-100)',
            yaxis=dict(range=[0, 100]), template='plotly_white', height=350,
            legend=dict(orientation="h", y=1.1, x=0.5, xanchor="center"),
        )
        return fig

    def _chart_histogram(self, go, make_subplots, metrics, participations):
        """Histogramas de distribución."""
        num = len(metrics['fields'])
        cols = min(num, 3)
        rows = (num + cols - 1) // cols
        
        fig = make_subplots(
            rows=rows, cols=cols,
            subplot_titles=[metrics['labels'][f] for f in metrics['fields']],
            horizontal_spacing=0.08, vertical_spacing=0.15
        )
        
        for idx, field in enumerate(metrics['fields']):
            r, c = idx // cols + 1, idx % cols + 1
            values = [getattr(p, field) or 0 for p in participations]
            
            fig.add_trace(go.Histogram(
                x=values, nbinsx=10, marker_color=metrics['colors'][field],
                opacity=0.8, showlegend=False
            ), row=r, col=c)
            
            fig.update_xaxes(title_text='Puntuación', row=r, col=c)
            fig.update_yaxes(title_text='Nº Alumnos', row=r, col=c)
        
        fig.update_layout(
            title='Distribución de Puntuaciones', template='plotly_white',
            height=300 * rows, margin=dict(l=50, r=50, t=80, b=50)
        )
        return fig

    def _error_html(self, message):
        """HTML de error."""
        return f"""<!DOCTYPE html><html><head><style>
            body {{ font-family: sans-serif; display: flex; justify-content: center;
                   align-items: center; height: 100vh; margin: 0; background: #f8f9fa; }}
            .msg {{ text-align: center; padding: 40px; background: white;
                   border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        </style></head><body><div class="msg"><h3>{message}</h3></div></body></html>"""
