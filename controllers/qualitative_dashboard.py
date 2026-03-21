# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
import json
from collections import Counter
import re
from markupsafe import Markup

# Importar utilidades compartidas
from odoo.addons.aula_metrics.utils import dashboard_styles, dashboard_helpers, palette, role_service
from odoo.addons.aula_metrics.utils.constants import (
    QUERY_LIMIT_QUALITATIVE, EVAL_STATES_ACTIVE,
    ROLE_ADMIN, ROLE_COUNSELOR, ROLE_MANAGEMENT, ROLE_TUTOR,
)
from .dashboard_controller import _render


class QualitativeDashboardController(http.Controller):
    
    @http.route('/aulametrics/qualitative/dashboard', type='http', auth='user')
    def qualitative_dashboard(self, evaluation_id=None, question_id=None,
                              course_level=None, group_id=None, embedded=None, **kwargs):
        """
        Dashboard principal de datos cualitativos.
        Muestra diferentes vistas según el rol del usuario.

        Args:
            evaluation_id: Filtrar por evaluación específica
            question_id:   Filtrar por pregunta específica
            course_level:  Filtrar por nivel educativo (solo counselor/admin/management)
            group_id:      Filtrar por grupo concreto (solo counselor/admin)
            embedded:      Si es 'true', devuelve solo el contenido sin wrapper HTML
        """

        # Detectar rol del usuario (incluye allowed_group_ids para tutores)
        user = request.env.user
        role_info = self._detect_user_role(user)
        role = role_info['role']

        # ── Dominio base: evaluación + pregunta ───────────────────────────────
        # Se usa para construir las listas de filtros y para las preguntas
        # disponibles; NO incluye todavía el filtro de nivel/grupo.
        base_domain = []
        if evaluation_id:
            base_domain.append(('evaluation_id', '=', int(evaluation_id)))
        if question_id:
            base_domain.append(('question_id', '=', int(question_id)))

        base_filtered = role_service.apply_group_filter(base_domain, role_info, field='academic_group_id')
        if base_filtered is None:
            base_responses = request.env['aula_metrics.qualitative_response']
        else:
            base_responses = request.env['aula_metrics.qualitative_response'].search(
                base_filtered,
                order='response_date desc',
                limit=QUERY_LIMIT_QUALITATIVE,
            )

        # ── Listas de filtros disponibles (derivadas del dominio base) ────────
        accessible_groups = base_responses.mapped('academic_group_id').sorted(key=lambda g: g.name)
        level_dict = dict(
            request.env['aula_metrics.academic_group']._fields['course_level'].selection
        )
        seen_levels = {}
        for g in accessible_groups:
            if g.course_level and g.course_level not in seen_levels:
                seen_levels[g.course_level] = level_dict.get(g.course_level, g.course_level)
        # Sorted by key (eso1, eso2, … bach1, bach2) keeps natural order
        available_levels = sorted(seen_levels.items(), key=lambda x: x[0])
        # Pass ALL accessible groups to the template; the JS cascade filters client-side
        available_groups = accessible_groups if role in [ROLE_COUNSELOR, ROLE_ADMIN] else []

        # ── Dominio completo: base + nivel/grupo ──────────────────────────────
        domain = list(base_domain)
        if course_level:
            domain.append(('academic_group_id.course_level', '=', course_level))
        if group_id:
            domain.append(('academic_group_id', '=', int(group_id)))

        filtered_domain = role_service.apply_group_filter(domain, role_info, field='academic_group_id')
        if filtered_domain is None:
            responses = request.env['aula_metrics.qualitative_response']
        else:
            responses = request.env['aula_metrics.qualitative_response'].search(
                filtered_domain,
                order='response_date desc',
                limit=QUERY_LIMIT_QUALITATIVE,
            )

        # Obtener filtros disponibles
        evaluations = self._get_available_evaluations(role_info)
        questions = self._get_available_questions(base_responses)  # usa base para no perder opciones

        # Construir contexto según rol
        context = {
            'role': role,
            'evaluations': evaluations,
            'questions': questions,
            'available_levels': available_levels,   # list of (key, label) tuples
            'available_groups': available_groups,   # recordset or []
            'evaluation_id': int(evaluation_id) if evaluation_id else None,
            'question_id': int(question_id) if question_id else None,
            'course_level': course_level or None,
            'group_id': int(group_id) if group_id else None,
        }

        # Añadir datos específicos por rol
        if role in [ROLE_COUNSELOR, ROLE_ADMIN]:
            context.update(self._get_counselor_data(responses))
        elif role == ROLE_TUTOR:
            context.update(self._get_tutor_data(responses))
        else:  # management
            context.update(self._get_management_data(responses))
        
        # Añadir valores de renderizado para QWeb
        role_labels = {
            ROLE_ADMIN: 'Vista completa identificada - Acceso total',
            ROLE_COUNSELOR: 'Vista completa identificada - Acceso total',
            ROLE_TUTOR: 'Vista de tu grupo - Respuestas anónimas',
            ROLE_MANAGEMENT: 'Vista agregada del centro - Solo estadísticas',
        }
        context['role_desc'] = role_labels.get(role, '')
        context['css_styles'] = dashboard_styles.get_common_styles()
        # Markup prevents QWeb t-out from HTML-escaping the JSON double quotes,
        # which would produce &quot; and break the inline JavaScript.
        context['wordcloud_json'] = Markup(json.dumps(context.get('wordcloud_data', [])))
        context['palette_json'] = Markup(json.dumps(palette.METRICS_PALETTE[:6]))

        template = (
            'aula_metrics.qualitative_dashboard_embedded'
            if embedded == 'true'
            else 'aula_metrics.qualitative_dashboard_full'
        )
        return _render(template, context)
    
    def _detect_user_role(self, user):
        """Detecta el rol del usuario con sus grupos académicos permitidos."""
        return role_service.get_role_info(request.env, user)
    
    def _get_available_evaluations(self, role_info):
        """Obtiene evaluaciones disponibles según rol - solo las que tienen preguntas abiertas."""
        domain = role_service.apply_group_filter(
            [('state', 'in', EVAL_STATES_ACTIVE)],
            role_info,
            field='academic_group_ids',
        )
        if domain is None:
            return []
        
        all_evaluations = request.env['aula_metrics.evaluation'].search(
            domain,
            order='date_start desc'
        )
        
        # Filtrar solo evaluaciones con preguntas de texto libre
        evaluations_with_text_questions = request.env['aula_metrics.evaluation']
        for evaluation in all_evaluations:
            # Verificar si alguna encuesta tiene preguntas de texto libre
            has_text_questions = False
            for survey in evaluation.survey_ids:
                # Buscar preguntas de tipo texto en la encuesta
                text_questions = request.env['survey.question'].sudo().search([
                    ('survey_id', '=', survey.id),
                    ('question_type', 'in', ['text_box', 'char_box'])
                ], limit=1)
                
                if text_questions:
                    has_text_questions = True
                    break
            
            if has_text_questions:
                evaluations_with_text_questions |= evaluation
        
        return evaluations_with_text_questions
    
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
                'keywords': [k.keyword for k in r.detected_keyword_ids] if r.detected_keyword_ids else [],
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
    
