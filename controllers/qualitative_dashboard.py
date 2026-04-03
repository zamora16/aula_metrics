# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
import json
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
    def qualitative_dashboard(self, evaluation_ids=None, embedded=None, **kwargs):
        """
        Dashboard principal de datos cualitativos.
        Muestra diferentes vistas según el rol del usuario.

        Args:
            evaluation_ids: IDs de evaluaciones separados por coma (o vacío = todas)
            embedded:       Si es 'true', devuelve solo el contenido sin wrapper HTML
        """

        # Acceso directo (no embebido) → redirigir al hub principal con la
        # sección activa. El hub carga este endpoint vía AJAX con embedded=true.
        if embedded != 'true':
            return request.redirect('/aulametrics/dashboard?section=qualitative')

        # Detectar rol del usuario (incluye allowed_group_ids para tutores)
        user = request.env.user
        role_info = self._detect_user_role(user)
        role = role_info['role']

        # ── Parsear IDs de evaluación (multi-select, mismo formato que cuantitativo) ──
        selected_eval_ids = []
        if evaluation_ids:
            try:
                selected_eval_ids = [int(e) for e in evaluation_ids.split(',') if e.strip().isdigit()]
            except (ValueError, AttributeError):
                pass

        # ── Dominio: filtro por evaluaciones seleccionadas ────────────────────
        domain = []
        if selected_eval_ids:
            domain.append(('evaluation_id', 'in', selected_eval_ids))

        filtered_domain = role_service.apply_group_filter(domain, role_info, field='academic_group_id')
        if filtered_domain is None:
            responses = request.env['aula_metrics.qualitative_response']
        else:
            responses = request.env['aula_metrics.qualitative_response'].search(
                filtered_domain,
                order='response_date desc',
                limit=QUERY_LIMIT_QUALITATIVE,
            )

        evaluations = self._get_available_evaluations(role_info)

        # Contexto base
        context = {
            'role': role,
            'evaluations': evaluations,
            'selected_evals': selected_eval_ids,
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
        context['role_info'] = role_info
        context['active_section'] = 'qualitative'
        context['css_styles'] = dashboard_styles.get_common_styles()
        context['palette_json'] = Markup(json.dumps(palette.METRICS_PALETTE[:6]))

        # Serializar wordclouds como un único JSON array para el template
        if 'wordclouds' in context:
            view_type = context.get('view_type')
            if view_type == 'management':
                # Management: wordclouds con data_by_course
                context['wordclouds_json'] = Markup(json.dumps([
                    {
                        'id': wc['id'],
                        'data': wc['data'],
                        'data_by_course': wc['data_by_course'],
                    }
                    for wc in context['wordclouds']
                ]))
            elif view_type == 'tutor':
                # Tutor: wordclouds simples (un grupo, sin desglose)
                context['wordclouds_json'] = Markup(json.dumps([
                    {
                        'id': wc['id'],
                        'data': wc['data'],
                    }
                    for wc in context['wordclouds']
                ]))
            else:
                # Counselor/admin: wordclouds con data_by_group
                context['wordclouds_json'] = Markup(json.dumps([
                    {
                        'id': wc['id'],
                        'data': wc['data'],
                        'data_by_group': wc['data_by_group'],
                    }
                    for wc in context['wordclouds']
                ]))

        return _render('aula_metrics.qualitative_dashboard_embedded', context)
    
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
        Incluye tabla de respuestas + un wordcloud por binomio (evaluación, pregunta).
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

        # Agrupar por binomio (evaluación, pregunta) preservando orden
        from collections import OrderedDict
        groups = OrderedDict()
        for r in responses:
            key = (r.evaluation_id.id, r.question_id.id)
            if key not in groups:
                groups[key] = {
                    'eval_name': r.evaluation_id.name or '',
                    'question_title': r.question_id.title or '',
                    'responses': [],
                }
            groups[key]['responses'].append(r)

        # Generar un wordcloud por grupo (con desglose por grupo académico)
        wordclouds = []
        for idx, (key, grp) in enumerate(groups.items()):
            wc_data = self._generate_wordcloud(grp['responses'])
            if not wc_data:
                continue

            # Desglose por grupo académico dentro de este binomio
            group_map = {}
            for r in grp['responses']:
                if not r.academic_group_id:
                    continue
                gid = r.academic_group_id.id
                if gid not in group_map:
                    group_map[gid] = {'group': r.academic_group_id, 'responses': []}
                group_map[gid]['responses'].append(r)

            groups_list = sorted(
                [{'id': gid, 'name': info['group'].name or 'Sin grupo'}
                 for gid, info in group_map.items()],
                key=lambda g: g['name']
            )
            data_by_group = {}
            for gid, info in group_map.items():
                gdata = self._generate_wordcloud(info['responses'])
                if gdata:
                    data_by_group[str(gid)] = gdata

            wordclouds.append({
                'id': 'wordcloud_%d' % idx,
                'eval_name': grp['eval_name'],
                'question_title': grp['question_title'],
                'data': wc_data,
                'count': len(grp['responses']),
                'groups': groups_list,
                'data_by_group': data_by_group,
            })

        return {
            'view_type': 'counselor',
            'responses': table_data,
            'wordclouds': wordclouds,
            'total_responses': len(responses),
            'responses_with_alerts': len([r for r in responses if r.has_alert_keywords])
        }
    
    def _get_tutor_data(self, responses):
        """
        Vista anónima para tutor: un wordcloud por binomio (evaluación, pregunta) +
        tabla anónima de respuestas por evaluación.
        Estructura paralela a _get_management_data, sin nivel educativo (el tutor
        solo ve su grupo) y sin filtro de curso.
        """
        from collections import OrderedDict

        # Agrupar por binomio (evaluación, pregunta) preservando orden cronológico
        groups = OrderedDict()
        for r in responses:
            key = (r.evaluation_id.id, r.question_id.id)
            if key not in groups:
                groups[key] = {
                    'eval_name': r.evaluation_id.name or '',
                    'question_title': r.question_id.title or '',
                    'responses': [],
                }
            groups[key]['responses'].append(r)

        # Generar un wordcloud por binomio (sin desglose: el tutor tiene un solo grupo)
        wordclouds = []
        for idx, (key, grp) in enumerate(groups.items()):
            wc_data = self._generate_wordcloud(grp['responses'])
            if not wc_data:
                continue
            wordclouds.append({
                'id': 'wordcloud_tutor_%d' % idx,
                'eval_name': grp['eval_name'],
                'question_title': grp['question_title'],
                'data': wc_data,
                'count': len(grp['responses']),
            })

        # Tabla de respuestas anónimas agrupada por evaluación
        responses_by_eval = OrderedDict()
        for r in responses:
            ename = r.evaluation_id.name or 'Sin evaluación'
            if ename not in responses_by_eval:
                responses_by_eval[ename] = []
            responses_by_eval[ename].append({
                'date': r.response_date.strftime('%d/%m/%Y %H:%M'),
                'response': r.response_text,
                'has_alerts': r.has_alert_keywords,
                'word_count': r.word_count,
            })

        total = len(responses)
        alerts_count = len([r for r in responses if r.has_alert_keywords])

        return {
            'view_type': 'tutor',
            'wordclouds': wordclouds,
            'responses_by_eval': responses_by_eval,
            'total_responses': total,
            'responses_with_alerts': alerts_count,
        }

    def _get_management_data(self, responses):
        """
        Vista management: un wordcloud por binomio (evaluación, pregunta) con filtro
        por nivel educativo, + tabla de respuestas anónimas por evaluación.
        Estructura paralela a _get_counselor_data pero sin nombres de alumno ni grupo.
        """
        from collections import OrderedDict

        # Agrupar por binomio (evaluación, pregunta) preservando orden cronológico
        groups = OrderedDict()
        for r in responses:
            key = (r.evaluation_id.id, r.question_id.id)
            if key not in groups:
                groups[key] = {
                    'eval_id': r.evaluation_id.id,
                    'eval_name': r.evaluation_id.name or '',
                    'question_title': r.question_id.title or '',
                    'responses': [],
                }
            groups[key]['responses'].append(r)

        # Generar un wordcloud por binomio con desglose por nivel educativo
        wordclouds = []
        for idx, (key, grp) in enumerate(groups.items()):
            wc_data = self._generate_wordcloud(grp['responses'])
            if not wc_data:
                continue

            # Desglose por nivel educativo dentro del binomio
            course_map = {}
            for r in grp['responses']:
                course = r.course_level or 'Sin clasificar'
                course_map.setdefault(course, []).append(r)

            courses_list = [{'id': c, 'name': c} for c in sorted(course_map.keys())]
            data_by_course = {}
            for course, rlist in course_map.items():
                wc = self._generate_wordcloud(rlist)
                if wc:
                    data_by_course[course] = wc

            wordclouds.append({
                'id': 'wordcloud_mgmt_%d' % idx,
                'eval_name': grp['eval_name'],
                'question_title': grp['question_title'],
                'data': wc_data,
                'count': len(grp['responses']),
                'courses': courses_list,
                'data_by_course': data_by_course,
            })

        # Tabla de respuestas anónimas agrupada por evaluación
        # { eval_name: [response_dict, ...] }
        evals_order = []
        responses_by_eval = OrderedDict()
        for r in responses:
            ename = r.evaluation_id.name or 'Sin evaluación'
            if ename not in responses_by_eval:
                evals_order.append(ename)
                responses_by_eval[ename] = []
            responses_by_eval[ename].append({
                'date': r.response_date.strftime('%d/%m/%Y %H:%M'),
                'course_level': r.course_level or 'Sin clasificar',
                'response': r.response_text,
                'has_alerts': r.has_alert_keywords,
                'word_count': r.word_count,
            })

        total = len(responses)
        alerts_count = len([r for r in responses if r.has_alert_keywords])

        return {
            'view_type': 'management',
            'wordclouds': wordclouds,
            'responses_by_eval': responses_by_eval,
            'total_responses': total,
            'responses_with_alerts': alerts_count,
        }
    
    def _generate_wordcloud(self, responses):
        return dashboard_helpers.generate_wordcloud(responses)
    
