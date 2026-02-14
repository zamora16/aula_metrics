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

    @http.route('/aulametrics/students', type='http', auth='user')
    def students_list_view(self, **kwargs):
        """
        Lista de estudiantes en formato HTML estilo dashboard.
        
        Acceso según rol:
        - Counselor/Admin: todos los alumnos
        - Tutor: solo alumnos de sus grupos
        - Management: bloqueado
        """
        role_info = self._detect_user_role()
        
        # Management no tiene acceso a perfiles individuales
        if role_info.get('role') == 'management':
            return request.make_response(
                "<h1>Acceso Denegado</h1><p>El equipo directivo no tiene acceso a perfiles individuales de alumnos.</p>",
                headers=[('Content-Type', 'text/html; charset=utf-8')],
                status=403
            )
        
        # Generar lista HTML de estudiantes
        html_content = request.env['aulametrics.dashboard.student_profile'].generate_students_list(
            role_info=role_info
        )
        
        return request.make_response(
            html_content,
            headers=[('Content-Type', 'text/html; charset=utf-8')]
        )

    @http.route('/aulametrics/student/<int:student_id>', type='http', auth='user')
    def student_profile_view(self, student_id, **kwargs):
        """
        Dashboard individual de alumno con visión longitudinal.
        
        Acceso según rol:
        - Counselor/Admin: todos los alumnos
        - Tutor: solo alumnos de sus grupos
        - Management: bloqueado
        
        Args:
            student_id: ID del res.partner con student=True
        """
        role_info = self._detect_user_role()
        
        # Verificar que el ID corresponde a un estudiante
        student = request.env['res.partner'].sudo().search([
            ('id', '=', student_id),
            ('is_student', '=', True)
        ], limit=1)
        
        if not student:
            return request.not_found(description="El estudiante solicitado no existe.")
        
        # Delegar validación de acceso y generación al modelo
        try:
            html_content = request.env['aulametrics.dashboard.student_profile'].generate_student_profile(
                student_id=student_id,
                role_info=role_info
            )
            
            return request.make_response(
                html_content,
                headers=[('Content-Type', 'text/html; charset=utf-8')]
            )
        except Exception as e:
            # Capturar errores de permisos o generación
            error_msg = str(e)
            if 'permiso' in error_msg.lower() or 'access' in error_msg.lower():
                return request.not_found(description=error_msg)
            else:
                # Error genérico
                return request.make_response(
                    f"<h1>Error al generar el perfil</h1><p>{error_msg}</p>",
                    headers=[('Content-Type', 'text/html; charset=utf-8')],
                    status=500
                )

    def _parse_hub_filters(self, kwargs):
        """Parsea los parámetros GET a un dict de filtros (SIMPLIFICADO: solo evaluaciones)."""
        filters = {
            'evaluation_ids': [],
        }

        # Solo evaluaciones (filtro maestro del que se derivan métricas y grupos)
        if kwargs.get('evaluation_ids'):
            try:
                filters['evaluation_ids'] = [int(e) for e in kwargs['evaluation_ids'].split(',') if e.strip().isdigit()]
            except (ValueError, AttributeError):
                pass

        return filters

    def _apply_role_restrictions(self, filters, role_info):
        """
        Aplica restricciones de rol a los filtros.
        Con el sistema simplificado (solo filtro de evaluaciones), 
        ya no es necesario filtrar por grupos aquí.
        Las restricciones de rol se aplican a nivel de modelo.
        """
        # El método ahora es pass-through
        # Las restricciones de datos por rol se manejan en el modelo generate_dashboard()
        return filters

