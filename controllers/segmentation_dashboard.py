# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request

from odoo.addons.aula_metrics.utils import dashboard_styles
from odoo.addons.aula_metrics.utils.constants import ROLE_LABELS
from .base import AulaMetricsBaseController
from .dashboard_controller import _render


class SegmentationDashboardController(AulaMetricsBaseController):

    @http.route('/aulametrics/segmentation/dashboard', type='http', auth='user')
    def segmentation_dashboard(self, evaluation_ids=None, embedded=None, **kwargs):
        role_info = self._detect_user_role()
        model = request.env['aula_metrics.dashboard.segmentation']

        selected_eval_ids = []
        if evaluation_ids:
            try:
                selected_eval_ids = [int(e) for e in evaluation_ids.split(',') if e.strip().isdigit()]
            except (ValueError, AttributeError):
                pass

        context = {
            'role': role_info['role'],
            'role_info': role_info,
            'active_section': 'segmentation',
            'role_desc': ROLE_LABELS.get(role_info['role'], ''),
            'evaluations': model.get_available_evaluations(role_info),
            'selected_evals': selected_eval_ids,
            'segmentation_variables': model.get_segmentation_variables(
                role_info, evaluation_ids=selected_eval_ids or None
            ),
            'css_styles': dashboard_styles.get_common_styles(),
        }

        template = (
            'aula_metrics.segmentation_dashboard_embedded'
            if embedded == 'true'
            else 'aula_metrics.segmentation_dashboard_full'
        )
        return _render(template, context)

