# -*- coding: utf-8 -*-
"""
Dashboard Charts - Generación de dashboard con métricas filtradas
"""
from odoo import models, api, fields
import pandas as pd
import json

# Importar utilidades compartidas
from ..utils import dashboard_styles, dashboard_layout, dashboard_helpers

class DashboardCharts(models.TransientModel):
    _name = 'aulametrics.dashboard.charts'
    _description = 'Generador de Dashboard de Métricas'

    @api.model
    def generate_dashboard(self, filters=None, role_info=None):
        """
        Genera el dashboard de métricas con filtros dinámicos.
        
        Args:
            filters (dict): Filtros aplicados {evaluation_ids}
            role_info (dict): Información de rol del usuario
        
        Returns:
            str: HTML completo del dashboard
        """
        if filters is None:
            filters = {}
        if role_info is None:
            role_info = {'role': 'admin', 'anonymize_students': False}

        # Obtener opciones disponibles para los filtros
        available_metrics = self._get_available_metrics(filters, role_info)
        available_groups = self._get_available_groups(filters, role_info)
        available_evaluations = self._get_available_evaluations(role_info)
        segmentation_vars = self._get_segmentation_variables(filters, role_info)

        # Si no hay datos disponibles, mostrar mensaje
        if not available_metrics:
            return self._build_html_empty(
                available_metrics, available_groups, available_evaluations, 
                filters, role_info
            )

        # Consultar valores de métricas según filtros
        metric_values = self._query_metric_values(filters, role_info)
        
        if not metric_values:
            return self._build_html_empty(
                available_metrics, available_groups, available_evaluations,
                filters, role_info
            )

        # Preparar DataFrame
        df = self._prepare_dataframe(metric_values, role_info)
        
        # Generar gráficos
        charts = self._generate_charts(df, filters, available_metrics, role_info, segmentation_vars)
        
        # Generar KPIs
        kpi_html = self._generate_kpis(df, filters, role_info)
        
        # Construir HTML final
        return self._build_html(
            available_metrics, available_groups, available_evaluations, 
            filters, role_info, kpi_html, charts, segmentation_vars
        )

    def _get_available_metrics(self, filters, role_info):
        """Obtiene las métricas únicas disponibles en metric_value."""
        MetricValue = self.env['aulametrics.metric_value']
        
        # Dominio base
        domain = []
        
        # Filtrar por grupos si rol tutor
        if role_info.get('role') == 'tutor':
            allowed_groups = role_info.get('allowed_group_ids', [])
            if allowed_groups:
                domain.append(('academic_group_id', 'in', allowed_groups))
            else:
                return []  # Tutor sin grupos asignados
        
        # Filtrar por evaluaciones si se especifica
        if filters.get('evaluation_ids'):
            domain.append(('evaluation_id', 'in', filters['evaluation_ids']))
        
        # Agrupar por metric_name y obtener labels
        result = MetricValue.read_group(
            domain,
            ['metric_name', 'metric_label'],
            ['metric_name']
        )
        
        # Obtener labels únicos y detectar tipo
        metrics = []
        seen = set()
        for r in result:
            name = r['metric_name']
            if name not in seen:
                seen.add(name)
                # Buscar un registro con datos para obtener el label y detectar tipo
                # Priorizar registros que realmente tienen valores
                sample = MetricValue.search([
                    ('metric_name', '=', name),
                    '|', '|',
                    ('value_float', '!=', False),
                    ('value_json', '!=', False),
                    ('value_text', '!=', False)
                ] + domain, limit=1)
                
                # Si no hay registro con datos, buscar cualquiera
                if not sample:
                    sample = MetricValue.search([
                        ('metric_name', '=', name)
                    ] + domain, limit=1)
                
                if not sample:
                    continue
                
                # Detectar tipo según qué campo tiene valor
                if sample.value_float:
                    metric_type = 'numeric'
                elif sample.value_json:
                    metric_type = 'json'
                elif sample.value_text:
                    metric_type = 'text'
                else:
                    continue  # Saltar si no tiene ningún valor
                
                metrics.append({
                    'name': name,
                    'label': sample.metric_label or name,
                    'type': metric_type
                })
        
        return sorted(metrics, key=lambda x: x['label'])

    def _get_available_groups(self, filters, role_info):
        """Obtiene los grupos académicos derivados de las evaluaciones filtradas según el rol.
        
        Los grupos se derivan automáticamente de las evaluaciones seleccionadas,
        mostrando solo aquellos que tienen participación en dichas evaluaciones.
        """
        AcademicGroup = self.env['aulametrics.academic_group']
        MetricValue = self.env['aulametrics.metric_value']
        
        # Si hay evaluaciones filtradas, derivar grupos desde ellas
        if filters.get('evaluation_ids'):
            # Buscar grupos únicos que participan en las evaluaciones filtradas
            domain = [('evaluation_id', 'in', filters['evaluation_ids'])]
            
            # Aplicar restricciones de rol
            if role_info.get('role') == 'tutor':
                allowed = role_info.get('allowed_group_ids', [])
                if allowed:
                    domain.append(('academic_group_id', 'in', allowed))
                else:
                    return []  # Tutor sin grupos asignados
            
            # Obtener IDs de grupos con participación
            group_ids = MetricValue.search(domain).mapped('academic_group_id').ids
            groups = AcademicGroup.browse(list(set(group_ids)))
        else:
            # Sin filtro de evaluaciones, mostrar todos los grupos permitidos
            if role_info.get('role') == 'tutor':
                allowed = role_info.get('allowed_group_ids', [])
                groups = AcademicGroup.browse(allowed)
            else:
                groups = AcademicGroup.search([])
        
        return [{'id': g.id, 'name': g.name, 'course': g.course_level, 'student_count': g.student_count} for g in groups]

    def _get_available_evaluations(self, role_info):
        """Obtiene las evaluaciones disponibles según el rol."""
        Evaluation = self.env['aulametrics.evaluation']
        
        # Las record rules ya aplican filtros, simplemente buscamos todas
        evaluations = Evaluation.search([], order='date_start desc')
        
        return [{'id': e.id, 'name': e.name, 'state': e.state, 'date_start': e.date_start} for e in evaluations]

    def _get_segmentation_variables(self, filters, role_info):
        """Obtiene variables de segmentación disponibles dinámicamente.
        
        Args:
            filters (dict): Filtros actuales aplicados
            role_info (dict): Información del rol del usuario
        
        Returns:
            list: Lista de dicts con estructura {value, label, type, options}
                - value: identificador ('gender' o 'question_123_choices')
                - label: nombre legible para mostrar
                - type: 'partner_field' o 'metric_json'
                - options: lista de valores posibles ['Masculino', 'Femenino', ...]
        """
        variables = []
        
        # 1. Género (siempre disponible desde res.partner)
        variables.append({
            'value': 'gender',
            'label': 'Género',
            'type': 'partner_field',
            'options': ['Masculino', 'Femenino', 'Otro', 'Prefiere no decir']
        })
        
        # 2. Preguntas de opciones múltiples (dinámicas desde metric_value)
        MetricValue = self.env['aulametrics.metric_value']
        SurveyQuestion = self.env['survey.question'].sudo()  # sudo() para lectura de metadatos de encuestas
        
        # Dominio base respetando permisos de rol
        domain = [('metric_name', 'like', 'question_%_choices')]
        
        if role_info.get('role') == 'tutor':
            allowed_groups = role_info.get('allowed_group_ids', [])
            if allowed_groups:
                domain.append(('academic_group_id', 'in', allowed_groups))
            else:
                return variables  # Solo retorna género si tutor sin grupos
        
        # NO aplicar filtros de evaluaciones/fechas para obtener TODAS las métricas JSON históricas
        # Esto permite segmentación completa independientemente de los filtros aplicados
        
        # Buscar TODAS las métricas JSON históricas (sin filtrar por evaluaciones)
        # para proporcionar segmentación completa independientemente de los filtros
        result = MetricValue.read_group(
            domain,
            ['metric_name'],
            ['metric_name']
        )
        
        for r in result:
            metric_name = r['metric_name']
            
            # Extraer question_id del patrón 'question_{id}_choices'
            try:
                question_id = int(metric_name.split('_')[1])
            except (IndexError, ValueError):
                continue
            
            # Obtener pregunta para nombre legible
            question = SurveyQuestion.browse(question_id).exists()
            if not question:
                continue
            
            # Extraer opciones únicas de todos los registros
            all_records = MetricValue.search([
                ('metric_name', '=', metric_name),
                ('value_json', '!=', False)
            ] + domain)
            
            options_set = set()
            for record in all_records:
                if record.value_json:
                    options_set.update(record.value_json)
            
            if options_set:
                variables.append({
                    'value': metric_name,
                    'label': question.metric_label,
                    'type': 'metric_json',
                    'options': sorted(list(options_set))
                })
        
        return variables

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

    def _query_metric_values(self, filters, role_info):
        """Consulta los valores de métricas. Las métricas y grupos se derivan automáticamente de las evaluaciones."""
        MetricValue = self.env['aulametrics.metric_value']
        
        domain = []
        
        # Filtro por evaluaciones (filtro maestro)
        if filters.get('evaluation_ids'):
            domain.append(('evaluation_id', 'in', filters['evaluation_ids']))
        
        # Restricciones de rol: Tutores ven solo sus grupos asignados
        if role_info.get('role') == 'tutor':
            allowed_groups = role_info.get('allowed_group_ids', [])
            if allowed_groups:
                domain.append(('academic_group_id', 'in', allowed_groups))
            else:
                # Si no tiene grupos, no ve nada
                return self.env['aulametrics.metric_value']
        
        return MetricValue.search(domain)

    def _prepare_dataframe(self, metric_values, role_info):
        """Convierte metric_values a un DataFrame de pandas para análisis."""
        data = []
        
        anonymize = role_info.get('anonymize_students', False)
        
        for mv in metric_values:
            student = mv.student_id
            academic_group = mv.academic_group_id
            evaluation = mv.evaluation_id
            
            # Datos del estudiante
            student_name = "Anónimo" if anonymize else student.name
            student_id_val = "***" if anonymize else str(student.id)
            
            # Detectar tipo de métrica según qué campo tiene valor
            if mv.value_float:
                metric_type = 'numeric'
                value_numeric = mv.value_float
                value_json = None
                value_text = None
            elif mv.value_json:
                metric_type = 'json'
                value_numeric = None
                value_json = mv.value_json
                value_text = None
            elif mv.value_text:
                metric_type = 'text'
                value_numeric = None
                value_json = None
                value_text = mv.value_text
            else:
                continue  # Saltar si no tiene ningún valor
            
            row = {
                'metric_name': mv.metric_name,
                'metric_label': mv.metric_label,
                'metric_type': metric_type,
                'value_numeric': value_numeric,
                'value_json': value_json,
                'value_text': value_text,
                'student_id': student_id_val,
                'student_name': student_name,
                'student_gender': student.gender if student.gender else 'Otro',
                'group_id': academic_group.id if academic_group else None,
                'group_name': academic_group.name if academic_group else 'Sin grupo',
                'curso': academic_group.course_level if academic_group and academic_group.course_level else 'Sin curso',
                'evaluation_id': evaluation.id if evaluation else None,
                'evaluation_name': evaluation.name if evaluation else 'Sin evaluación',
                'completed_at': mv.timestamp,
            }
            data.append(row)
        
        return pd.DataFrame(data)

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
        if role == 'management':
            # Management usa la misma UI que counselor pero con datos por curso
            by_courses_html = self._chart_numeric_by_course(df, label, segmentation_vars)
            evo_html = self._chart_numeric_evolution_by_course(df, label) if has_evolution else ''
            
            if by_courses_html and evo_html:
                charts_html += self._chart_numeric_with_toggle(by_courses_html, evo_html, label, 'curso')
            else:
                charts_html += by_courses_html or evo_html
                
        elif role == 'tutor':
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
        Threshold = self.env['aulametrics.threshold']
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
    
    def _chart_numeric_evolution_by_course(self, df, label):
        """Evolución temporal de la métrica por curso (Management)."""
        # Agrupar por evaluación (no por timestamp individual)
        evaluations = df.groupby('evaluation_name')['completed_at'].min().sort_values()
        
        if len(evaluations) < 2:
            return ''
        
        cursos = sorted(df['curso'].unique())
        color_palette = ['#3b82f6', '#10b981', '#f59e0b', '#8b5cf6', '#ec4899', '#06b6d4', '#f97316', '#84cc16']
        
        # Preparar datasets por curso
        datasets = []
        for idx, curso in enumerate(cursos):
            df_curso = df[df['curso'] == curso]
            data_points = []
            
            for eval_name, eval_date in evaluations.items():
                df_eval = df_curso[df_curso['evaluation_name'] == eval_name]['value_numeric'].dropna()
                if len(df_eval) > 0:
                    data_points.append({
                        'x': eval_date.isoformat() if hasattr(eval_date, 'isoformat') else str(eval_date),
                        'y': float(df_eval.mean())
                    })
            
            if data_points:
                datasets.append({
                    'label': curso,
                    'data': data_points,
                    'borderColor': color_palette[idx % len(color_palette)],
                    'backgroundColor': color_palette[idx % len(color_palette)] + '20',
                    'tension': 0.3
                })
        
        if not datasets:
            return ''
        
        chart_id = f'evolution_{label.replace(" ", "_").replace("/", "_").replace(".", "_")}'
        
        return f'''
        <div class="card">
            <div class="card-header">
                <h5 class="card-title">Evolución: {label}</h5>
                <p class="card-subtitle">Tendencia temporal por curso académico</p>
            </div>
            <div class="card-body">
                <canvas id="{chart_id}" height="260"></canvas>
            </div>
        </div>
        
        <script>
        new Chart(document.getElementById('{chart_id}'), {{
            type: 'line',
            data: {{
                datasets: {json.dumps(datasets)}
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: true,
                plugins: {{
                    legend: {{
                        display: true,
                        position: 'top',
                        labels: {{
                            usePointStyle: true,
                            padding: 10,
                            font: {{ size: 10, family: "'Inter', sans-serif" }},
                            color: '#64748b',
                            boxWidth: 8
                        }}
                    }},
                    tooltip: {{
                        backgroundColor: '#1e293b',
                        padding: 12,
                        cornerRadius: 6,
                        titleFont: {{ family: "'Inter', sans-serif", size: 13, weight: '600' }},
                        bodyFont: {{ family: "'Inter', sans-serif", size: 12 }},
                        callbacks: {{
                            title: function(context) {{
                                return new Date(context[0].parsed.x).toLocaleDateString('es-ES');
                            }},
                            label: function(context) {{
                                return context.dataset.label + ': ' + context.parsed.y.toFixed(1) + ' pts';
                            }}
                        }}
                    }}
                }},
                scales: {{
                    x: {{
                        type: 'time',
                        time: {{
                            unit: 'day',
                            displayFormats: {{
                                day: 'dd/MM/yyyy'
                            }}
                        }},
                        grid: {{ display: false, drawBorder: false }},
                        ticks: {{
                            font: {{ size: 11, family: "'Inter', sans-serif" }},
                            color: '#64748b'
                        }}
                    }},
                    y: {{
                        beginAtZero: true,
                        max: 100,
                        grid: {{ color: '#f1f5f9', drawBorder: false }},
                        ticks: {{
                            font: {{ size: 11, family: "'Inter', sans-serif" }},
                            color: '#94a3b8'
                        }}
                    }}
                }}
            }}
        }});
        </script>
        '''
    
    def _chart_numeric_evolution_distribution(self, df, label):
        """Evolución temporal: trayectorias individuales + media del grupo (Tutor - anónimo)."""
        # Agrupar por evaluación (no por timestamp individual)
        evaluations = df.groupby('evaluation_name')['completed_at'].min().sort_values()
        
        if len(evaluations) < 2:
            return ''
        
        # Dataset 1: Media del grupo en cada evaluación
        group_data_points = []
        for eval_name, eval_date in evaluations.items():
            df_eval = df[df['evaluation_name'] == eval_name]['value_numeric'].dropna()
            if len(df_eval) > 0:
                group_data_points.append({
                    'x': eval_date.isoformat() if hasattr(eval_date, 'isoformat') else str(eval_date),
                    'y': float(df_eval.mean())
                })
        
        if not group_data_points:
            return ''
        
        # Dataset 2: Trayectorias individuales de cada alumno (anonimizado)
        individual_datasets = []
        students = df['student_id'].unique()
        total_students = len(students)
        
        for idx, student_id in enumerate(students, 1):
            df_student = df[df['student_id'] == student_id]
            student_data_points = []
            
            for eval_name, eval_date in evaluations.items():
                df_student_eval = df_student[df_student['evaluation_name'] == eval_name]['value_numeric'].dropna()
                if len(df_student_eval) > 0:
                    student_data_points.append({
                        'x': eval_date.isoformat() if hasattr(eval_date, 'isoformat') else str(eval_date),
                        'y': float(df_student_eval.iloc[0])
                    })
            
            # Solo agregar si tiene al menos 2 puntos temporales
            if len(student_data_points) >= 2:
                # Generar color único para cada alumno usando HSL
                hue = (idx * 360 / total_students) % 360
                individual_datasets.append({
                    'label': f'Alumno {idx}',
                    'data': student_data_points,
                    'borderColor': f'hsl({hue}, 70%, 55%)',
                    'backgroundColor': 'transparent',
                    'borderWidth': 2,
                    'tension': 0.2,
                    'pointRadius': 3,
                    'pointHoverRadius': 5,
                    'pointBackgroundColor': f'hsl({hue}, 70%, 55%)',
                    'pointBorderColor': '#ffffff',
                    'pointBorderWidth': 1
                })
        
        # Dataset de media grupal (destacado con línea negra gruesa)
        group_dataset = {
            'label': 'Media del grupo',
            'data': group_data_points,
            'borderColor': '#1e293b',
            'backgroundColor': '#1e293b20',
            'borderWidth': 4,
            'borderDash': [],
            'tension': 0.3,
            'fill': True,
            'pointRadius': 5,
            'pointHoverRadius': 7,
            'pointBackgroundColor': '#1e293b',
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
                <canvas id="{chart_id}" height="260"></canvas>
            </div>
        </div>
        
        <script>
        new Chart(document.getElementById('{chart_id}'), {{
            type: 'line',
            data: {{
                datasets: {json.dumps(all_datasets)}
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: true,
                plugins: {{
                    legend: {{ 
                        display: true,
                        position: 'top',
                        labels: {{
                            usePointStyle: true,
                            padding: 10,
                            font: {{ size: 10, family: "'Inter', sans-serif" }},
                            color: '#64748b',
                            boxWidth: 8
                        }}
                    }},
                    tooltip: {{
                        backgroundColor: '#1e293b',
                        padding: 12,
                        cornerRadius: 6,
                        titleFont: {{ family: "'Inter', sans-serif", size: 13, weight: '600' }},
                        bodyFont: {{ family: "'Inter', sans-serif", size: 12 }},
                        callbacks: {{
                            title: function(context) {{
                                return new Date(context[0].parsed.x).toLocaleDateString('es-ES');
                            }},
                            label: function(context) {{
                                if (context.dataset.label === 'Media del grupo') {{
                                    return 'Media: ' + context.parsed.y.toFixed(1) + ' pts';
                                }} else {{
                                    return context.dataset.label + ': ' + context.parsed.y.toFixed(1) + ' pts';
                                }}
                            }}
                        }}
                    }}
                }},
                interaction: {{
                    mode: 'nearest',
                    axis: 'x',
                    intersect: false
                }},
                scales: {{
                    x: {{
                        type: 'time',
                        time: {{
                            unit: 'day',
                            displayFormats: {{
                                day: 'dd/MM/yyyy'
                            }}
                        }},
                        grid: {{ display: false, drawBorder: false }},
                        ticks: {{
                            font: {{ size: 11, family: "'Inter', sans-serif" }},
                            color: '#64748b'
                        }}
                    }},
                    y: {{
                        beginAtZero: true,
                        max: 100,
                        grid: {{ color: '#f1f5f9', drawBorder: false }},
                        ticks: {{
                            font: {{ size: 11, family: "'Inter', sans-serif" }},
                            color: '#94a3b8'
                        }}
                    }}
                }}
            }}
        }});
        </script>
        '''
    
    def _chart_numeric_evolution_by_groups(self, df, label):
        """Evolución temporal de la métrica por grupo (Counselor)."""
        # Agrupar por evaluación (no por timestamp individual)
        evaluations = df.groupby('evaluation_name')['completed_at'].min().sort_values()
        
        if len(evaluations) < 2:
            return ''
        
        grupos = sorted(df['group_name'].unique())
        color_palette = ['#3b82f6', '#10b981', '#f59e0b', '#8b5cf6', '#ec4899', '#06b6d4', '#f97316', '#84cc16', '#f43f5e', '#14b8a6']
        
        # Preparar datasets por grupo
        datasets = []
        for idx, grupo in enumerate(grupos):
            df_grupo = df[df['group_name'] == grupo]
            data_points = []
            
            for eval_name, eval_date in evaluations.items():
                df_eval = df_grupo[df_grupo['evaluation_name'] == eval_name]['value_numeric'].dropna()
                if len(df_eval) > 0:
                    data_points.append({
                        'x': eval_date.isoformat() if hasattr(eval_date, 'isoformat') else str(eval_date),
                        'y': float(df_eval.mean())
                    })
            
            if data_points:
                datasets.append({
                    'label': grupo,
                    'data': data_points,
                    'borderColor': color_palette[idx % len(color_palette)],
                    'backgroundColor': color_palette[idx % len(color_palette)] + '20',
                    'tension': 0.3
                })
        
        if not datasets:
            return ''
        
        chart_id = f'evolution_{label.replace(" ", "_").replace("/", "_").replace(".", "_")}'
        
        return f'''
        <div class="card">
            <div class="card-header">
                <h5 class="card-title">Evolución: {label}</h5>
                <p class="card-subtitle">Tendencia temporal por grupo</p>
            </div>
            <div class="card-body">
                <canvas id="{chart_id}" height="260"></canvas>
            </div>
        </div>
        
        <script>
        new Chart(document.getElementById('{chart_id}'), {{
            type: 'line',
            data: {{
                datasets: {json.dumps(datasets)}
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: true,
                plugins: {{
                    legend: {{
                        display: true,
                        position: 'top',
                        labels: {{
                            usePointStyle: true,
                            padding: 10,
                            font: {{ size: 10, family: "'Inter', sans-serif" }},
                            color: '#64748b',
                            boxWidth: 8
                        }}
                    }},
                    tooltip: {{
                        backgroundColor: '#1e293b',
                        padding: 12,
                        cornerRadius: 6,
                        titleFont: {{ family: "'Inter', sans-serif", size: 13, weight: '600' }},
                        bodyFont: {{ family: "'Inter', sans-serif", size: 12 }},
                        callbacks: {{
                            title: function(context) {{
                                return new Date(context[0].parsed.x).toLocaleDateString('es-ES');
                            }},
                            label: function(context) {{
                                return context.dataset.label + ': ' + context.parsed.y.toFixed(1) + ' pts';
                            }}
                        }}
                    }}
                }},
                scales: {{
                    x: {{
                        type: 'time',
                        time: {{
                            unit: 'day',
                            displayFormats: {{
                                day: 'dd/MM/yyyy'
                            }}
                        }},
                        grid: {{ display: false, drawBorder: false }},
                        ticks: {{
                            font: {{ size: 11, family: "'Inter', sans-serif" }},
                            color: '#64748b'
                        }}
                    }},
                    y: {{
                        beginAtZero: true,
                        max: 100,
                        grid: {{ color: '#f1f5f9', drawBorder: false }},
                        ticks: {{
                            font: {{ size: 11, family: "'Inter', sans-serif" }},
                            color: '#94a3b8'
                        }}
                    }}
                }}
            }}
        }});
        </script>
        '''
    
    def _chart_numeric_by_course(self, df, label, segmentation_vars):
        """Vista Management: Agregado por curso académico (barras compactas)."""
        cursos = sorted(df['curso'].unique())
        stats = []
        
        # Paleta de colores consistente para cursos
        color_palette = ['#3b82f6', '#10b981', '#f59e0b', '#8b5cf6', '#ec4899', '#06b6d4', '#f97316', '#84cc16']
        
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
        MetricValue = self.env['aulametrics.metric_value']
        
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
                    <button id="sort_{chart_id}" style="padding: 6px 12px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; cursor: pointer; font-size: 12px; color: #475569; font-weight: 500; transition: all 0.2s;" onmouseover="this.style.background='#f1f5f9'" onmouseout="this.style.background='#f8fafc'">
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
        bin_colors = ['#3b82f6', '#60a5fa', '#fb923c', '#f97316']
        
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
        MetricValue = self.env['aulametrics.metric_value']
        
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
        color_palette = ['#3b82f6', '#10b981', '#f59e0b', '#8b5cf6', '#ec4899', '#06b6d4', '#f97316', '#84cc16', '#f43f5e', '#14b8a6']
        
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
        MetricValue = self.env['aulametrics.metric_value']
        
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
                    <button id="sort_{chart_id}" style="padding: 6px 12px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; cursor: pointer; font-size: 12px; color: #475569; font-weight: 500; transition: all 0.2s;" onmouseover="this.style.background='#f1f5f9'" onmouseout="this.style.background='#f8fafc'">
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

    def _generate_kpis(self, df, filters, role_info):
        """Genera tarjetas KPI con diseño profesional."""
        kpis = []
        
        # Total de estudiantes
        total_students = df['student_id'].nunique()
        kpis.append(f"""
        <div class="kpi-card">
            <div class="kpi-label">Estudiantes</div>
            <div class="kpi-value">{total_students}</div>
            <div class="kpi-description">Total analizados</div>
        </div>
        """)
        
        # Total de grupos
        total_groups = df['group_id'].nunique()
        kpis.append(f"""
        <div class="kpi-card">
            <div class="kpi-label">Grupos</div>
            <div class="kpi-value">{total_groups}</div>
            <div class="kpi-description">Académicos</div>
        </div>
        """)
        
        # Total de evaluaciones
        total_evals = df['evaluation_id'].nunique()
        kpis.append(f"""
        <div class="kpi-card">
            <div class="kpi-label">Evaluaciones</div>
            <div class="kpi-value">{total_evals}</div>
            <div class="kpi-description">Completadas</div>
        </div>
        """)
        
        # Total de métricas
        total_metrics = len(df)
        kpis.append(f"""
        <div class="kpi-card">
            <div class="kpi-label">Métricas</div>
            <div class="kpi-value">{total_metrics}</div>
            <div class="kpi-description">Registradas</div>
        </div>
        """)
        
        return '\n'.join(kpis)

    def _build_html_empty(self, metrics, groups, evaluations, filters, role_info):
        """HTML cuando no hay datos disponibles."""
        # Usar utilidades compartidas
        role_badge = dashboard_helpers.get_role_badge(role_info)
        filter_controls = self._build_filter_controls(metrics, groups, evaluations, filters)
        sidebar_html = dashboard_layout.get_sidebar(role_info, active_section='home')
        
        # Topbar con fecha
        date_str = dashboard_helpers.format_date(fields.Date.today())
        topbar_html = dashboard_layout.get_topbar(
            title='Inicio',
            subtitle=f'<i class="fa-regular fa-calendar me-2"></i>{date_str}',
            role_badge=role_badge
        )
        
        home_html = self._home_section(metrics, groups, evaluations, filters, role_info)
        
        # Construir contenido de las secciones
        content = f"""
            <!-- Sección Home -->
            <div class="content-section active" id="section-home">
                {home_html}
            </div>
            
            <!-- Sección Datos Cuantitativos -->
            <div class="content-section" id="section-quantitative">
                <div class="container-fluid">
                    {filter_controls}
                    {dashboard_layout.get_empty_state('chart-line', 'No hay datos disponibles', 'Ajusta los filtros para ver resultados')}
                </div>
            </div>
            
            <!-- Sección Datos Cualitativos -->
            <div class="content-section" id="section-qualitative">
                <div id="qualitativeContent">
                    <div style="text-align: center; padding: 60px 20px;">
                        <i class="fa-solid fa-spinner fa-spin" style="font-size: 48px; color: #3b82f6;"></i>
                        <p style="margin-top: 20px; color: #64748b;">Cargando datos cualitativos...</p>
                    </div>
                </div>
            </div>
        """
        
        # Usar wrapper para estructura completa
        bootstrap_js = '<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>'
        
        return dashboard_layout.get_html_wrapper(
            title='Dashboard de Métricas',
            content=content,
            sidebar_html=sidebar_html,
            topbar_html=topbar_html,
            styles=dashboard_styles.get_common_styles(),
            scripts=self._scripts(),
            head_extra=bootstrap_js
        )

    def _build_html(self, metrics, groups, evaluations, filters, role_info, kpi_html, charts, segmentation_vars):
        """Construye el HTML completo del dashboard."""
        # Usar utilidades compartidas
        role_badge = dashboard_helpers.get_role_badge(role_info)
        filter_controls = self._build_filter_controls(metrics, groups, evaluations, filters)
        sidebar_html = dashboard_layout.get_sidebar(role_info, active_section='home')
        
        # Topbar con fecha
        date_str = dashboard_helpers.format_date(fields.Date.today())
        topbar_html = dashboard_layout.get_topbar(
            title='Inicio',
            subtitle=f'<i class="fa-regular fa-calendar me-2"></i>{date_str}',
            role_badge=role_badge
        )
        
        home_html = self._home_section(metrics, groups, evaluations, filters, role_info)
        
        charts_html = '\n'.join(charts) if charts else '<p class="text-muted">No hay gráficos para mostrar</p>'
        
        # Construir contenido de las secciones
        content = f"""
            <!-- Sección Home -->
            <div class="content-section active" id="section-home">
                {home_html}
            </div>
            
            <!-- Sección Datos Cuantitativos -->
            <div class="content-section" id="section-quantitative">
                <div class="container-fluid">
                    {filter_controls}
                    
                    <div class="kpi-container my-4">
                        {kpi_html}
                    </div>
                    
                    <div class="charts-container">
                        {charts_html}
                    </div>
                </div>
            </div>
            
            <!-- Sección Datos Cualitativos -->
            <div class="content-section" id="section-qualitative">
                <div id="qualitativeContent">
                    <div style="text-align: center; padding: 60px 20px;">
                        <i class="fa-solid fa-spinner fa-spin" style="font-size: 48px; color: #3b82f6;"></i>
                        <p style="margin-top: 20px; color: #64748b;">Cargando datos cualitativos...</p>
                    </div>
                </div>
            </div>
        """
        
        # Usar wrapper con Chart.js incluido
        chart_libs = '<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>\n' + \
                     '<script src="https://cdn.jsdelivr.net/npm/chartjs-adapter-date-fns@3.0.0/dist/chartjs-adapter-date-fns.bundle.min.js"></script>'
        
        return dashboard_layout.get_html_wrapper(
            title='Dashboard de Métricas',
            content=content,
            sidebar_html=sidebar_html,
            topbar_html=topbar_html,
            styles=dashboard_styles.get_common_styles(),
            scripts=self._scripts(),
            head_extra=chart_libs
        )

    def _build_filter_controls(self, metrics, groups, evaluations, filters):
        """Construye controles de filtrado compactos (solo evaluaciones)."""
        # Pills de evaluaciones
        eval_checks = ''
        selected_evals = filters.get('evaluation_ids', [])
        for e in evaluations:
            active = 'active' if e['id'] in selected_evals or not selected_evals else ''
            
            eval_checks += f"""
            <span class="filter-pill eval-pill {active}" data-type="eval" data-value="{e['id']}" onclick="togglePill(this)">
                {e['name']}
            </span>"""

        # Los estilos están definidos en dashboard_styles.py (get_common_styles)
        return f"""
        <div class="filter-panel-compact">
            <form id="hub-filters" method="get" action="/aulametrics/dashboard">
                <div class="filter-header">
                    <i class="fa-solid fa-filter"></i>
                    <span>Filtrar por Evaluaciones</span>
                </div>
                
                <div class="filter-pills-container">
                    {eval_checks}
                </div>
                
                <div class="filter-actions">
                    <button type="button" class="btn-filter-action" onclick="selectAllEvals()">
                        <i class="fa-solid fa-check-double me-1"></i>Todas
                    </button>
                    <button type="button" class="btn-filter-action" onclick="selectNoneEvals()">
                        <i class="fa-solid fa-xmark me-1"></i>Ninguna
                    </button>
                    <button type="submit" class="btn-filter-action btn-filter-primary">
                        <i class="fa-solid fa-magnifying-glass me-1"></i>Aplicar Filtros
                    </button>
                </div>
            </form>
        </div>
        """
    
    def _home_section(self, metrics, groups, evaluations, filters, role_info):
        """Sección Home con evaluaciones activas y estadísticas."""
        try:
            # Obtener evaluaciones activas
            active_evaluations = self._get_active_evaluations(role_info)
            
            # Generar tarjetas de evaluación
            evaluation_cards_html = self._build_evaluation_cards(active_evaluations, role_info)
            
            # Generar estadísticas rápidas
            quick_stats_html = self._build_quick_stats(active_evaluations, role_info)
            
            return f"""
    <div class="home-section">
        <div class="welcome-banner">
            <h2>
                <i class="fa-solid fa-hand-wave me-3" style="color: #fbbf24;"></i>
                Bienvenido al Dashboard de AulaMetrics
            </h2>
            <p>Panel de control para el seguimiento del bienestar del alumnado</p>
        </div>
        
        {quick_stats_html}
        
        <div class="evaluations-section">
            <h3 class="section-title">
                <i class="fa-solid fa-clipboard-check"></i>
                Evaluaciones Activas
            </h3>
            {evaluation_cards_html}
        </div>
    </div>
            """
        except Exception as e:
            # Si ocurre error, mostrar vista simplificada con estilos
            return f"""
    <div class="home-section">
        <div class="welcome-banner">
            <h2>
                <i class="fa-solid fa-hand-wave me-3" style="color: #fbbf24;"></i>
                Bienvenido al Dashboard de AulaMetrics
            </h2>
            <p>Utiliza el menú lateral para navegar entre las diferentes secciones</p>
        </div>
        <div class="empty-state">
            <i class="fa-solid fa-exclamation-triangle fa-3x"></i>
            <h3>Error al cargar las evaluaciones</h3>
            <p>Por favor, contacte al administrador del sistema</p>
        </div>
    </div>
            """
    
    def _get_active_evaluations(self, role_info):
        """
        Obtiene las evaluaciones activas filtradas por rol.
        
        Args:
            role_info (dict): Información del rol del usuario
        
        Returns:
            list: Lista de dicts con información de evaluaciones activas
        """
        Evaluation = self.env['aulametrics.evaluation']
        
        # Filtro base: solo evaluaciones activas
        domain = [('state', '=', 'active')]
        
        # Filtrar por rol tutor: solo evaluaciones de sus grupos
        if role_info.get('role') == 'tutor':
            allowed_groups = role_info.get('allowed_group_ids', [])
            if allowed_groups:
                domain.append(('academic_group_ids', 'in', allowed_groups))
            else:
                return []  # Tutor sin grupos asignados
        
        # Buscar evaluaciones
        evaluations = Evaluation.search(domain, order='date_start desc')
        
        result = []
        for evaluation in evaluations:
            eval_data = {
                'id': evaluation.id,
                'name': evaluation.name,
                'date_start': evaluation.date_start,
                'date_end': evaluation.date_end,
                'participation_rate': evaluation.participation_rate,
                'total_students': evaluation.total_students,
                'completed_students': evaluation.completed_students,
            }
            
            # Contar alertas activas relacionadas (solo para counselor/admin)
            if role_info.get('role') in ['admin', 'counselor']:
                Alert = self.env['aulametrics.alert']
                alert_count = Alert.search_count([
                    ('participation_id.evaluation_id', '=', evaluation.id),
                    ('status', '=', 'active')
                ])
                eval_data['alert_count'] = alert_count
            
            result.append(eval_data)
        
        return result
    
    def _build_evaluation_cards(self, evaluations, role_info):
        """
        Construye el HTML de las tarjetas de evaluaciones.
        
        Args:
            evaluations (list): Lista de evaluaciones
            role_info (dict): Información del rol del usuario
        
        Returns:
            str: HTML de las tarjetas
        """
        if not evaluations:
            return """
            <div class="empty-evaluations">
                <i class="fa-solid fa-clipboard-question"></i>
                <h3>No hay evaluaciones activas</h3>
                <p>No se encontraron evaluaciones activas en este momento</p>
            </div>
            """
        
        cards_html = '<div class="evaluations-grid">'
        
        for evaluation in evaluations:
            # Formatear datos
            date_range = dashboard_helpers.format_date_range(
                evaluation['date_start'], 
                evaluation['date_end']
            )
            participation = dashboard_helpers.format_participation_rate(
                evaluation['participation_rate']
            )
            
            # Determinar clase de badge de participación
            rate = evaluation['participation_rate']
            if rate >= 80:
                participation_class = 'high'
            elif rate >= 50:
                participation_class = 'medium'
            else:
                participation_class = 'low'
            
            # HTML de alertas (solo para counselor/admin)
            alerts_html = ''
            if role_info.get('role') in ['admin', 'counselor']:
                alert_count = evaluation.get('alert_count', 0)
                alert_badge_class = 'zero' if alert_count == 0 else ''
                alert_icon = 'fa-check-circle' if alert_count == 0 else 'fa-exclamation-triangle'
                alerts_html = f"""
                <div class="evaluation-info-item">
                    <i class="fa-solid fa-bell"></i>
                    <span class="evaluation-info-label">Alertas:</span>
                    <span class="alerts-badge {alert_badge_class}">
                        <i class="fa-solid {alert_icon}"></i>
                        {alert_count}
                    </span>
                </div>
                """
            
            cards_html += f"""
            <div class="evaluation-card">
                <div class="evaluation-card-header">
                    <h4 class="evaluation-card-title">
                        <i class="fa-solid fa-clipboard-check"></i>
                        {evaluation['name']}
                    </h4>
                </div>
                <div class="evaluation-card-body">
                    <div class="evaluation-info-item">
                        <i class="fa-solid fa-calendar-days"></i>
                        <span class="evaluation-info-label">Período:</span>
                        <span class="evaluation-info-value">{date_range}</span>
                    </div>
                    <div class="evaluation-info-item">
                        <i class="fa-solid fa-chart-line"></i>
                        <span class="evaluation-info-label">Participación:</span>
                        <span class="participation-badge {participation_class}">{participation}</span>
                    </div>
                    <div class="evaluation-info-item">
                        <i class="fa-solid fa-users"></i>
                        <span class="evaluation-info-label">Completados:</span>
                        <span class="evaluation-info-value">{evaluation['completed_students']} / {evaluation['total_students']}</span>
                    </div>
                    {alerts_html}
                </div>
            </div>
            """
        
        cards_html += '</div>'
        return cards_html
    
    def _build_quick_stats(self, evaluations, role_info):
        """
        Genera las estadísticas rápidas.
        
        Args:
            evaluations (list): Lista de evaluaciones
            role_info (dict): Información del rol del usuario
        
        Returns:
            str: HTML de las estadísticas
        """
        # Calcular estadísticas
        total_evaluations = len(evaluations)
        
        # Participación promedio
        if evaluations:
            avg_participation = sum(e['participation_rate'] for e in evaluations) / len(evaluations)
        else:
            avg_participation = 0.0
        
        # Total de alertas (solo para counselor/admin)
        total_alerts = 0
        if role_info.get('role') in ['admin', 'counselor']:
            total_alerts = sum(e.get('alert_count', 0) for e in evaluations)
        
        # Construir HTML
        stats_html = '<div class="quick-stats-container">'
        
        # Stat 1: Total evaluaciones activas
        stats_html += f"""
        <div class="stat-card">
            <div class="stat-icon blue">
                <i class="fa-solid fa-clipboard-check"></i>
            </div>
            <div class="stat-content">
                <div class="stat-label">Evaluaciones Activas</div>
                <div class="stat-value">{total_evaluations}</div>
            </div>
        </div>
        """
        
        # Stat 2: Participación promedio
        stats_html += f"""
        <div class="stat-card">
            <div class="stat-icon green">
                <i class="fa-solid fa-chart-line"></i>
            </div>
            <div class="stat-content">
                <div class="stat-label">Participación Promedio</div>
                <div class="stat-value">{dashboard_helpers.format_participation_rate(avg_participation)}</div>
            </div>
        </div>
        """
        
        # Stat 3: Alertas activas (solo counselor/admin)
        if role_info.get('role') in ['admin', 'counselor']:
            stats_html += f"""
        <div class="stat-card">
            <div class="stat-icon red">
                <i class="fa-solid fa-bell"></i>
            </div>
            <div class="stat-content">
                <div class="stat-label">Alertas Activas</div>
                <div class="stat-value">{total_alerts}</div>
            </div>
        </div>
            """
        
        stats_html += '</div>'
        return stats_html

    def _home_section_old(self, metrics, groups, evaluations, filters, role_info):
        """Sección Home simplificada."""
        return f"""
    <div class="home-section">
        <div class="welcome-banner">
            <h2>
                <i class="fa-solid fa-hand-wave me-3" style="color: #f59e0b;"></i>
                Bienvenido al Dashboard
            </h2>
            <p>Utiliza el menú lateral para navegar entre las diferentes secciones</p>
        </div>
    </div>
        """

    def _scripts(self):
        """Scripts JavaScript del dashboard (SIMPLIFICADO: solo evaluaciones)."""
        return """
    <script>
        function togglePill(pill) {
            pill.classList.toggle('active');
        }
        
        function selectAllEvals() {
            document.querySelectorAll('.eval-pill').forEach(pill => {
                pill.classList.add('active');
            });
        }
        
        function selectNoneEvals() {
            document.querySelectorAll('.eval-pill').forEach(pill => {
                pill.classList.remove('active');
            });
        }
        
        document.getElementById('hub-filters').addEventListener('submit', function(e) {
            e.preventDefault(); // Prevenir recarga de página
            
            // Obtener botón de submit
            const submitBtn = e.target.querySelector('button[type="submit"]');
            const originalBtnContent = submitBtn.innerHTML;
            
            // Cambiar botón a estado loading
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin me-1"></i>Cargando...';
            
            // Consolidar pills de evaluaciones activas
            const evalPills = document.querySelectorAll('.eval-pill.active');
            const evalValues = Array.from(evalPills).map(p => p.dataset.value);
            
            // Construir URL con parámetros
            const params = new URLSearchParams();
            if (evalValues.length > 0) {
                params.append('evaluation_ids', evalValues.join(','));
            }
            params.append('section', 'quantitative');
            
            const url = '/aulametrics/dashboard?' + params.toString();
            
            // Mostrar indicador de carga
            const kpiContainer = document.querySelector('#section-quantitative .kpi-container');
            const chartsContainer = document.querySelector('#section-quantitative .charts-container');
            
            if (kpiContainer) {
                kpiContainer.style.opacity = '0.5';
                kpiContainer.style.transition = 'opacity 0.3s';
            }
            if (chartsContainer) {
                chartsContainer.style.opacity = '0.5';
                chartsContainer.style.transition = 'opacity 0.3s';
            }
            
            // Hacer petición AJAX
            fetch(url)
                .then(response => response.text())
                .then(html => {
                    // Crear un elemento temporal para parsear el HTML
                    const tempDiv = document.createElement('div');
                    tempDiv.innerHTML = html;
                    
                    // Extraer los KPIs
                    const newKpis = tempDiv.querySelector('.kpi-container');
                    if (newKpis && kpiContainer) {
                        kpiContainer.innerHTML = newKpis.innerHTML;
                        kpiContainer.style.opacity = '0';
                        setTimeout(() => {
                            kpiContainer.style.opacity = '1';
                        }, 50);
                    }
                    
                    // Extraer los gráficos
                    const newCharts = tempDiv.querySelector('.charts-container');
                    if (newCharts && chartsContainer) {
                        chartsContainer.innerHTML = newCharts.innerHTML;
                        chartsContainer.style.opacity = '0';
                        
                        // Re-ejecutar scripts de los gráficos
                        const scripts = chartsContainer.querySelectorAll('script');
                        scripts.forEach(oldScript => {
                            const newScript = document.createElement('script');
                            newScript.textContent = oldScript.textContent;
                            oldScript.parentNode.replaceChild(newScript, oldScript);
                        });
                        
                        setTimeout(() => {
                            chartsContainer.style.opacity = '1';
                        }, 50);
                    }
                    
                    // Restaurar botón
                    submitBtn.disabled = false;
                    submitBtn.innerHTML = originalBtnContent;
                    
                    // Smooth scroll a los resultados
                    if (kpiContainer) {
                        kpiContainer.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                    }
                    
                    // Actualizar URL sin recargar
                    history.pushState({}, '', url);
                })
                .catch(error => {
                    console.error('Error al aplicar filtros:', error);
                    
                    // Restaurar botón
                    submitBtn.disabled = false;
                    submitBtn.innerHTML = originalBtnContent;
                    
                    // Mostrar error
                    if (kpiContainer) {
                        kpiContainer.style.opacity = '1';
                        kpiContainer.innerHTML = '<div style="text-align: center; padding: 40px;"><i class="fa-solid fa-exclamation-triangle" style="font-size: 32px; color: #ef4444;"></i><p style="margin-top: 12px; color: #64748b;">Error al cargar datos. Intenta de nuevo.</p></div>';
                    }
                    if (chartsContainer) {
                        chartsContainer.style.opacity = '1';
                    }
                });
        });
        
        // Navegación entre secciones
        function navigateTo(section) {
            // Actualizar items del sidebar
            document.querySelectorAll('.sidebar-item').forEach(item => {
                item.classList.remove('active');
            });
            document.querySelector(`[data-section="${section}"]`).classList.add('active');
            
            // Actualizar secciones de contenido
            document.querySelectorAll('.content-section').forEach(sec => {
                sec.classList.remove('active');
            });
            document.getElementById(`section-${section}`).classList.add('active');
            
            // Actualizar título
            const titles = {
                'home': 'Inicio',
                'quantitative': 'Datos Cuantitativos',
                'qualitative': 'Datos Cualitativos'
            };
            document.getElementById('sectionTitle').textContent = titles[section] || section;
            
            // Cargar contenido cualitativo si es necesario
            if (section === 'qualitative' && !window.qualitativeLoaded) {
                loadQualitativeContent();
            }
        }
        
        // Cargar contenido cualitativo
        function loadQualitativeContent() {
            window.qualitativeLoaded = true;
            const contentDiv = document.getElementById('qualitativeContent');
            
            fetch('/aulametrics/qualitative/dashboard?embedded=true')
                .then(response => response.text())
                .then(html => {
                    contentDiv.innerHTML = html;
                    
                    // Ejecutar scripts si los hay
                    const scripts = contentDiv.querySelectorAll('script');
                    scripts.forEach(oldScript => {
                        const newScript = document.createElement('script');
                        if (oldScript.src) {
                            newScript.src = oldScript.src;
                            if (oldScript.src.includes('d3')) {
                                newScript.onload = function() {
                                    console.log('D3 cargado:', oldScript.src);
                                };
                            }
                        } else {
                            newScript.textContent = oldScript.textContent;
                        }
                        oldScript.parentNode.replaceChild(newScript, oldScript);
                    });
                    
                    // Inicializar wordclouds
                    setTimeout(() => {
                        console.log('Intentando inicializar wordclouds...');
                        if (typeof initWordcloudCounselor !== 'undefined') {
                            console.log('Llamando a initWordcloudCounselor');
                            initWordcloudCounselor();
                        } else if (typeof initWordcloudTutor !== 'undefined') {
                            console.log('Llamando a initWordcloudTutor');
                            initWordcloudTutor();
                        } else {
                            console.log('No se encontraron funciones de inicialización de wordcloud');
                        }
                    }, 500);
                })
                .catch(error => {
                    contentDiv.innerHTML = '<div style="text-align: center; padding: 60px 20px;"><i class="fa-solid fa-exclamation-triangle" style="font-size: 48px; color: #ef4444;"></i><p style="margin-top: 20px; color: #64748b;">Error al cargar datos cualitativos</p></div>';
                    console.error('Error cargando datos cualitativos:', error);
                });
        }
        
        // Al cargar la página, navegar a la sección indicada en la URL
        document.addEventListener('DOMContentLoaded', function() {
            const urlParams = new URLSearchParams(window.location.search);
            const section = urlParams.get('section');
            if (section && ['home', 'quantitative', 'qualitative'].includes(section)) {
                navigateTo(section);
            }
            
            // Event delegation para formulario cualitativo (interceptar submit)
            document.addEventListener('submit', function(e) {
                const form = e.target;
                
                // Solo interceptar si es el formulario cualitativo embebido
                if (form.id === 'qualitativeFiltersForm') {
                    e.preventDefault();
                    
                    const formData = new FormData(form);
                    const params = new URLSearchParams();
                    
                    for (const [key, value] of formData.entries()) {
                        if (value) params.append(key, value);
                    }
                    params.append('embedded', 'true');
                    
                    const url = '/aulametrics/qualitative/dashboard?' + params.toString();
                    
                    fetch(url)
                        .then(response => response.text())
                        .then(html => {
                            const contentDiv = document.getElementById('qualitativeContent');
                            if (contentDiv) {
                                contentDiv.innerHTML = html;
                                
                                // Re-ejecutar scripts
                                const scripts = contentDiv.querySelectorAll('script');
                                scripts.forEach(oldScript => {
                                    const newScript = document.createElement('script');
                                    if (oldScript.src) {
                                        newScript.src = oldScript.src;
                                    } else {
                                        newScript.textContent = oldScript.textContent;
                                    }
                                    oldScript.parentNode.replaceChild(newScript, oldScript);
                                });
                                
                                // Reinicializar wordclouds
                                setTimeout(() => {
                                    if (typeof initWordcloudCounselor !== 'undefined') {
                                        initWordcloudCounselor();
                                    } else if (typeof initWordcloudTutor !== 'undefined') {
                                        initWordcloudTutor();
                                    }
                                }, 300);
                            }
                        })
                        .catch(error => {
                            console.error('Error al filtrar datos cualitativos:', error);
                            alert('Error al aplicar filtros');
                        });
                }
            });
        });
    </script>
        """
