# -*- coding: utf-8 -*-
"""
Controlador base para AulaMetrics.

Define comportamiento compartido por todos los controladores del módulo:
- Detección del rol del usuario (_detect_user_role)

Los controladores concretos heredan de AulaMetricsBaseController en lugar
de reimplementar esta lógica.
"""
from odoo import http
from odoo.http import request
from odoo.addons.aula_metrics.utils import role_service


class AulaMetricsBaseController(http.Controller):

    def _detect_user_role(self):
        """Detecta el rol del usuario actual con sus grupos académicos permitidos.

        Jerarquía: admin > counselor > management > tutor.
        Delega a role_service, que es la única fuente de verdad sobre roles.

        Returns:
            dict: role_info con claves role, user_id, allowed_group_ids, etc.
        """
        return role_service.get_role_info(request.env, request.env.user)
