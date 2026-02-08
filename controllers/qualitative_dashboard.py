# -*- coding: utf-8 -*-

from odoo import http
from odoo.http import request
import json
from collections import Counter
import re

class QualitativeDashboardController(http.Controller):
    
    @http.route('/aulametrics/qualitative/dashboard', type='http', auth='user')
    def qualitative_dashboard(self, evaluation_id=None, question_id=None, embedded=None, **kwargs):
        """
        Dashboard principal de datos cualitativos.
        Muestra diferentes vistas según el rol del usuario.
        
        Args:
            embedded: Si es 'true', devuelve solo el contenido sin wrapper HTML
        """
        
        # Detectar rol del usuario
        user = request.env.user
        role = self._detect_user_role(user)
        
        # Obtener respuestas según permisos del rol
        domain = []
        if evaluation_id:
            domain.append(('evaluation_id', '=', int(evaluation_id)))
        if question_id:
            domain.append(('question_id', '=', int(question_id)))
        
        # Aplicar filtros por rol
        if role == 'tutor':
            # Solo su grupo académico
            tutor_groups = request.env['aulametrics.academic_group'].search([
                ('tutor_id', '=', user.id)
            ])
            domain.append(('academic_group_id', 'in', tutor_groups.ids))
        
        responses = request.env['aulametrics.qualitative_response'].search(
            domain, 
            order='response_date desc',
            limit=500  # Límite de seguridad
        )
        
        # Obtener filtros disponibles
        evaluations = self._get_available_evaluations(role)
        questions = self._get_available_questions(responses)
        
        # Construir contexto según rol
        context = {
            'role': role,
            'evaluations': evaluations,
            'questions': questions,
            'evaluation_id': int(evaluation_id) if evaluation_id else None,
            'question_id': int(question_id) if question_id else None,
        }
        
        # Añadir datos específicos por rol
        if role == 'counselor':
            context.update(self._get_counselor_data(responses))
        elif role == 'tutor':
            context.update(self._get_tutor_data(responses))
        else:  # management
            context.update(self._get_management_data(responses))
        
        # Generar HTML directamente
        if embedded == 'true':
            html_content = self._generate_embedded_html(context)
        else:
            html_content = self._generate_html(context)
        
        return request.make_response(
            html_content,
            headers=[('Content-Type', 'text/html; charset=utf-8')]
        )
    
    def _detect_user_role(self, user):
        """Detecta el rol principal del usuario."""
        if user.has_group('aula_metrics.group_aulametrics_counselor') or \
           user.has_group('aula_metrics.group_aulametrics_admin'):
            return 'counselor'
        elif user.has_group('aula_metrics.group_aulametrics_tutor'):
            return 'tutor'
        else:
            return 'management'
    
    def _get_available_evaluations(self, role):
        """Obtiene evaluaciones disponibles según rol."""
        domain = [('state', 'in', ['scheduled', 'active', 'completed'])]
        
        if role == 'tutor':
            # Solo evaluaciones de sus grupos
            user = request.env.user
            tutor_groups = request.env['aulametrics.academic_group'].search([
                ('tutor_id', '=', user.id)
            ])
            domain.append(('academic_group_ids', 'in', tutor_groups.ids))
        
        return request.env['aulametrics.evaluation'].search(
            domain,
            order='date_start desc'
        )
    
    def _get_available_questions(self, responses):
        """Obtiene preguntas que tienen respuestas."""
        question_ids = responses.mapped('question_id')
        return question_ids.sorted(key=lambda q: q.sequence)
    
    def _get_counselor_data(self, responses):
        """
        Vista completa identificada para counselor.
        Incluye tabla de respuestas + wordcloud.
        """
        
        # Preparar datos de tabla
        table_data = []
        for r in responses:
            table_data.append({
                'id': r.id,
                'student_id': r.student_id.id,
                'student_name': r.student_id.name,
                'group_name': r.academic_group_id.name if r.academic_group_id else 'N/A',
                'date': r.response_date.strftime('%d/%m/%Y %H:%M'),
                'response': r.response_text,
                'word_count': r.word_count,
                'has_alerts': r.has_alert_keywords,
                'keywords': json.loads(r.detected_keywords) if r.detected_keywords else [],
                'question': r.question_id.title
            })
        
        # Generar wordcloud data
        wordcloud_data = self._generate_wordcloud(responses)
        
        return {
            'view_type': 'counselor',
            'responses': table_data,
            'wordcloud_data': wordcloud_data,  # No hacer json.dumps aquí
            'total_responses': len(responses),
            'responses_with_alerts': len([r for r in responses if r.has_alert_keywords])
        }
    
    def _get_tutor_data(self, responses):
        """
        Vista anónima para tutor con wordcloud y estadísticas.
        """
        
        # Wordcloud
        wordcloud_data = self._generate_wordcloud(responses)
        
        # Estadísticas
        total = len(responses)
        avg_length = sum(r.word_count for r in responses) / total if total > 0 else 0
        top_words = wordcloud_data[:10] if wordcloud_data else []
        
        # Respuestas anónimas
        anonymous_responses = []
        for r in responses:
            anonymous_responses.append({
                'date': r.response_date.strftime('%d/%m/%Y'),
                'response': r.response_text,
                'has_alerts': r.has_alert_keywords,
                'word_count': r.word_count
            })
        
        return {
            'view_type': 'tutor',
            'wordcloud_data': wordcloud_data,  # No hacer json.dumps aquí
            'anonymous_responses': anonymous_responses,
            'stats': {
                'total_responses': total,
                'avg_length': round(avg_length, 1),
                'top_words': top_words,
                'responses_with_alerts': len([r for r in responses if r.has_alert_keywords])
            }
        }
    
    def _get_management_data(self, responses):
        """
        Vista agregada para management (solo estadísticas por curso).
        """
        
        # Agrupar por curso
        by_course = {}
        for r in responses:
            course = r.course_level or 'Sin clasificar'
            if course not in by_course:
                by_course[course] = []
            by_course[course].append(r)
        
        # Calcular estadísticas por curso
        stats_by_course = {}
        for course, course_responses in by_course.items():
            # Palabras más frecuentes del curso
            wordcloud_data = self._generate_wordcloud(course_responses)
            
            stats_by_course[course] = {
                'total_responses': len(course_responses),
                'avg_length': round(sum(r.word_count for r in course_responses) / len(course_responses), 1) if course_responses else 0,
                'top_words': wordcloud_data[:10],
                'responses_with_alerts': len([r for r in course_responses if r.has_alert_keywords])
            }
        
        return {
            'view_type': 'management',
            'stats_by_course': stats_by_course,
            'total_responses': len(responses)
        }
    
    def _generate_wordcloud(self, responses):
        """
        Genera datos para wordcloud (frecuencia de palabras).
        Retorna lista de tuplas (palabra, frecuencia) ordenadas.
        """
        
        # Stopwords en español (palabras comunes a ignorar)
        STOPWORDS = {
            'el', 'la', 'de', 'que', 'y', 'a', 'en', 'un', 'ser', 'se', 'no', 'haber',
            'por', 'con', 'su', 'para', 'como', 'estar', 'tener', 'le', 'lo', 'todo',
            'pero', 'más', 'hacer', 'o', 'poder', 'decir', 'este', 'ir', 'otro', 'ese',
            'la', 'si', 'me', 'ya', 'ver', 'porque', 'dar', 'cuando', 'él', 'muy',
            'sin', 'vez', 'mucho', 'saber', 'qué', 'sobre', 'mi', 'alguno', 'mismo',
            'yo', 'también', 'hasta', 'año', 'dos', 'querer', 'entre', 'así', 'primero',
            'desde', 'grande', 'eso', 'ni', 'nos', 'llegar', 'pasar', 'tiempo', 'ella',
            'sí', 'día', 'uno', 'bien', 'poco', 'deber', 'entonces', 'poner', 'cosa',
            'tanto', 'hombre', 'parecer', 'nuestro', 'tan', 'donde', 'ahora', 'parte',
            'después', 'vida', 'quedar', 'siempre', 'creer', 'hablar', 'llevar', 'dejar',
            'nada', 'cada', 'seguir', 'menos', 'nuevo', 'encontrar', 'algo', 'solo',
            'decir', 'estos', 'trabajar', 'llamar', 'mundo', 'venir', 'pensar', 'salir',
            'volver', 'tomar', 'conocer', 'vivir', 'sentir', 'tratar', 'mirar', 'contar',
            'empezar', 'esperar', 'buscar', 'existir', 'entrar', 'trabajar', 'escribir',
            'perder', 'producir', 'ocurrir', 'entender', 'pedir', 'recibir', 'recordar',
            'terminar', 'permitir', 'aparecer', 'conseguir', 'comenzar', 'servir',
            'sacar', 'necesitar', 'mantener', 'resultar', 'leer', 'caer', 'cambiar',
            'presentar', 'crear', 'abrir', 'considerar', 'oír', 'acabar', 'mil', 'tu',
            'te', 'les', 'ha', 'he', 'hay', 'estoy', 'esta', 'están', 'son', 'fue',
            'del', 'al', 'una', 'unos', 'unas', 'los', 'las', 'es', 'era', 'eres',
            'creo', 'me', 'gustaría', 'hubiera', 'debería', 'podría', 'sería'
        }
        
        all_words = []
        for r in responses:
            # Tokenizar: solo palabras de 4+ letras
            words = re.findall(r'\b[a-záéíóúñü]{4,}\b', r.response_text.lower())
            # Filtrar stopwords
            words = [w for w in words if w not in STOPWORDS]
            all_words.extend(words)
        
        # Contar frecuencias
        word_freq = Counter(all_words).most_common(50)
        
        return word_freq
    
    def _generate_html(self, context):
        """Genera el HTML completo del dashboard cualitativo."""
        role = context['role']
        
        # Construir opciones de evaluaciones
        eval_options = ''
        for eval in context['evaluations']:
            selected = 'selected' if context.get('evaluation_id') == eval.id else ''
            eval_options += f'<option value="{eval.id}" {selected}>{eval.name}</option>'
        
        # Construir opciones de preguntas
        question_options = ''
        for q in context['questions']:
            selected = 'selected' if context.get('question_id') == q.id else ''
            title = q.title[:80] if len(q.title) > 80 else q.title
            question_options += f'<option value="{q.id}" {selected}>{title}</option>'
        
        # Descripción del rol
        role_desc = {
            'counselor': 'Vista completa identificada - Acceso total',
            'tutor': 'Vista de tu grupo - Respuestas anónimas',
            'management': 'Vista agregada del centro - Solo estadísticas'
        }.get(role, '')
        
        # Generar contenido específico por rol
        content_html = ''
        if role == 'counselor':
            content_html = self._generate_counselor_view(context)
        elif role == 'tutor':
            content_html = self._generate_tutor_view(context)
        else:
            content_html = self._generate_management_view(context)
        
        return f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Análisis Cualitativo - AulaMetrics</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <script src="https://cdnjs.cloudflare.com/ajax/libs/d3/7.8.5/d3.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/d3-cloud/1.2.7/d3.layout.cloud.min.js"></script>
    {self._styles()}
</head>
<body>
    <div class="dashboard-header">
        <div>
            <div class="header-title">
                <h2><i class="fa-solid fa-comments me-2 text-primary"></i>Análisis Cualitativo</h2>
            </div>
            <div class="header-meta">{role_desc}</div>
        </div>
    </div>
    
    <div class="container-fluid">
        <!-- Filtros -->
        <div class="row mb-4">
            <div class="col-12">
                <div class="card">
                    <div class="card-body">
                        <form method="get" action="/aulametrics/qualitative/dashboard" class="row g-3">
                            <div class="col-md-5">
                                <label class="form-label">Evaluación</label>
                                <select name="evaluation_id" class="form-select">
                                    <option value="">Todas las evaluaciones</option>
                                    {eval_options}
                                </select>
                            </div>
                            <div class="col-md-5">
                                <label class="form-label">Pregunta</label>
                                <select name="question_id" class="form-select">
                                    <option value="">Todas las preguntas</option>
                                    {question_options}
                                </select>
                            </div>
                            <div class="col-md-2 d-flex align-items-end">
                                <button type="submit" class="btn btn-primary w-100">Filtrar</button>
                            </div>
                        </form>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Contenido según rol -->
        {content_html}
    </div>
</body>
</html>"""
    
    def _generate_embedded_html(self, context):
        """Genera HTML embebido para integración en pestañas (sin wrapper completo)."""
        role = context['role']
        
        # Construir opciones de evaluaciones
        eval_options = ''
        for eval in context['evaluations']:
            selected = 'selected' if context.get('evaluation_id') == eval.id else ''
            eval_options += f'<option value="{eval.id}" {selected}>{eval.name}</option>'
        
        # Construir opciones de preguntas
        question_options = ''
        for q in context['questions']:
            selected = 'selected' if context.get('question_id') == q.id else ''
            title = q.title[:80] if len(q.title) > 80 else q.title
            question_options += f'<option value="{q.id}" {selected}>{title}</option>'
        
        # Descripción del rol
        role_desc = {
            'counselor': 'Vista completa identificada - Acceso total',
            'tutor': 'Vista de tu grupo - Respuestas anónimas',
            'management': 'Vista agregada del centro - Solo estadísticas'
        }.get(role, '')
        
        # Generar contenido específico por rol
        content_html = ''
        if role == 'counselor':
            content_html = self._generate_counselor_view(context)
        elif role == 'tutor':
            content_html = self._generate_tutor_view(context)
        else:
            content_html = self._generate_management_view(context)
        
        # Devolver solo el contenido con estilos inline (sin html/head/body wrapper)
        return f"""
    <script src="https://cdnjs.cloudflare.com/ajax/libs/d3/7.8.5/d3.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/d3-cloud/1.2.7/d3.layout.cloud.min.js"></script>
    {self._styles()}
    <div class="container-fluid mt-4">
        <div class="row mb-3">
            <div class="col-12">
                <p class="text-muted" style="font-size: 14px; margin-bottom: 16px;">{role_desc}</p>
            </div>
        </div>
        
        <!-- Filtros -->
        <div class="row mb-4">
            <div class="col-12">
                <div class="card">
                    <div class="card-body">
                        <form method="get" action="/aulametrics/qualitative/dashboard" class="row g-3">
                            <div class="col-md-5">
                                <label class="form-label">Evaluación</label>
                                <select name="evaluation_id" class="form-select">
                                    <option value="">Todas las evaluaciones</option>
                                    {eval_options}
                                </select>
                            </div>
                            <div class="col-md-5">
                                <label class="form-label">Pregunta</label>
                                <select name="question_id" class="form-select">
                                    <option value="">Todas las preguntas</option>
                                    {question_options}
                                </select>
                            </div>
                            <div class="col-md-2 d-flex align-items-end">
                                <button type="submit" class="btn btn-primary w-100">Filtrar</button>
                            </div>
                        </form>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Contenido según rol -->
        {content_html}
    </div>
    """
    
    def _generate_counselor_view(self, context):
        """Genera HTML para vista counselor."""
        total_responses = context.get('total_responses', 0)
        responses_with_alerts = context.get('responses_with_alerts', 0)
        responses = context.get('responses', [])
        wordcloud_data = json.dumps(context.get('wordcloud_data', []))
        
        # Generar filas de la tabla
        rows_html = ''
        if not responses:
            rows_html = '<tr><td colspan="6" class="text-center text-muted py-4">No hay respuestas cualitativas.</td></tr>'
        else:
            for resp in responses:
                alert_class = 'table-warning' if resp['has_alerts'] else ''
                alert_badge = '''<span class="badge bg-danger">Alerta</span>''' if resp['has_alerts'] else '''<span class="badge bg-success">OK</span>'''
                
                # Respuesta con expand si es larga
                response_html = resp['response']
                if len(resp['response']) > 150:
                    preview = resp['response'][:150]
                    full_text_escaped = resp['response'].replace("'", "\\'")
                    response_html = f'''{preview}... <a href="#" class="text-primary" onclick="alert('{full_text_escaped}'); return false;">Ver más</a>'''
                
                rows_html += f'''
                <tr class="{alert_class}">
                    <td><a href="/aulametrics/student/{resp['student_id']}" class="fw-bold">{resp['student_name']}</a></td>
                    <td><span class="badge bg-secondary">{resp['group_name']}</span></td>
                    <td><small>{resp['date']}</small></td>
                    <td>{response_html}</td>
                    <td class="text-center">{resp['word_count']}</td>
                    <td>{alert_badge}</td>
                </tr>
                '''
        
        return f'''
        <!-- KPI Cards -->
        <div class="kpi-container">
            <div class="kpi-card">
                <div class="kpi-label">Total Respuestas</div>
                <div class="kpi-value">{total_responses}</div>
                <div class="kpi-description">Respuestas recibidas</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">Con Alertas</div>
                <div class="kpi-value">{responses_with_alerts}</div>
                <div class="kpi-description">Requieren atención</div>
            </div>
        </div>
        
        <div class="row">
            <div class="col-12 mb-4">
                <div class="card">
                    <div class="card-header">
                        <h5 class="card-title mb-0">Nube de Palabras</h5>
                    </div>
                    <div class="card-body">
                        <div id="wordcloud" style="width:100%; height:400px;"></div>
                    </div>
                </div>
            </div>
            <div class="col-12">
                <div class="card">
                    <div class="card-header">
                        <h5 class="card-title mb-0">Respuestas Completas</h5>
                    </div>
                    <div class="card-body">
                        <div class="table-responsive">
                            <table>
                                <thead>
                                    <tr>
                                        <th>Alumno</th>
                                        <th>Grupo</th>
                                        <th>Fecha</th>
                                        <th>Respuesta</th>
                                        <th>Palabras</th>
                                        <th>Estado</th>
                                    </tr>
                                </thead>
                                <tbody>{rows_html}</tbody>
                            </table>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        <script>
            // Función para inicializar wordcloud - se llama después de insertar el HTML
            function initWordcloudCounselor() {{
                var wordcloudData = {wordcloud_data};
                console.log('Inicializando wordcloud counselor, datos:', wordcloudData);
                
                if (wordcloudData && wordcloudData.length > 0) {{
                    var wordcloudEl = document.getElementById('wordcloud');
                    if (!wordcloudEl) {{
                        console.error('Elemento wordcloud no encontrado');
                        return;
                    }}
                    
                    var words = wordcloudData.map(d => ({{text: d[0], size: Math.sqrt(d[1]) * 10 + 10}}));
                    console.log('Palabras procesadas:', words);
                    
                    var layout = d3.layout.cloud()
                        .size([wordcloudEl.offsetWidth || 800, 400])
                        .words(words)
                        .padding(5)
                        .rotate(() => ~~(Math.random() * 2) * 90)
                        .font("Inter")
                        .fontSize(d => d.size)
                        .on("end", draw);
                    layout.start();
                    
                    function draw(words) {{
                        d3.select("#wordcloud").append("svg")
                            .attr("width", layout.size()[0])
                            .attr("height", layout.size()[1])
                            .append("g")
                            .attr("transform", "translate(" + layout.size()[0] / 2 + "," + layout.size()[1] / 2 + ")")
                            .selectAll("text")
                            .data(words)
                            .enter().append("text")
                            .style("font-size", d => d.size + "px")
                            .style("font-family", "Inter")
                            .style("fill", (d, i) => ["#3b82f6", "#8b5cf6", "#ec4899", "#f59e0b", "#10b981", "#06b6d4"][i % 6])
                            .attr("text-anchor", "middle")
                            .attr("transform", d => "translate(" + [d.x, d.y] + ")rotate(" + d.rotate + ")")
                            .text(d => d.text);
                    }}
                }} else {{
                    console.log('No hay datos para wordcloud');
                    document.getElementById('wordcloud').innerHTML = '<div style="text-align: center; padding: 40px; color: #94a3b8;">No hay suficientes palabras para generar la nube</div>';
                }}
            }}
            
            // Ejecutar inmediatamente si estamos en página standalone
            if (typeof initWordcloud === 'undefined') {{
                setTimeout(initWordcloudCounselor, 100);
            }}
        </script>
        '''
    
    def _generate_tutor_view(self, context):
        """Genera HTML para vista tutor."""
        stats = context.get('stats', {})
        anonymous_responses = context.get('anonymous_responses', [])
        wordcloud_data = json.dumps(context.get('wordcloud_data', []))
        
        # Generar cartas de respuestas anónimas
        responses_html = ''
        if not anonymous_responses:
            responses_html = '<p class="text-center text-muted py-4">No hay respuestas cualitativas.</p>'
        else:
            for resp in anonymous_responses:
                border = 'border-warning' if resp['has_alerts'] else ''
                badge = '<span class="badge bg-warning">Alerta</span>' if resp['has_alerts'] else ''
                responses_html += f'''
                <div class="mb-3 p-3 bg-light rounded border {border}">
                    <div class="d-flex justify-content-between mb-2">
                        <small class="text-muted">{resp['date']} | {resp['word_count']} palabras</small>
                        {badge}
                    </div>
                    <p class="mb-0">{resp['response']}</p>
                </div>
                '''
        
        top_words_html = ''.join([f'<li><strong>{w[0]}</strong> ({w[1]} veces)</li>' for w in stats.get('top_words', [])[:5]])
        
        return f'''
        <!-- KPI Cards -->
        <div class="kpi-container">
            <div class="kpi-card">
                <div class="kpi-label">Total Respuestas</div>
                <div class="kpi-value">{stats.get('total_responses', 0)}</div>
                <div class="kpi-description">De tu grupo</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">Longitud Media</div>
                <div class="kpi-value">{stats.get('avg_length', 0)}</div>
                <div class="kpi-description">Palabras promedio</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">Con Alertas</div>
                <div class="kpi-value">{stats.get('responses_with_alerts', 0)}</div>
                <div class="kpi-description">Requieren atención</div>
            </div>
        </div>
        
        <div class="row">
            <div class="col-md-4 mb-4">
                <div class="card">
                    <div class="card-header">
                        <h5 class="card-title mb-0">Palabras Frecuentes</h5>
                    </div>
                    <div class="card-body">
                        <ol>{top_words_html}</ol>
                    </div>
                </div>
            </div>
            <div class="col-md-8 mb-4">
                <div class="card">
                    <div class="card-header">
                        <h5 class="card-title mb-0">Nube de Palabras</h5>
                    </div>
                    <div class="card-body">
                        <div id="wordcloud" style="width:100%; height:350px;"></div>
                    </div>
                </div>
            </div>
            <div class="col-12">
                <div class="card">
                    <div class="card-header">
                        <h5 class="card-title mb-0">Respuestas Anónimas</h5>
                    </div>
                    <div class="card-body">{responses_html}</div>
                </div>
            </div>
        </div>
        <script>
            // Función para inicializar wordcloud tutor - se llama después de insertar el HTML
            function initWordcloudTutor() {{
                var wordcloudData = {wordcloud_data};
                console.log('Inicializando wordcloud tutor, datos:', wordcloudData);
                
                if (wordcloudData && wordcloudData.length > 0) {{
                    var wordcloudEl = document.getElementById('wordcloud');
                    if (!wordcloudEl) {{
                        console.error('Elemento wordcloud no encontrado');
                        return;
                    }}
                    
                    var words = wordcloudData.map(d => ({{text: d[0], size: Math.sqrt(d[1]) * 10 + 10}}));
                    console.log('Palabras procesadas:', words);
                    
                    var layout = d3.layout.cloud()
                        .size([wordcloudEl.offsetWidth || 800, 350])
                        .words(words)
                        .padding(5)
                        .rotate(() => ~~(Math.random() * 2) * 90)
                        .font("Inter")
                        .fontSize(d => d.size)
                        .on("end", draw);
                    layout.start();
                    
                    function draw(words) {{
                        d3.select("#wordcloud").append("svg")
                            .attr("width", layout.size()[0])
                            .attr("height", layout.size()[1])
                            .append("g")
                            .attr("transform", "translate(" + layout.size()[0] / 2 + "," + layout.size()[1] / 2 + ")")
                            .selectAll("text")
                            .data(words)
                            .enter().append("text")
                            .style("font-size", d => d.size + "px")
                            .style("font-family", "Inter")
                            .style("fill", (d, i) => ["#3b82f6", "#8b5cf6", "#ec4899", "#f59e0b", "#10b981", "#06b6d4"][i % 6])
                            .attr("text-anchor", "middle")
                            .attr("transform", d => "translate(" + [d.x, d.y] + ")rotate(" + d.rotate + ")")
                            .text(d => d.text);
                    }}
                }} else {{
                    console.log('No hay datos para wordcloud');
                    document.getElementById('wordcloud').innerHTML = '<div style="text-align: center; padding: 40px; color: #94a3b8;">No hay suficientes palabras para generar la nube</div>';
                }}
            }}
            
            // Ejecutar inmediatamente si estamos en página standalone
            if (typeof initWordcloud === 'undefined') {{
                setTimeout(initWordcloudTutor, 100);
            }}
        </script>
        '''
    
    def _generate_management_view(self, context):
        """Genera HTML para vista management."""
        total_responses = context.get('total_responses', 0)
        stats_by_course = context.get('stats_by_course', {})
        
        # Generar cartas por curso
        cards_html = ''
        if not stats_by_course:
            cards_html = '<div class="col-12"><p class="text-center text-muted py-5">No hay respuestas disponibles.</p></div>'
        else:
            for course, stats in stats_by_course.items():
                top_words = ''.join([f'<li><strong>{w[0]}</strong> ({w[1]})</li>' for w in stats.get('top_words', [])[:5]])
                cards_html += f'''
                <div class="col-md-6 col-lg-4 mb-4">
                    <div class="card h-100">
                        <div class="card-header">
                            <h5 class="card-title mb-0">{course}</h5>
                        </div>
                        <div class="card-body">
                            <div class="kpi-value">{stats.get('total_responses', 0)}</div>
                            <div class="kpi-label mb-3">Respuestas totales</div>
                            
                            <p class="mb-2"><strong>Longitud media:</strong> {stats.get('avg_length', 0)} palabras</p>
                            <p class="mb-3"><strong>Con alertas:</strong> {stats.get('responses_with_alerts', 0)}</p>
                            <hr>
                            <h6>Palabras frecuentes:</h6>
                            <ol class="small">{top_words}</ol>
                        </div>
                    </div>
                </div>
                '''
        
        return f'''
        <div class="row">
            <div class="col-12 mb-4">
                <div class="alert alert-info">
                    <h5 class="alert-heading">Vista Agregada de Privacidad</h5>
                    <p class="mb-0">Solo se muestran estadísticas agregadas por curso para proteger la privacidad de los estudiantes.</p>
                </div>
            </div>
            <div class="col-12 mb-4">
                <div class="kpi-card">
                    <div class="kpi-label">Total de Respuestas en el Centro</div>
                    <div class="kpi-value">{total_responses}</div>
                    <div class="kpi-description">Respuestas cualitativas recibidas</div>
                </div>
            </div>
            {cards_html}
        </div>
        '''
    
    def _styles(self):
        """Estilos profesionales tipo Stripe/Linear/Notion - Consistentes con el dashboard principal."""
        return """
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
        
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background-color: #fafbfc;
            color: #0f172a;
            line-height: 1.6;
            font-size: 15px;
            padding-bottom: 80px;
        }
        
        .dashboard-header {
            background: white;
            padding: 24px 32px;
            border-bottom: 1px solid #e5e7eb;
            margin-bottom: 32px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
        }
        
        .header-title h2 {
            font-size: 24px;
            font-weight: 700;
            margin: 0;
            color: #0f172a;
            letter-spacing: -0.5px;
        }
        
        .header-meta {
            color: #64748b;
            font-size: 14px;
            margin-top: 4px;
        }
        
        .container-fluid {
            max-width: 1400px;
            margin: 0 auto;
            padding: 0 24px;
        }
        
        /* Tarjetas de gráficos */
        .charts-container {
            display: grid;
            gap: 24px;
        }
        
        .card {
            background: white;
            border: 1px solid #e5e7eb;
            border-radius: 10px;
            overflow: hidden;
            box-shadow: 0 1px 3px rgba(0,0,0,0.04);
        }
        
        .card-header {
            padding: 20px 24px;
            border-bottom: 1px solid #f1f5f9;
            background: white;
        }
        
        .card-title {
            font-size: 18px;
            font-weight: 600;
            color: #0f172a;
            margin: 0;
        }
        
        .card-subtitle {
            font-size: 13px;
            color: #64748b;
            margin: 4px 0 0 0;
            font-weight: 400;
        }
        
        .card-body {
            padding: 24px;
        }
        
        .form-control, .form-select {
            border-radius: 6px;
            border: 1px solid #e5e7eb;
            padding: 8px 12px;
            font-size: 14px;
            font-family: 'Inter', sans-serif;
            transition: all 0.2s;
        }
        
        .form-control:focus, .form-select:focus {
            border-color: #3b82f6;
            box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
            outline: none;
        }
        
        .form-label {
            font-size: 13px;
            font-weight: 600;
            color: #475569;
            margin-bottom: 8px;
        }
        
        /* KPIs */
        .kpi-container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
            gap: 20px;
            margin-bottom: 32px;
        }
        
        .kpi-card {
            background: white;
            border: 1px solid #e5e7eb;
            border-radius: 10px;
            padding: 24px;
            transition: all 0.2s ease;
        }
        
        .kpi-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.08);
            border-color: #d1d5db;
        }
        
        .kpi-label {
            font-size: 13px;
            font-weight: 500;
            color: #64748b;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 8px;
        }
        
        .kpi-value {
            font-size: 36px;
            font-weight: 700;
            color: #0f172a;
            line-height: 1;
            margin-bottom: 4px;
        }
        
        .kpi-description {
            font-size: 13px;
            color: #94a3b8;
            font-weight: 400;
        }
        
        /* Tablas */
        table {
            width: 100%;
            border-collapse: collapse;
            font-size: 14px;
        }
        
        thead {
            background: #f8fafc;
            border-bottom: 1px solid #e5e7eb;
        }
        
        th {
            padding: 12px 16px;
            text-align: left;
            font-weight: 600;
            color: #475569;
            font-size: 13px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        td {
            padding: 14px 16px;
            border-bottom: 1px solid #f1f5f9;
            color: #334155;
        }
        
        tr:last-child td {
            border-bottom: none;
        }
        
        tbody tr:hover {
            background: #fafbfc;
        }
        
        /* Botones */
        .btn {
            padding: 8px 16px;
            border-radius: 6px;
            font-size: 14px;
            font-weight: 500;
            font-family: 'Inter', sans-serif;
            border: 1px solid transparent;
            cursor: pointer;
            transition: all 0.2s;
            text-decoration: none;
            display: inline-block;
        }
        
        .btn-primary {
            background: #3b82f6;
            color: white;
            border-color: #3b82f6;
        }
        
        .btn-primary:hover {
            background: #2563eb;
            border-color: #2563eb;
        }
        
        .btn-outline-secondary {
            background: white;
            color: #64748b;
            border-color: #e5e7eb;
        }
        
        .btn-outline-secondary:hover {
            background: #fafbfc;
            border-color: #d1d5db;
            color: #475569;
        }
        
        .btn-sm {
            padding: 6px 12px;
            font-size: 13px;
        }
        
        /* Badges */
        .badge {
            display: inline-block;
            padding: 4px 10px;
            border-radius: 6px;
            font-size: 12px;
            font-weight: 500;
            letter-spacing: 0.3px;
        }
        
        .badge.bg-danger {
            background: #fee2e2;
            color: #991b1b;
        }
        
        .badge.bg-primary {
            background: #dbeafe;
            color: #1e40af;
        }
        
        .badge.bg-warning {
            background: #fef3c7;
            color: #92400e;
        }
        
        .badge.bg-success {
            background: #d1fae5;
            color: #065f46;
        }
        
        .badge.bg-secondary {
            background: #f1f5f9;
            color: #475569;
        }
        
        /* Alertas */
        .alert {
            padding: 16px 20px;
            border-radius: 8px;
            border: 1px solid;
            margin-bottom: 20px;
        }
        
        .alert-info {
            background: #eff6ff;
            border-color: #bfdbfe;
            color: #1e40af;
        }
        
        .alert-warning {
            background: #fef3c7;
            border-color: #fde68a;
            color: #92400e;
        }
        
        .alert-heading {
            font-size: 16px;
            font-weight: 600;
            margin-bottom: 8px;
        }
        
        /* Utilidades */
        .mt-4 { margin-top: 24px; }
        .mb-3 { margin-bottom: 20px; }
        .mb-4 { margin-bottom: 24px; }
        .mb-0 { margin-bottom: 0; }
        .w-100 { width: 100%; }
        .text-center { text-align: center; }
        .text-primary { color: #3b82f6; }
        .text-muted { color: #94a3b8; }
        .text-white { color: white; }
        .fw-bold { font-weight: 600; }
        .bg-light { background-color: #f8fafc !important; }
        .border { border: 1px solid #e5e7eb !important; }
        .border-warning { border-color: #fbbf24 !important; }
        .rounded { border-radius: 6px; }
        .p-3 { padding: 16px; }
        .py-4 { padding-top: 24px; padding-bottom: 24px; }
        .py-5 { padding-top: 32px; padding-bottom: 32px; }
        .h-100 { height: 100%; }
        .d-flex { display: flex; }
        .justify-content-between { justify-content: space-between; }
        .align-items-center { align-items: center; }
        
        .row {
            display: flex;
            flex-wrap: wrap;
            margin: 0 -12px;
        }
        
        .col-12 {
            flex: 0 0 100%;
            max-width: 100%;
            padding: 0 12px;
        }
        
        .col-md-4 {
            flex: 0 0 33.333%;
            max-width: 33.333%;
            padding: 0 12px;
        }
        
        .col-md-5 {
            flex: 0 0 41.666%;
            max-width: 41.666%;
            padding: 0 12px;
        }
        
        .col-md-2 {
            flex: 0 0 16.666%;
            max-width: 16.666%;
            padding: 0 12px;
        }
        
        .col-md-6 {
            flex: 0 0 50%;
            max-width: 50%;
            padding: 0 12px;
        }
        
        .col-md-8 {
            flex: 0 0 66.666%;
            max-width: 66.666%;
            padding: 0 12px;
        }
        
        .col-lg-4 {
            flex: 0 0 33.333%;
            max-width: 33.333%;
            padding: 0 12px;
        }
        
        .g-3 { gap: 16px; }
        
        .table-responsive {
            overflow-x: auto;
        }
        
        .small {
            font-size: 13px;
        }
        
        @media (max-width: 768px) {
            .col-md-4, .col-md-5, .col-md-2, .col-md-6, .col-md-8, .col-lg-4 {
                flex: 0 0 100%;
                max-width: 100%;
            }
        }
    </style>
        """
