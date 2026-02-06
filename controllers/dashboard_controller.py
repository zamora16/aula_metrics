# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
from datetime import datetime, timedelta


class DashboardChartsController(http.Controller):
    """Controlador para dashboard interactivo con filtros de rol."""

    def _detect_user_role(self):
        """
        Detecta el rol del usuario actual en AulaMetrics.
        Retorna un dict con el rol y los group_ids permitidos.
        Jerarquía: admin > counselor > management > tutor
        """
        user = request.env.user
        role_info = {
            'role': 'tutor',  # Default más restrictivo
            'user_id': user.id,
            'is_admin': False,
            'is_counselor': False,
            'is_management': False,
            'is_tutor': False,
            'allowed_group_ids': [],  # IDs de academic_group permitidos
            'anonymize_students': False,  # Management no ve nombres individuales
        }

        if user.has_group('aula_metrics.group_aulametrics_admin'):
            role_info.update({
                'role': 'admin',
                'is_admin': True,
                'is_counselor': True,  # admin implies counselor
                'is_management': True,  # admin implies management
                'is_tutor': True,  # admin implies tutor
            })
        elif user.has_group('aula_metrics.group_aulametrics_counselor'):
            role_info.update({
                'role': 'counselor',
                'is_counselor': True,
                'is_tutor': True,  # counselor implies tutor
            })
        elif user.has_group('aula_metrics.group_aulametrics_management'):
            role_info.update({
                'role': 'management',
                'is_management': True,
                'is_tutor': True,  # management implies tutor
                'anonymize_students': True,  # Management ve datos agregados, no individuales
            })
        else:
            role_info['is_tutor'] = True

        # Para tutores (no counselor/admin), restringir a sus grupos asignados
        if role_info['role'] == 'tutor':
            tutor_groups = request.env['aulametrics.academic_group'].search([
                ('tutor_id', '=', user.id)
            ])
            role_info['allowed_group_ids'] = tutor_groups.ids

        return role_info

    @http.route('/aulametrics/dashboard', type='http', auth='user')
    def dashboard_view(self, **kwargs):
        """
        Dashboard principal con filtros dinámicos.
        
        Parámetros GET:
        - metric_names: lista CSV de nombres de métricas
        - date_from: fecha inicio formato YYYY-MM-DD
        - date_to: fecha fin formato YYYY-MM-DD
        - group_ids: lista CSV de IDs de grupos académicos
        - evaluation_ids: lista CSV de IDs de evaluaciones
        """
        role_info = self._detect_user_role()

        # Parsear parámetros de filtro
        filters = self._parse_hub_filters(kwargs)
        
        # Aplicar restricciones de rol a los filtros
        filters = self._apply_role_restrictions(filters, role_info)

        html_content = request.env['aulametrics.dashboard.charts'].generate_dashboard(
            filters=filters, 
            role_info=role_info
        )

        return request.make_response(
            html_content,
            headers=[('Content-Type', 'text/html; charset=utf-8')]
        )

    def _parse_hub_filters(self, kwargs):
        """Parsea los parámetros GET a un dict de filtros."""
        filters = {
            'metric_names': [],
            'date_from': None,
            'date_to': None,
            'group_ids': [],
            'evaluation_ids': [],
        }

        # Métricas
        if kwargs.get('metric_names'):
            filters['metric_names'] = [m.strip() for m in kwargs['metric_names'].split(',') if m.strip()]

        # Fechas
        if kwargs.get('date_from'):
            try:
                filters['date_from'] = datetime.strptime(kwargs['date_from'], '%Y-%m-%d').date()
            except ValueError:
                pass
        if kwargs.get('date_to'):
            try:
                filters['date_to'] = datetime.strptime(kwargs['date_to'], '%Y-%m-%d').date()
            except ValueError:
                pass

        # Grupos e evaluaciones (IDs enteros)
        if kwargs.get('group_ids'):
            try:
                filters['group_ids'] = [int(g) for g in kwargs['group_ids'].split(',') if g.strip().isdigit()]
            except (ValueError, AttributeError):
                pass
        if kwargs.get('evaluation_ids'):
            try:
                filters['evaluation_ids'] = [int(e) for e in kwargs['evaluation_ids'].split(',') if e.strip().isdigit()]
            except (ValueError, AttributeError):
                pass

        return filters

    def _apply_role_restrictions(self, filters, role_info):
        """Aplica restricciones de rol a los filtros."""
        role = role_info.get('role', 'tutor')

        # Para tutores, forzar filtro a sus grupos permitidos
        if role == 'tutor':
            allowed = role_info.get('allowed_group_ids', [])
            if allowed:
                if filters['group_ids']:
                    # Intersección: solo grupos que el tutor tiene permitidos Y que solicitó
                    filters['group_ids'] = list(set(filters['group_ids']) & set(allowed))
                else:
                    # Sin filtro específico: mostrar todos sus grupos
                    filters['group_ids'] = allowed
            else:
                # Tutor sin grupos asignados: sin datos
                filters['group_ids'] = [-1]  # ID imposible para forzar resultado vacío

        return filters

