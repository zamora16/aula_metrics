# -*- coding: utf-8 -*-
"""
Dashboard Data Queries - Consultas y preparación de datos para dashboards
"""
import logging
from odoo import models, api
import pandas as pd
from ...utils import role_service, dashboard_helpers
from ...utils.constants import ROLE_TUTOR, EVAL_STATES_ACTIVE

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
                # Solo grupos que tienen evaluaciones con métricas
                groups_with_data = self.env['aula_metrics.metric_value'].search([
                    ('evaluation_id', 'in', filters['evaluation_ids'])
                ]).mapped('academic_group_id')
                # Filtrar grupos válidos (no None)
                valid_group_ids = [g.id for g in groups_with_data if g]
                if valid_group_ids:
                    domain.append(('id', 'in', valid_group_ids))
                else:
                    # Si no hay grupos válidos, retornar lista vacía
                    return []

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
    def get_available_evaluations(self, role_info):
        """Obtiene las evaluaciones disponibles según rol."""
        try:
            Evaluation = self.env['aula_metrics.evaluation']

            domain = [('state', 'in', EVAL_STATES_ACTIVE)]

            # Restricciones por rol
            if role_info.get('role') == ROLE_TUTOR:
                allowed_groups = role_info.get('allowed_group_ids', [])
                if allowed_groups:
                    # Solo evaluaciones que incluyen grupos del tutor
                    evaluations_with_groups = Evaluation.search([
                        ('survey_ids.participation_ids.academic_group_id', 'in', allowed_groups)
                    ])
                    domain.append(('id', 'in', evaluations_with_groups.ids))
                else:
                    return []

            evaluations = Evaluation.search(domain, order='date_start desc')
            return [{
                'id': e.id,
                'name': e.name,
                'date_start': e.date_start,
                'date_end': e.date_end,
                'state': e.state,
            } for e in evaluations]
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
        
        return MetricValue.search(domain)

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
        """Obtiene variables de segmentación disponibles dinámicamente."""
        try:
            variables = []
            
            # 1. Género (siempre disponible desde res.partner)
            variables.append({
                'value': 'gender',
                'label': 'Género',
                'type': 'partner_field',
                'options': ['Masculino', 'Femenino', 'Otro', 'Prefiere no decir']
            })
            
            return variables
        except Exception as e:
            _logger.error("Error in get_segmentation_variables: %s", e)
            return [{
                'value': 'gender',
                'label': 'Género',
                'type': 'partner_field',
                'options': ['Masculino', 'Femenino', 'Otro', 'Prefiere no decir']
            }]
