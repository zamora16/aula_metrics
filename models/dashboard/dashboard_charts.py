# -*- coding: utf-8 -*-
"""
Dashboard Charts - Generación de dashboard con métricas filtradas
"""
from odoo import models, api, fields
import pandas as pd
import json

# Importar utilidades compartidas
from ...utils import dashboard_styles, dashboard_helpers, palette, role_service
from ...utils.constants import ROLE_ADMIN, ROLE_COUNSELOR, ROLE_MANAGEMENT, ROLE_TUTOR
from . import dashboard_data_queries

class DashboardCharts(models.TransientModel):
    _name = 'aula_metrics.dashboard.charts'
    _description = 'Generador de Dashboard de Métricas'

    @api.model
    def generate_dashboard(self, filters=None, role_info=None):
        """
        Genera el dashboard de métricas con filtros dinámicos.
        
        Args:
            filters (dict): Filtros aplicados {evaluation_ids}
            role_info (dict): Información de rol del usuario
        
        Returns:
            Dict: Valores para renderizado QWeb via 'aula_metrics.dashboard_main'
        """
        if filters is None:
            filters = {}
        if role_info is None:
            role_info = {'role': 'admin', 'anonymize_students': False}

        # Obtener opciones disponibles para los filtros
        available_metrics = self.env['aula_metrics.dashboard.data_queries'].get_available_metrics(filters, role_info)
        available_groups = self.env['aula_metrics.dashboard.data_queries'].get_available_groups(filters, role_info)
        available_evaluations = self.env['aula_metrics.dashboard.data_queries'].get_available_evaluations(role_info)
        segmentation_vars = self.env['aula_metrics.dashboard.data_queries'].get_segmentation_variables(filters, role_info)

        # Si no hay datos disponibles, mostrar mensaje
        if not available_metrics:
            return self._build_html_empty(
                available_metrics, available_groups, available_evaluations, 
                filters, role_info
            )

        # Consultar valores de métricas según filtros
        metric_values = self.env['aula_metrics.dashboard.data_queries'].query_metric_values(filters, role_info)
        
        if not metric_values:
            return self._build_html_empty(
                available_metrics, available_groups, available_evaluations,
                filters, role_info
            )

        # Preparar DataFrame
        df = self.env['aula_metrics.dashboard.data_queries'].prepare_dataframe(metric_values, role_info)
        
        # Generar gráficos
        charts = self._generate_charts(df, filters, available_metrics, role_info, segmentation_vars)
        
        # Generar KPIs (retorna dict con kpi_students, kpi_groups, kpi_evals, kpi_metrics)
        kpi_values = self._generate_kpis(df, filters, role_info)
        
        # Construir contexto para dashboard_main
        return self._build_html(
            available_metrics, available_groups, available_evaluations, 
            filters, role_info, kpi_values, charts, segmentation_vars
        )
        
    def _get_segmentation_variables(self, filters, role_info):
        """Obtiene variables de segmentación disponibles dinámicamente.
        
        Args:
            filters (dict): Filtros actuales aplicados
            role_info (dict): Información del rol del usuario
        
        Returns:
            list: Lista de dicts con estructura {value, label, type, options}
        """
        return dashboard_data_queries.get_segmentation_variables(self, filters, role_info)
    def _build_segment_options_html(self, segmentation_vars):
        """Construye el HTML del selector de segmentación.
        
        Args:
            segmentation_vars (list): Lista de variables de segmentación
        
        Returns:
            str: HTML con opciones del selector
        """
        options_html = '<option value="">Sin segmentar</option>'
        for seg_var in segmentation_vars:
            options_html += f'<option value="{seg_var["value"]}">{seg_var["label"]}</option>'
        return options_html
    
    def _build_global_segmentation_selector(self, segmentation_vars):
        """Construye el selector de segmentación global que afecta a todas las gráficas.
        
        Args:
            segmentation_vars (list): Lista de variables de segmentación históricas
        
        Returns:
            str: HTML del selector global con JavaScript para sincronizar todas las gráficas
        """
        if not segmentation_vars:
            return ''
        
        segment_options_html = self._build_segment_options_html(segmentation_vars)
        
        return f"""
        <div class="global-segmentation-bar mb-4" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 16px 24px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
            <div class="d-flex align-items-center justify-content-between">
                <div class="d-flex align-items-center gap-3">
                    <div style="background: rgba(255,255,255,0.2); padding: 10px; border-radius: 8px;">
                        <i class="fa-solid fa-layer-group" style="font-size: 24px; color: white;"></i>
                    </div>
                    <div>
                        <h6 class="mb-0" style="color: white; font-weight: 600;">Segmentación Global</h6>
                        <p class="mb-0" style="color: rgba(255,255,255,0.8); font-size: 13px;">Divide los datos en todas las gráficas comparativas</p>
                    </div>
                </div>
                <select id="globalSegmentationSelector" class="form-select" style="max-width: 300px; border: 2px solid rgba(255,255,255,0.3); background: rgba(255,255,255,0.95); font-weight: 500;">
                    {segment_options_html}
                </select>
            </div>
        </div>
        
        <script>
        (function() {{
            const globalSelector = document.getElementById('globalSegmentationSelector');
            
            // Escuchar cambios en el selector global
            globalSelector.addEventListener('change', function(e) {{
                const selectedSegmentation = e.target.value;
                
                // Disparar evento personalizado que todas las gráficas escucharán
                document.dispatchEvent(new CustomEvent('globalSegmentationChange', {{
                    detail: {{ segmentation: selectedSegmentation }}
                }}));
            }});
        }})();
        </script>
        """


    def _generate_charts(self, df, filters, available_metrics, role_info, segmentation_vars):
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
            
            chart_html = self._generate_chart_by_metric_type(metric_info, df, role_info, segmentation_vars)
            if chart_html:
                charts.append(chart_html)
        
        return charts

    def _generate_chart_by_metric_type(self, metric_info, df, role_info, segmentation_vars):
        """Genera el gráfico apropiado según el tipo de métrica y rol."""
        metric_name = metric_info['name']
        metric_label = metric_info['label']
        metric_type = metric_info['type']
        
        df_metric = df[df['metric_name'] == metric_name].copy()
        
        if metric_type == 'numeric':
            return self._chart_numeric_metric(df_metric, metric_label, role_info, segmentation_vars)
        elif metric_type == 'json':
            # Las métricas JSON solo se usan para segmentación, no generan cards propias
            return ''
        # Las métricas de texto no se muestran aquí, se gestionan en la pestaña cualitativa
        
        return ''

    def _chart_numeric_metric(self, df, label, role_info, segmentation_vars):
        """Gráfico adaptado según rol del usuario con gradiente de colores."""
        if df.empty or df['value_numeric'].isna().all():
            return ''
        
        role = role_info.get('role', 'counselor')
        charts_html = ''
        
        # Detectar si hay múltiples mediciones temporales
        evaluations = df['evaluation_name'].dropna().unique()
        has_evolution = len(evaluations) >= 2
        
        # Gráfico principal según rol
        if role == ROLE_MANAGEMENT:
            # Management usa la misma UI que counselor pero con datos por curso
            by_courses_html = self._chart_numeric_by_course(df, label, segmentation_vars)
            evo_html = self._chart_numeric_evolution_by_course(df, label) if has_evolution else ''
            
            if by_courses_html and evo_html:
                charts_html += self._chart_numeric_with_toggle(by_courses_html, evo_html, label, 'curso')
            else:
                charts_html += by_courses_html or evo_html
                
        elif role == ROLE_TUTOR:
            charts_html += self._chart_numeric_distribution(df, label, segmentation_vars)
            if has_evolution:
                charts_html += self._chart_numeric_evolution_distribution(df, label)
        else:  # counselor/admin
            # Generar ambas vistas por separado y, si existen las dos, combinarlas
            by_groups_html = self._chart_numeric_by_groups(df, label, segmentation_vars)
            evo_html = self._chart_numeric_evolution_by_groups(df, label) if has_evolution else ''

            if by_groups_html and evo_html:
                charts_html += self._chart_numeric_with_toggle(by_groups_html, evo_html, label, 'grupo')
            else:
                charts_html += by_groups_html or evo_html

        return charts_html

    def _chart_numeric_with_toggle(self, by_groups_html, evo_html, label, tipo='grupo'):
        """Combina la card de comparativa por grupo/curso y la de evolución en una sola card con un switch.

        - Preserva IDs de canvas/controls ya generados por las funciones hijas.
        - Oculta los headers internos (solo se muestra el header combinado).
        - Fuerza resize/update de Chart.js al alternar vistas.
        
        Args:
            tipo: 'grupo' para counselor o 'curso' para management
        """
        if not by_groups_html and not evo_html:
            return ''
        if not by_groups_html:
            return evo_html
        if not evo_html:
            return by_groups_html

        safe_id = dashboard_helpers.sanitize_id(label)
        wrapper_by = f'view_by_{safe_id}'
        wrapper_evo = f'view_evo_{safe_id}'
        toggle_id = f'toggle_{safe_id}'
        
        # Subtítulo dinámico según el tipo
        subtitle = f"Comparativa por {tipo} · Evolución temporal"
        comparativa_title = f"Comparativa por {tipo}"

        html = '''
        <div class="card">
            <div class="card-header" style="display:flex; justify-content:space-between; align-items:center; gap:12px;">
                <div>
                    <h5 class="card-title">__LABEL__</h5>
                    <p class="card-subtitle">__SUBTITLE__</p>
                </div>
                <div style="display:flex; gap:5px; align-items:center;">
                    <button id="__TOGGLE_ID___bars" class="btn btn-sm btn-outline-primary active" style="padding:6px 10px;" title="__COMPARATIVA_TITLE__">
                        <i class="fa fa-bar-chart"></i>
                    </button>
                    <button id="__TOGGLE_ID___lines" class="btn btn-sm btn-outline-primary" style="padding:6px 10px;" title="Evolución temporal">
                        <i class="fa fa-line-chart"></i>
                    </button>
                </div>
            </div>
            <div class="card-body" style="padding:0;">
                <div id="__WRAP_BY__">__BY_HTML__</div>
                <div id="__WRAP_EVO__" style="display:none;">__EVO_HTML__</div>
            </div>
        </div>

        <style>
        /* Ocultar header interno SOLO de la vista de evolución (la comparativa mantiene sus controles) */
        #__WRAP_EVO__ .card-header { display: none; }
        /* Ocultar título/subtítulo de la header de la comparativa embebida pero conservar controles */
        #__WRAP_BY__ .card-header .card-title, #__WRAP_BY__ .card-header .card-subtitle { display: none; }
        /* Ajustes visuales para que el contenido embebido se vea consistente */
        #__WRAP_BY__ .card-body, #__WRAP_EVO__ .card-body { padding: 16px; }
        </style>

        <script>
        (function() {
            const btnBars = document.getElementById('__TOGGLE_ID___bars');
            const btnLines = document.getElementById('__TOGGLE_ID___lines');
            const viewBy = document.getElementById('__WRAP_BY__');
            const viewEvo = document.getElementById('__WRAP_EVO__');

            function setView(showEvo) {
                viewBy.style.display = showEvo ? 'none' : 'block';
                viewEvo.style.display = showEvo ? 'block' : 'none';
                
                // Actualizar botones
                if (showEvo) {
                    btnBars.classList.remove('active');
                    btnLines.classList.add('active');
                } else {
                    btnBars.classList.add('active');
                    btnLines.classList.remove('active');
                }

                // Forzar resize/update de Chart.js para asegurar render correcto
                try {
                    const byCanvas = viewBy.querySelector('canvas');
                    const evoCanvas = viewEvo.querySelector('canvas');
                    if (byCanvas) {
                        const ch = Chart.getChart(byCanvas.id);
                        if (ch) { ch.resize(); ch.update(); }
                    }
                    if (evoCanvas) {
                        const ch2 = Chart.getChart(evoCanvas.id);
                        if (ch2) { ch2.resize(); ch2.update(); }
                    }
                } catch (err) { console.warn('chart toggle resize error', err); }
            }

            btnBars.addEventListener('click', function() { setView(false); });
            btnLines.addEventListener('click', function() { setView(true); });
            // Por defecto: mostrar comparativa por grupo/curso
            setView(false);
        })();
        </script>
        '''
        return html.replace('__TOGGLE_ID__', toggle_id).replace('__WRAP_BY__', wrapper_by).replace('__WRAP_EVO__', wrapper_evo).replace('__LABEL__', label).replace('__SUBTITLE__', subtitle).replace('__COMPARATIVA_TITLE__', comparativa_title).replace('__BY_HTML__', by_groups_html).replace('__EVO_HTML__', evo_html)

    def _get_semaphore_color(self, value):
        """Retorna color gradiente según valor normalizado 0-100."""
        if value >= 80:
            return '#f97316'  # Naranja oscuro - Alto
        elif value >= 60:
            return '#fb923c'  # Naranja suave - Medio-Alto
        elif value >= 40:
            return '#60a5fa'  # Azul claro - Medio-Bajo
        else:
            return '#3b82f6'  # Azul oscuro - Bajo
    
    def _get_thresholds_for_metric(self, metric_name):
        """Obtiene umbrales activos configurados para una métrica.
        
        Args:
            metric_name (str): Nombre de la métrica (ej: 'who5_score', 'asq14_total')
        
        Returns:
            list: Lista de dicts con {value, operator, label, severity}
        """
        Threshold = self.env['aula_metrics.threshold']
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
    
