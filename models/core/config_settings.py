# -*- coding: utf-8 -*-
from odoo import models, fields, api

PARAM_KEY = 'aula_metrics.enable_centro_surveys'
_MENU_XMLID = 'aula_metrics.menu_aulametrics_surveys_adhoc'


class AulaMetricsSettings(models.TransientModel):
    """
    Ajustes del módulo AulaMetrics accesibles desde Ajustes → AulaMetrics.
    """
    _inherit = 'res.config.settings'

    enable_centro_surveys = fields.Boolean(
        string='Activar cuestionarios del centro',
        help=(
            'Permite crear cuestionarios personalizados no-oficiales y ver sus '
            'resultados en dashboards y reportes.\n'
            'Desactivado por defecto — actívalo solo cuando el centro esté '
            'preparado para usarlos.'
        ),
    )

    def set_values(self):
        super().set_values()
        enabled = self.enable_centro_surveys
        self.env['ir.config_parameter'].sudo().set_param(PARAM_KEY, str(enabled))
        # Activar/desactivar el menú directamente — efecto inmediato tras recargar
        menu = self.env.ref(_MENU_XMLID, raise_if_not_found=False)
        if menu:
            menu.sudo().write({'active': enabled})

    @api.model
    def get_values(self):
        res = super().get_values()
        param = self.env['ir.config_parameter'].sudo().get_param(PARAM_KEY, 'False')
        res['enable_centro_surveys'] = param == 'True'
        return res
