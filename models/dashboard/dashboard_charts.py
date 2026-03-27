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
        
        # Generar KPIs (retorna dict con kpi_students, kpi_groups, kpi_evals, kpi_participation)
        kpi_values = self._generate_kpis(df, filters, role_info)
        
        # Construir contexto para dashboard_main
        return self._build_html(
            available_metrics, available_groups, available_evaluations, 
            filters, role_info, kpi_values, charts, segmentation_vars
        )
        
    def _get_segmentation_variables(self, filters, role_info):
        """Obtiene variables de segmentación disponibles dinámicamente."""
        return self.env['aula_metrics.dashboard.data_queries'].get_segmentation_variables(
            filters, role_info
        )
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
        <div class="global-segmentation-bar mb-4" style="background: {palette.UI_SEGMENTATION_BAR_GRADIENT}; padding: 16px 24px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
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
        """Genera gráficos. Los cuestionarios oficiales con sub-escalas se agrupan
        en una card jerárquica (total prominente + sub-escalas colapsables).
        El resto de métricas genera una card individual por métrica.
        """
        charts = []
        multiscale_metric_names = set()

        # Paso 1: detectar cuestionarios oficiales multi-escala y agruparlos
        if 'survey_id' in df.columns and 'is_aulametrics' in df.columns:
            for survey_id, df_survey in df.groupby('survey_id', dropna=False):
                if pd.isna(survey_id) or not df_survey['is_aulametrics'].any():
                    continue
                numeric_names = (
                    df_survey[df_survey['metric_type'] == 'numeric']['metric_name'].unique()
                )
                if len(numeric_names) > 1:
                    chart = self._chart_multi_scale_survey(df_survey, role_info, segmentation_vars)
                    if chart:
                        charts.append(chart)
                        multiscale_metric_names.update(numeric_names)

        # Paso 2: métricas individuales (no agrupadas en paso 1)
        # Solo tipos que producen gráficos cuantitativos; 'text' va al dashboard cualitativo.
        grouped = (
            df[
                ~df['metric_name'].isin(multiscale_metric_names) &
                (df['metric_type'] == 'numeric')
            ]
            .groupby(['metric_name', 'metric_label', 'metric_type'])
            .size().reset_index(name='count')
        )
        for _, row in grouped.iterrows():
            metric_info = {
                'name':  row['metric_name'],
                'label': row['metric_label'],
                'type':  row['metric_type'],
            }
            chart_html = self._generate_chart_by_metric_type(metric_info, df, role_info, segmentation_vars)
            if chart_html:
                charts.append(chart_html)

        return charts

    def _get_y_range_for_metric(self, df_metric):
        """Determina el rango (y_min, y_max) del eje de valores según los baremos del cuestionario.

        - Centro (is_aulametrics=False): (0, 100) — scores normalizados.
        - Oficial con baremos: (min baremo score_min, max baremo score_max) para esa escala.
            SDQ_emotional → scale_name='emotional' → (0, 10)
            SWLS          → metric_name == survey_code → scale_name='total' → (5, 35)
        - Sin baremos para esa escala: (0, 110% del valor máximo real).
        """
        if df_metric.empty or 'is_aulametrics' not in df_metric.columns:
            return (0, 100)
        if not df_metric['is_aulametrics'].any():
            return (0, 100)

        survey_id_vals = df_metric['survey_id'].dropna()
        if survey_id_vals.empty:
            return (0, 100)

        survey = self.env['survey.survey'].browse(int(survey_id_vals.iloc[0]))
        if not survey.exists() or not survey.baremo_ids:
            data_max = df_metric['value_numeric'].dropna().max()
            y_max = round(float(data_max) * 1.1, 1) if pd.notna(data_max) else 100
            return (0, y_max)

        # Derivar scale_name desde metric_name usando survey_code.
        # Patrones soportados:
        #   SDQ_emotional → survey_code='SDQ', scale_name='emotional'
        #   SWLS          → metric_name == survey_code → scale_name='total' (escala única)
        metric_name = df_metric['metric_name'].iloc[0]
        survey_code = (survey.survey_code or '').strip().upper()

        if survey_code and metric_name.upper().startswith(f'{survey_code}_'):
            # Multi-escala: SDQ_emotional, SDQ_total, …
            scale_name = metric_name[len(survey_code) + 1:].lower()
        elif survey_code and metric_name.upper() == survey_code:
            # Escala única: metric_name es exactamente el código → usar 'total'
            scale_name = 'total'
        else:
            scale_name = None

        Baremo = self.env['aula_metrics.survey_baremo_range']
        baremos = Baremo.browse()
        if scale_name:
            baremos = Baremo.search([
                ('survey_id', '=', survey.id),
                ('scale_name', '=', scale_name),
            ])
        if not baremos:
            # Fallback: cualquier baremo del cuestionario
            baremos = Baremo.search([('survey_id', '=', survey.id)])

        if baremos:
            return (min(baremos.mapped('score_min')), max(baremos.mapped('score_max')))

        data_max = df_metric['value_numeric'].dropna().max()
        y_max = round(float(data_max) * 1.1, 1) if pd.notna(data_max) else 100
        return (0, y_max)

    def _generate_chart_by_metric_type(self, metric_info, df, role_info, segmentation_vars):
        """Genera el gráfico apropiado según el tipo de métrica y rol."""
        metric_name = metric_info['name']
        metric_label = metric_info['label']
        metric_type = metric_info['type']

        df_metric = df[df['metric_name'] == metric_name].copy()
        y_min, y_max = self._get_y_range_for_metric(df_metric)

        if metric_type == 'numeric':
            return self._chart_numeric_metric(df_metric, metric_label, role_info, segmentation_vars, y_max, y_min)
        elif metric_type == 'json':
            return ''
        return ''

    def _chart_multi_scale_survey(self, df_survey, role_info, segmentation_vars):
        """Una única card que reúne total + sub-escalas mediante tabs/pills.

        Estructura: card con pills en el header; cada pill pane contiene
        el gráfico de esa escala (con sus propios controles: segmentación,
        toggle barra/línea si hay evolución). Los bordes de las cards
        internas se aplanan por CSS para dar sensación de card única.
        Escalable: funciona con cualquier número de sub-escalas.
        """
        survey_id_val = df_survey['survey_id'].dropna().iloc[0]
        survey = self.env['survey.survey'].browse(int(survey_id_val))
        survey_title = survey.title if survey.exists() else 'Cuestionario'
        survey_code  = (getattr(survey, 'survey_code', '') or '').upper()

        numeric_df   = df_survey[df_survey['metric_type'] == 'numeric']
        metric_names = numeric_df['metric_name'].unique().tolist()

        def is_primary(mn):
            if survey_code:
                return mn.upper() == f'{survey_code}_TOTAL'
            return 'total' in mn.lower() or 'global' in mn.lower()

        primary_names   = [m for m in metric_names if     is_primary(m)]
        secondary_names = [m for m in metric_names if not is_primary(m)]
        if not primary_names:
            primary_names, secondary_names = metric_names[:1], metric_names[1:]

        role = role_info.get('role', 'counselor')

        # Construir lista ordenada: escala total primero, luego sub-escalas
        # Separar by_html y evo_html para poder gestionar el toggle globalmente
        ordered_scales = []
        any_evolution  = False
        for mn in primary_names[:1] + secondary_names:
            df_scale = df_survey[df_survey['metric_name'] == mn].copy()
            if df_scale.empty:
                continue
            label = df_scale['metric_label'].iloc[0]
            y_min, y_max = self._get_y_range_for_metric(df_scale)

            evaluations   = df_scale['evaluation_name'].dropna().unique()
            has_evolution = len(evaluations) >= 2
            if has_evolution:
                any_evolution = True

            if role == ROLE_MANAGEMENT:
                by_html  = self._chart_numeric_by_course(df_scale, label, segmentation_vars, y_max, y_min)
                evo_html = self._chart_numeric_evolution_by_course(df_scale, label, y_max, y_min) if has_evolution else ''
            elif role == ROLE_TUTOR:
                by_html  = self._chart_numeric_distribution(df_scale, label, segmentation_vars, y_max, y_min)
                evo_html = ''
            else:  # counselor/admin
                by_html  = self._chart_numeric_by_groups(df_scale, label, segmentation_vars, y_max, y_min)
                evo_html = self._chart_numeric_evolution_by_groups(df_scale, label, y_max, y_min) if has_evolution else ''

            if by_html or evo_html:
                ordered_scales.append((mn, label, by_html, evo_html))

        if not ordered_scales:
            return ''

        group_id   = dashboard_helpers.sanitize_id(survey_code or survey_title)
        toggle_id  = f'toggle_{group_id}'
        nav_items  = []
        tab_panes  = []

        for i, (mn, label, by_html, evo_html) in enumerate(ordered_scales):
            tab_id   = f'scale-{group_id}-{i}'
            is_first = (i == 0)
            bold     = ' fw-semibold' if is_first else ''
            active   = ' am-tab-active' if is_first else ''
            visible  = '' if is_first else 'display:none;'

            nav_items.append(
                f'<li class="nav-item">'
                f'<button class="nav-link{bold}{active}" type="button" '
                f'data-am-tab="{tab_id}" data-am-group="{group_id}">'
                f'{label}</button></li>'
            )
            evo_div = (f'<div class="am-tab-evo" style="display:none;">{evo_html}</div>'
                       if evo_html else '')
            tab_panes.append(
                f'<div class="am-tab-pane" id="{tab_id}" style="{visible}">'
                f'<div class="am-tab-comparativa">{by_html}</div>'
                f'{evo_div}'
                f'</div>'
            )

        nav_html   = '\n'.join(nav_items)
        panes_html = '\n'.join(tab_panes)

        # Toggle global en el header (igual que en tarjetas de métrica única)
        toggle_html = ''
        if any_evolution:
            toggle_html = f'''
            <div class="am-view-toggle" role="group" aria-label="Tipo de vista">
                <button id="{toggle_id}_bars" class="am-vtoggle-btn am-vtoggle-btn--active">
                    <i class="fa-solid fa-chart-bar"></i><span>Comparativa</span>
                </button>
                <button id="{toggle_id}_lines" class="am-vtoggle-btn">
                    <i class="fa-solid fa-chart-line"></i><span>Evolución</span>
                </button>
            </div>'''

        return f"""
    <div class="card survey-unified-card" id="survey-card-{group_id}">
        <div class="card-header">
            <div style="display:flex; justify-content:space-between; align-items:center; gap:12px; margin-bottom:10px;">
                <h5 class="card-title" style="margin:0;">{survey_title}</h5>
                {toggle_html}
            </div>
            <ul class="nav survey-scale-tabs">
                {nav_html}
            </ul>
        </div>
        <div class="am-tab-content">
            {panes_html}
        </div>
    </div>
    <script>
    (function() {{
        const card = document.getElementById('survey-card-{group_id}');
        if (!card) return;

        // ── Toggle comparativa / evolución (global para todas las escalas) ──
        const btnBars  = document.getElementById('{toggle_id}_bars');
        const btnLines = document.getElementById('{toggle_id}_lines');
        if (btnBars && btnLines) {{
            function setSurveyView(showEvo) {{
                btnBars.classList.toggle('am-vtoggle-btn--active', !showEvo);
                btnLines.classList.toggle('am-vtoggle-btn--active', showEvo);
                card.querySelectorAll('.am-tab-comparativa').forEach(function(d) {{
                    d.style.display = showEvo ? 'none' : '';
                }});
                card.querySelectorAll('.am-tab-evo').forEach(function(d) {{
                    d.style.display = showEvo ? '' : 'none';
                }});
                // Resize charts in the currently visible pane
                card.querySelectorAll('.am-tab-pane').forEach(function(p) {{
                    if (p.style.display === 'none') return;
                    p.querySelectorAll('canvas').forEach(function(c) {{
                        const ch = Chart.getChart(c.id);
                        if (ch) {{ ch.resize(); ch.update(); }}
                    }});
                }});
            }}
            btnBars.addEventListener('click', function() {{ setSurveyView(false); }});
            btnLines.addEventListener('click', function() {{ setSurveyView(true); }});
        }}

        // ── Tab switching ──
        card.querySelectorAll('[data-am-tab]').forEach(function(btn) {{
            btn.addEventListener('click', function(e) {{
                e.preventDefault();
                e.stopPropagation();
                const savedY   = window.scrollY;
                const targetId = btn.getAttribute('data-am-tab');
                const group    = btn.getAttribute('data-am-group');
                card.querySelectorAll('[data-am-group="' + group + '"]').forEach(function(b) {{
                    b.classList.remove('am-tab-active');
                }});
                card.querySelectorAll('.am-tab-pane').forEach(function(p) {{
                    p.style.display = 'none';
                }});
                btn.classList.add('am-tab-active');
                const pane = document.getElementById(targetId);
                if (pane) {{
                    pane.style.display = '';
                    pane.querySelectorAll('canvas').forEach(function(c) {{
                        const ch = Chart.getChart(c.id);
                        if (ch) {{ ch.resize(); ch.update(); }}
                    }});
                }}
                window.scrollTo({{ top: savedY, behavior: 'instant' }});
            }});
        }});
    }})();
    </script>"""

    def _chart_numeric_metric(self, df, label, role_info, segmentation_vars, y_max=100, y_min=0):
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
            by_courses_html = self._chart_numeric_by_course(df, label, segmentation_vars, y_max, y_min)
            evo_html = self._chart_numeric_evolution_by_course(df, label, y_max, y_min) if has_evolution else ''

            if by_courses_html and evo_html:
                charts_html += self._chart_numeric_with_toggle(by_courses_html, evo_html, label, 'curso')
            else:
                charts_html += by_courses_html or evo_html

        elif role == ROLE_TUTOR:
            charts_html += self._chart_numeric_distribution(df, label, segmentation_vars, y_max, y_min)
            if has_evolution:
                charts_html += self._chart_numeric_evolution_distribution(df, label, y_max, y_min)
        else:  # counselor/admin
            by_groups_html = self._chart_numeric_by_groups(df, label, segmentation_vars, y_max, y_min)
            evo_html = self._chart_numeric_evolution_by_groups(df, label, y_max, y_min) if has_evolution else ''

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
                </div>
                <div class="am-view-toggle" role="group" aria-label="Tipo de vista">
                    <button id="__TOGGLE_ID___bars" class="am-vtoggle-btn am-vtoggle-btn--active">
                        <i class="fa-solid fa-chart-bar"></i>
                        <span>Comparativa</span>
                    </button>
                    <button id="__TOGGLE_ID___lines" class="am-vtoggle-btn">
                        <i class="fa-solid fa-chart-line"></i>
                        <span>Evolución</span>
                    </button>
                </div>
            </div>
            <div class="card-body" style="padding:0;">
                <div id="__WRAP_BY__">__BY_HTML__</div>
                <div id="__WRAP_EVO__" style="display:none;">__EVO_HTML__</div>
            </div>
        </div>

        <style>
        /* Ocultar solo título/subtítulo de las cards embebidas — los controles permanecen visibles */
        #__WRAP_EVO__ .card-header, #__WRAP_BY__ .card-header { border-bottom: none; padding-bottom: 0; }
        #__WRAP_EVO__ .card-header .am-card-header__info, #__WRAP_BY__ .card-header .am-card-header__info { display: none; }
        /* Quitar borde/sombra de las cards anidadas para que se vean como contenido plano */
        #__WRAP_BY__ > .card, #__WRAP_EVO__ > .card { border: none; border-radius: 0; box-shadow: none; }
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
                btnBars.classList.toggle('am-vtoggle-btn--active', !showEvo);
                btnLines.classList.toggle('am-vtoggle-btn--active', showEvo);

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
            setView(false);
        })();
        </script>
        '''
        return html.replace('__TOGGLE_ID__', toggle_id).replace('__WRAP_BY__', wrapper_by).replace('__WRAP_EVO__', wrapper_evo).replace('__LABEL__', label).replace('__SUBTITLE__', subtitle).replace('__BY_HTML__', by_groups_html).replace('__EVO_HTML__', evo_html)

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
    
