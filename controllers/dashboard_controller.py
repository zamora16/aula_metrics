# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request


class DashboardChartsController(http.Controller):
    """Controlador para dashboard interactivo."""

    @http.route('/aulametrics/dashboard/<int:evaluation_id>', type='http', auth='user')
    def dashboard_view(self, evaluation_id):
        """Genera y retorna el dashboard completo con todos los gráficos."""
        html_content = request.env['aulametrics.dashboard.charts'].generate_dashboard(evaluation_id)
        
        return request.make_response(
            html_content,
            headers=[('Content-Type', 'text/html; charset=utf-8')]
        )

