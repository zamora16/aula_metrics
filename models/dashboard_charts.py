# -*- coding: utf-8 -*-
"""
Dashboard Charts - Generación de gráficos interactivos con Plotly
Versión Ejecutiva/Orientación - Enero 2026
"""
from odoo import models, fields, api

# Importar configuración centralizada
from .survey_config import SURVEY_METRICS

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
        if not go:
            return self._error_html("Plotly no instalado.")

        evaluation = self.env['aulametrics.evaluation'].browse(evaluation_id)
        if not evaluation.exists():
            return self._error_html("Evaluación no encontrada")

        metrics = self._get_metrics(evaluation)
        participations = evaluation.participation_ids.filtered(lambda p: p.state == 'completed')
        if not participations:
            return self._error_html("Esperando datos... No hay participaciones completas aún.")

        # Secuencia modularizada
        data = self._prepare_data_section(participations, metrics)
        kpi_html = self._generate_kpis_section(data, metrics, evaluation)
        fig_heatmap = self._generate_heatmap_section(go, data, metrics)
        fig_gender = self._generate_gender_section(go, data, metrics)
        fig_ranking = self._generate_ranking_section(go, data, metrics)

        return self._build_final_html(evaluation, kpi_html, fig_heatmap, fig_gender, fig_ranking)

    def _prepare_data_section(self, participations, metrics):
        """Preprocesamiento de datos para el dashboard."""
        return self._prepare_dataframe(participations, metrics)

    def _generate_kpis_section(self, data, metrics, evaluation):
        """Generación de KPIs en HTML."""
        return self._generate_kpis_html(data, metrics, evaluation)

    def _generate_heatmap_section(self, go, data, metrics):
        """Creación de figura Heatmap Plotly."""
        return self._chart_heatmap(go, data, metrics)

    def _generate_gender_section(self, go, data, metrics):
        """Creación de figura de distribución por género."""
        return self._chart_gender_box(go, data, metrics)

    def _generate_ranking_section(self, go, data, metrics):
        """Creación de figura de ranking de grupos."""
        return self._chart_groups_ranking(go, data, metrics)

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

        html = '<div class="kpi-container">'
        
        # KPI 1: Tasa Global
        html += f"""
        <div class="kpi-card" style="border-bottom: 4px solid {p_color}">
            <i class="fa-solid fa-users kpi-icon-bg"></i>
            <div>
                <div class="kpi-label">Participación Global</div>
                <div class="kpi-number">{part_rate:.1f}%</div>
                <div class="kpi-sub">{evaluation.completed_students}/{evaluation.total_students} alumnos</div>
            </div>
        </div>
        """

        # Desglose por grupos si hay más de 1
        groups = list(set(d['group'] for d in data))
        if len(groups) > 1:
            for group in sorted(groups):
                group_participations = [d for d in data if d['group'] == group]
                completed = len(group_participations)
                # Obtener total de estudiantes en el grupo
                group_obj = self.env['aulametrics.academic_group'].search([('name', '=', group)], limit=1)
                total = group_obj.student_count if group_obj else completed
                rate = (completed / total * 100) if total > 0 else 0
                g_color = '#28a745' if rate > 80 else '#ffc107' if rate > 50 else '#dc3545'
                html += f"""
                <div class="kpi-card" style="border-bottom: 4px solid {g_color}">
                    <i class="fa-solid fa-school kpi-icon-bg"></i>
                    <div>
                        <div class="kpi-label">{group}</div>
                        <div class="kpi-number">{rate:.1f}%</div>
                        <div class="kpi-sub">{completed}/{total} alumnos</div>
                    </div>
                </div>
                """
        html += '</div>'

        return html

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
            legend=dict(orientation="h", y=1.15, x=0.5, xanchor='center')
        )
        return fig

    def _build_final_html(self, evaluation, kpi, heat, gender, ranking):
        return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Dashboard AulaMetrics</title>
    <script src="https://cdn.plot.ly/plotly-2.26.0.min.js"></script>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap" rel="stylesheet">
    <style>
        body {{ background: #f1f5f9; font-family: 'Inter', sans-serif; padding-bottom: 60px; color: #1e293b; }}
        .dashboard-header {{ background: white; padding: 1.5rem 2rem; border-bottom: 1px solid #e2e8f0; margin-bottom: 2rem; display: flex; justify-content: space-between; align-items: center; box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.05); }}
        .header-title h1 {{ font-size: 1.5rem; font-weight: 700; margin: 0; color: #0f172a; }}
        .header-meta {{ color: #64748b; font-size: 0.875rem; margin-top: 4px; }}
        .kpi-container {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 25px; margin-bottom: 30px; }}
        .kpi-card {{
            background: white;
            border-radius: 16px;
            padding: 1.5rem;
            border: 1px solid #f1f5f9;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);
            transition: transform 0.2s ease, box-shadow 0.2s ease;
            position: relative;
            overflow: hidden;
        }}
        
        .kpi-card:hover {{
            transform: translateY(-2px);
            box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05);
        }}

        .kpi-icon-bg {{
            position: absolute;
            right: -10px;
            top: -10px;
            font-size: 5rem;
            opacity: 0.05;
            transform: rotate(15deg);
        }}
        .kpi-label {{ font-size: 0.85rem; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; }}
        .kpi-number {{ font-size: 2.5rem; font-weight: 700; color: #0f172a; margin: 0.5rem 0; letter-spacing: -0.02em; }}
        .kpi-sub {{ font-size: 0.85rem; color: #64748b; }}
        
        .section-header {{
            display: flex;
            align-items: center;
            margin-bottom: 1.25rem;
            margin-top: 1rem;
        }}
        
        .section-icon {{
            width: 32px;
            height: 32px;
            background: #e0e7ff;
            color: #4f46e5;
            border-radius: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            margin-right: 12px;
        }}
        
        .section-title {{
            font-size: 1.1rem;
            font-weight: 600;
            color: #334155;
            margin: 0;
        }}

        /* Animaciones */
        @keyframes fadeInUp {{
            from {{
                opacity: 0;
                transform: translateY(30px);
            }}
            to {{
                opacity: 1;
                transform: translateY(0);
            }}
        }}

        .chart-card {{
            background: white;
            border-radius: 16px;
            padding: 1.5rem;
            border: 1px solid #f1f5f9;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);
            transition: transform 0.2s ease, box-shadow 0.2s ease;
            height: 100%;
            overflow: hidden;
            animation: fadeInUp 0.6s ease-out;
        }}
        
        .chart-card:hover {{
            transform: translateY(-2px);
            box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05);
        }}
        
        .grid-split {{ display: grid; grid-template-columns: 1fr 1fr; gap: 25px; margin-bottom: 25px; }}
        
        @media (max-width: 992px) {{ .grid-split {{ grid-template-columns: 1fr; }} }}
    </style>
</head>
<body class="container-fluid px-0">
    <header class="dashboard-header">
        <div>
            <div class="header-title">
                <h1><i class="fa-solid fa-chart-pie me-2 text-primary"></i>Resultados de Evaluación</h1>
            </div>
            <div class="header-meta">
                {evaluation.name} &bull; Generado el {fields.Date.today().strftime('%d/%m/%Y')}
            </div>
        </div>
        <div>
            <span class="badge bg-light text-dark border px-3 py-2">
                <i class="fa-regular fa-user me-1"></i> Ejecutivo
            </span>
        </div>
    </header>

    <div class="container-fluid px-4">
        {kpi}

        <div class="row mb-2">
            <div class="col-12">
                <div class="section-header">
                    <div class="section-icon"><i class="fa-solid fa-layer-group"></i></div>
                    <h3 class="section-title">Mapa Estratégico</h3>
                </div>
                <div class="chart-card">
                    {heat.to_html(include_plotlyjs=False, full_html=False, config={'displayModeBar': False})}
                </div>
            </div>
        </div>
        
        <div class="row mb-5" style="margin-top: 4rem;">
            <div class="col-lg-6 mb-4 mb-lg-0">
                <div class="section-header">
                    <div class="section-icon"><i class="fa-solid fa-venus-mars"></i></div>
                    <h3 class="section-title">Distribución por Género</h3>
                </div>
                <div class="chart-card">
                    {gender.to_html(include_plotlyjs=False, full_html=False, config={'displayModeBar': False})}
                </div>
            </div>
            <div class="col-lg-6">
                <div class="section-header">
                    <div class="section-icon"><i class="fa-solid fa-list-ol"></i></div>
                    <h3 class="section-title">Ranking de Grupos</h3>
                </div>
                <div class="chart-card">
                    {ranking.to_html(include_plotlyjs=False, full_html=False, config={'displayModeBar': False})}
                    <div class="text-center text-muted mt-2 small">Ranking de puntuaciones promedio por grupo académico</div>
                </div>
            </div>
</html>"""

    def _error_html(self, message):
         return f"""<div style="text-align:center; padding:50px; font-family:sans-serif; color:#666;">
            <h3>🚧 {message}</h3></div>"""
