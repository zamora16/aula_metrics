# -*- coding: utf-8 -*-
from odoo import models, fields, api

# Importar configuración centralizada
from .survey_config import SURVEY_METRICS


class Report(models.Model):
    """
    Reporte de resultados de una evaluación.
    Centraliza el acceso a las puntuaciones de una evaluación específica.
    """
    _name = 'aulametrics.report'
    _description = 'Reporte de Evaluación'
    _order = 'create_date desc'

    # Relación principal con evaluación (1:1)
    evaluation_id = fields.Many2one(
        'aulametrics.evaluation',
        string='Evaluación',
        required=True,
        ondelete='cascade',
        index=True
    )

    # Campos related para acceso directo (store=True para búsquedas y ordenación)
    name = fields.Char(
        related='evaluation_id.name',
        string='Nombre',
        store=True
    )
    state = fields.Selection(
        related='evaluation_id.state',
        string='Estado',
        store=True
    )
    completion_rate = fields.Float(
        related='evaluation_id.participation_rate',
        string='% Completado'
    )

    # Estadísticas agregadas (computed)
    avg_who5 = fields.Float(
        string='Media WHO-5',
        compute='_compute_statistics',
        digits=(5, 1)
    )
    avg_bullying = fields.Float(
        string='Media Bullying',
        compute='_compute_statistics',
        digits=(5, 1)
    )
    avg_stress = fields.Float(
        string='Media Estrés',
        compute='_compute_statistics',
        digits=(5, 1)
    )

    # Indicadores de surveys incluidos
    has_who5 = fields.Boolean(
        related='evaluation_id.has_who5',
        string='Incluye WHO-5',
        store=True
    )
    has_bullying = fields.Boolean(
        related='evaluation_id.has_bullying',
        string='Incluye Bullying',
        store=True
    )
    has_stress = fields.Boolean(
        related='evaluation_id.has_stress',
        string='Incluye Estrés',
        store=True
    )

    @api.depends('evaluation_id.participation_ids.state')
    def _compute_statistics(self):
        """Calcula estadísticas agregadas desde metric_value."""
        for report in self:
            participations = report.evaluation_id.participation_ids.filtered(
                lambda p: p.state == 'completed'
            )
            
            if not participations:
                report.avg_who5 = 0
                report.avg_bullying = 0
                report.avg_stress = 0
                continue

            # Obtener métricas desde metric_value
            MetricValue = self.env['aulametrics.metric_value']
            
            who5_metrics = MetricValue.search([
                ('evaluation_id', '=', report.evaluation_id.id),
                ('metric_name', '=', 'who5_score')
            ])
            bullying_metrics = MetricValue.search([
                ('evaluation_id', '=', report.evaluation_id.id),
                ('metric_name', '=', 'bullying_score')
            ])
            stress_metrics = MetricValue.search([
                ('evaluation_id', '=', report.evaluation_id.id),
                ('metric_name', '=', 'stress_score')
            ])

            who5_values = [m.value_float for m in who5_metrics if m.value_float]
            bullying_values = [m.value_float for m in bullying_metrics if m.value_float]
            stress_values = [m.value_float for m in stress_metrics if m.value_float]

            report.avg_who5 = sum(who5_values) / len(who5_values) if who5_values else 0
            report.avg_bullying = sum(bullying_values) / len(bullying_values) if bullying_values else 0
            report.avg_stress = sum(stress_values) / len(stress_values) if stress_values else 0

    def action_view_participations(self):
        """Abre las participaciones completadas de esta evaluación."""
        self.ensure_one()

        # Vista simplificada - las métricas ahora están en metric_value
        return {
            'name': f'Participaciones: {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'aulametrics.participation',
            'view_mode': 'tree,form',
            'domain': [
                ('evaluation_id', '=', self.evaluation_id.id),
                ('state', '=', 'completed')
            ],
            'context': {
                'create': False,
                'delete': False,
            },
        }

    def action_open_interactive_dashboard(self):
        """Abre el dashboard interactivo con gráficos Plotly."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': f'/aulametrics/dashboard/{self.evaluation_id.id}',
            'target': 'new',
        }
