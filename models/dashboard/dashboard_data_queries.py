# -*- coding: utf-8 -*-
"""
Dashboard Data Queries - Consultas y preparación de datos para dashboards
"""
import logging
from odoo import models, api
import pandas as pd
from ...utils import role_service, dashboard_helpers
from ...utils.constants import ROLE_TUTOR, EVAL_STATES_ACTIVE, QUERY_LIMIT_METRIC_VALUES

_logger = logging.getLogger(__name__)


class DashboardDataQueries(models.Model):
    """Clase para centralizar todas las consultas de datos del dashboard"""

    _name = 'aula_metrics.dashboard.data_queries'
    _description = 'Consultas de datos para dashboards'

    @api.model
    def get_available_metrics(self, filters, role_info):
        """Obtiene las métricas únicas disponibles en metric_value."""
        MetricValue = self.env['aula_metrics.metric_value']

        # Filtrar por grupos según rol
        domain = role_service.apply_group_filter([], role_info, field='academic_group_id')
        if domain is None:
            return []  # Tutor sin grupos asignados

        # Filtrar por evaluaciones si se especifica
        if filters.get('evaluation_ids'):
            domain.append(('evaluation_id', 'in', filters['evaluation_ids']))
        elif filters.get('academic_year_id'):
            domain.append(('academic_year_id', '=', filters['academic_year_id']))

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
            if name in seen:
                continue
            seen.add(name)

            label = r.get('metric_label', name.replace('_', ' ').capitalize())

            # Detectar tipo de métrica basado en el nombre
            metric_type = 'percentage'
            if any(keyword in name.lower() for keyword in ['count', 'total', 'number']):
                metric_type = 'count'
            elif any(keyword in name.lower() for keyword in ['avg', 'average', 'mean']):
                metric_type = 'average'

            metrics.append({
                'name': name,
                'label': label,
                'type': metric_type,
            })

        return metrics

    @api.model
    def get_available_groups(self, filters, role_info):
        """Obtiene los grupos académicos disponibles según rol."""
        try:
            AcademicGroup = self.env['aula_metrics.academic_group']

            domain = role_service.apply_group_filter(
                [('active', '=', True)],
                role_info,
                field='id',
            )
            if domain is None:
                return []

            # Filtrar por evaluaciones si se especifica
            if filters.get('evaluation_ids'):
                # Obtener IDs de grupos con métricas usando read_group (sin cargar registros)
                rows = self.env['aula_metrics.metric_value'].read_group(
                    [
                        ('evaluation_id', 'in', filters['evaluation_ids']),
                        ('academic_group_id', '!=', False),
                    ],
                    ['academic_group_id'],
                    ['academic_group_id'],
                )
                valid_group_ids = [r['academic_group_id'][0] for r in rows if r.get('academic_group_id')]
                if valid_group_ids:
                    domain.append(('id', 'in', valid_group_ids))
                else:
                    return []
            elif filters.get('academic_year_id'):
                domain.append(('academic_year_id', '=', filters['academic_year_id']))

            groups = AcademicGroup.search(domain, order='name')
            return [{
                'id': g.id,
                'name': g.name,
                'course_level': g.course_level,
            } for g in groups]
        except Exception as e:
            _logger.error("Error in get_available_groups: %s", e)
            return []

    @api.model
    def get_available_evaluations(self, role_info, filters=None):
        """Obtiene las evaluaciones disponibles según rol y curso académico."""
        if filters is None:
            filters = {}
        try:
            Evaluation = self.env['aula_metrics.evaluation']

            domain = [('state', 'in', EVAL_STATES_ACTIVE)]

            # Filtro por curso académico
            if filters.get('academic_year_id'):
                domain.append(('academic_year_id', '=', filters['academic_year_id']))

            # Restricciones por rol
            if role_info.get('role') == ROLE_TUTOR:
                allowed_groups = role_info.get('allowed_group_ids', [])
                if allowed_groups:
                    # Solo evaluaciones que tienen participaciones de los grupos del tutor
                    evaluations_with_groups = Evaluation.search([
                        ('participation_ids.academic_group_id', 'in', allowed_groups)
                    ])
                    domain.append(('id', 'in', evaluations_with_groups.ids))
                else:
                    return []

            evaluations = Evaluation.search(domain, order='date_start desc')

            result = []
            for e in evaluations:
                # Exclude evaluations whose surveys contain ONLY segmentation questions.
                # Such evaluations are used purely as segmentation sources and should
                # not appear as quantitative filter options.
                all_questions = e.survey_ids.mapped('question_ids')
                if all_questions and all(q.is_segmentation for q in all_questions):
                    continue
                result.append({
                    'id': e.id,
                    'name': e.name,
                    'date_start': e.date_start,
                    'date_end': e.date_end,
                    'state': e.state,
                })
            return result
        except Exception as e:
            _logger.error("Error in get_available_evaluations: %s", e)
            return []

    @api.model
    def query_metric_values(self, filters, role_info):
        """Consulta los valores de métricas según filtros."""
        MetricValue = self.env['aula_metrics.metric_value']
        
        domain = role_service.apply_group_filter([], role_info, field='academic_group_id')
        if domain is None:
            return self.env['aula_metrics.metric_value']  # Tutor sin grupos → vacío

        # Filtros de evaluación
        if filters.get('evaluation_ids'):
            domain.append(('evaluation_id', 'in', filters['evaluation_ids']))
        elif filters.get('academic_year_id'):
            domain.append(('academic_year_id', '=', filters['academic_year_id']))
        
        return MetricValue.search(domain, limit=QUERY_LIMIT_METRIC_VALUES)

    @api.model
    def prepare_dataframe(self, metric_values, role_info):
        """
        Construye el DataFrame del dashboard agregado (cross-grupo) a partir de
        un recordset de aula_metrics.metric_value.

        La conversión de registros se delega en
        dashboard_helpers.metric_values_to_records, que es el único lugar donde
        vive la lógica de detección de tipo y normalización de columnas.
        """
        if not metric_values:
            return pd.DataFrame()
        return pd.DataFrame(dashboard_helpers.metric_values_to_records(metric_values))

    @api.model
    def get_segmentation_variables(self, filters, role_info):
        """Obtiene variables de segmentación disponibles dinámicamente.

        Returns gender (from res.partner) plus any survey question with
        is_segmentation=True that has actual metric_value records stored
        via _save_multiplechoice_responses() (metric_name='question_<id>_choices').
        """
        variables = [
            {
                'value': 'gender',
                'label': 'Género',
                'type': 'partner_field',
                'options': ['Masculino', 'Femenino', 'Otro', 'Prefiere no decir'],
            }
        ]

        try:
            seg_questions = self.env['survey.question'].search(
                [('is_segmentation', '=', True)]
            )
            for question in seg_questions:
                metric_name = f'question_{question.id}_choices'

                # Only include if there are actual records (respecting role filter)
                domain = role_service.apply_group_filter(
                    [('metric_name', '=', metric_name), ('value_json', '!=', False)],
                    role_info,
                    field='academic_group_id',
                )
                if domain is None:
                    continue

                # Do NOT filter by evaluation_ids here: segmentation data lives in
                # segmentation-only evaluations (excluded from the quantitative filter)
                # and must remain available regardless of which evaluations are selected.

                if not self.env['aula_metrics.metric_value'].search_count(domain):
                    continue

                # Derive available options from the answer choices defined on the question
                options = [
                    ans.value or ans.name
                    for ans in question.suggested_answer_ids
                    if ans.value or ans.name
                ]

                variables.append({
                    'value': metric_name,
                    'label': question.metric_label or question.title or metric_name,
                    'type': 'metric_json',
                    'options': options,
                })
        except Exception as e:
            _logger.error("Error building segmentation variables: %s", e)

        return variables
