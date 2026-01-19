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

    @api.depends('evaluation_id.participation_ids.state',
                 'evaluation_id.participation_ids.who5_score',
                 'evaluation_id.participation_ids.bullying_score',
                 'evaluation_id.participation_ids.stress_score')
    def _compute_statistics(self):
        """Calcula estadísticas agregadas de las participaciones completadas."""
        for report in self:
            participations = report.evaluation_id.participation_ids.filtered(
                lambda p: p.state == 'completed'
            )
            
            if not participations:
                report.avg_who5 = 0
                report.avg_bullying = 0
                report.avg_stress = 0
                continue

            # Calcular promedios solo de valores no nulos
            who5_scores = [p.who5_score for p in participations if p.who5_score]
            bullying_scores = [p.bullying_score for p in participations if p.bullying_score]
            stress_scores = [p.stress_score for p in participations if p.stress_score]

            report.avg_who5 = sum(who5_scores) / len(who5_scores) if who5_scores else 0
            report.avg_bullying = sum(bullying_scores) / len(bullying_scores) if bullying_scores else 0
            report.avg_stress = sum(stress_scores) / len(stress_scores) if stress_scores else 0

    def action_view_participations(self):
        """Abre las participaciones completadas de esta evaluación con vista de puntuaciones."""
        self.ensure_one()

        # Determinar qué campos de puntuación mostrar basándose en los surveys incluidos
        survey_codes = self.evaluation_id.survey_ids.mapped('survey_code')

        # Crear vista tree dinámica con solo los campos relevantes
        view_arch = """<tree string="Puntuaciones"
                      decoration-success="state == 'completed'"
                      decoration-warning="state == 'pending'"
                      decoration-danger="state == 'expired'"
                      create="false" delete="false">
                <field name="student_id"/>
                <field name="academic_group_id"/>"""

        # Añadir campos dinámicamente basados en SURVEY_METRICS
        for survey_code, survey_config in SURVEY_METRICS.items():
            if survey_code in survey_codes:
                for field_name in survey_config['fields']:
                    label = survey_config['labels'].get(field_name, field_name)
                    view_arch += f'<field name="{field_name}" string="{label}"/>'

        view_arch += """<field name="state" widget="badge"
                       decoration-success="state == 'completed'"
                       decoration-warning="state == 'pending'"
                       decoration-danger="state == 'expired'"/>
                <field name="completed_at"/>
            </tree>"""

        # Crear vista temporal
        view = self.env['ir.ui.view'].create({
            'name': f'participation_scores_{self.evaluation_id.id}',
            'model': 'aulametrics.participation',
            'type': 'tree',
            'arch': view_arch,
            'active': False,  # Vista temporal
        })

        return {
            'name': f'Puntuaciones: {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'aulametrics.participation',
            'view_mode': 'tree',
            'views': [(view.id, 'tree')],
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
