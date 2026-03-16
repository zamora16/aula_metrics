# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request

from odoo.addons.aula_metrics.utils import dashboard_styles, role_service
from odoo.addons.aula_metrics.utils.constants import (
    ROLE_ADMIN, ROLE_COUNSELOR, ROLE_MANAGEMENT, ROLE_TUTOR,
)
from .dashboard_controller import _render

_ROLE_LABELS = {
    ROLE_ADMIN: 'Vista completa del centro — Acceso total',
    ROLE_COUNSELOR: 'Vista completa del centro — Acceso total',
    ROLE_TUTOR: 'Vista de tu grupo',
    ROLE_MANAGEMENT: 'Vista agregada del centro — Por nivel educativo',
}


class SegmentationDashboardController(http.Controller):

    @http.route('/aulametrics/segmentation/dashboard', type='http', auth='user')
    def segmentation_dashboard(self, evaluation_id=None, embedded=None, **kwargs):
        role_info = self._detect_user_role()
        model = request.env['aula_metrics.dashboard.segmentation']

        context = {
            'role': role_info['role'],
            'role_desc': _ROLE_LABELS.get(role_info['role'], ''),
            'evaluations': model.get_available_evaluations(role_info),
            'evaluation_id': int(evaluation_id) if evaluation_id else None,
            'segmentation_variables': model.get_segmentation_variables(
                role_info, evaluation_id=evaluation_id
            ),
            'css_styles': dashboard_styles.get_common_styles(),
        }

        template = (
            'aula_metrics.segmentation_dashboard_embedded'
            if embedded == 'true'
            else 'aula_metrics.segmentation_dashboard_full'
        )
        return _render(template, context)

    def _detect_user_role(self):
        """Detecta el rol del usuario actual con sus grupos académicos permitidos."""
        return role_service.get_role_info(request.env, request.env.user)
