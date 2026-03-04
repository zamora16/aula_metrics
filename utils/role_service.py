# -*- coding: utf-8 -*-
"""
Servicio centralizado de acceso por roles para AulaMetrics.

Este módulo es el ÚNICO lugar donde se decide:
  - Qué rol tiene un usuario y qué grupos académicos puede ver (get_role_info)
  - Cómo filtrar un dominio ORM por grupos para tutores (apply_group_filter)
  - Si un usuario puede acceder al perfil individual de un alumno (can_access_student)

Los controladores y modelos llaman a estas funciones en lugar de reimplementar
la lógica. Así, cualquier cambio en las reglas de acceso se aplica en un único lugar.
"""

from .constants import ROLE_ADMIN, ROLE_COUNSELOR, ROLE_MANAGEMENT, ROLE_TUTOR
from . import dashboard_helpers


def get_role_info(env, user):
    """
    Detecta el rol del usuario y resuelve los grupos académicos permitidos.

    Combina detect_user_role() con la resolución de allowed_group_ids para tutores,
    que requiere acceso al ORM (env). Es el punto de entrada principal para
    controladores y cualquier código que necesite saber qué puede ver el usuario.

    Args:
        env: Odoo environment (request.env o self.env)
        user: recordset res.users del usuario activo

    Returns:
        dict: role_info completo con 'allowed_group_ids' ya resuelto para tutores.
              {
                  'role': str,
                  'user_id': int,
                  'is_admin': bool,
                  'is_counselor': bool,
                  'is_management': bool,
                  'is_tutor': bool,
                  'allowed_group_ids': list[int],
                  'anonymize_students': bool,
              }
    """
    role_info = dashboard_helpers.detect_user_role(user)

    if role_info['role'] == ROLE_TUTOR:
        tutor_groups = env['aula_metrics.academic_group'].search([
            ('tutor_id', '=', user.id)
        ])
        role_info['allowed_group_ids'] = tutor_groups.ids

    return role_info


def apply_group_filter(domain, role_info, field='academic_group_id'):
    """
    Añade el filtro de grupos académicos al dominio ORM para tutores.

    Para roles con acceso global (admin, counselor, management) devuelve el
    dominio sin cambios. Para tutores, restringe al conjunto de grupos asignados.
    Si el tutor no tiene grupos asignados devuelve None — la convención es que
    el caller retorne una colección vacía inmediatamente:

        domain = role_service.apply_group_filter(domain, role_info)
        if domain is None:
            return []  # o recordset vacío, según el caller

    Args:
        domain (list): Dominio ORM existente (puede estar vacío: [])
        role_info (dict): Resultado de get_role_info()
        field (str): Campo del modelo al que aplicar el filtro.
                     Por defecto 'academic_group_id'; usar 'id' al filtrar el
                     propio modelo academic_group, o 'academic_group_ids' para
                     relaciones M2M como en evaluation.

    Returns:
        list | None: Dominio ampliado, o None si el tutor no tiene grupos asignados.
    """
    if role_info.get('role') != ROLE_TUTOR:
        return domain

    allowed_groups = role_info.get('allowed_group_ids', [])
    if not allowed_groups:
        return None  # Sin grupos → sin acceso

    return domain + [(field, 'in', allowed_groups)]


def can_access_student(role_info, student):
    """
    Decide si el rol actual puede acceder al perfil individual de un alumno.

    Reglas:
      - admin / counselor → acceso total
      - management        → sin acceso (ve solo datos agregados)
      - tutor             → solo alumnos de sus grupos asignados

    Args:
        role_info (dict): Resultado de get_role_info()
        student: recordset res.partner del alumno

    Returns:
        bool: True si tiene acceso, False si no.
    """
    role = role_info.get('role', ROLE_TUTOR)

    if role in (ROLE_ADMIN, ROLE_COUNSELOR):
        return True

    if role == ROLE_MANAGEMENT:
        return False

    if role == ROLE_TUTOR:
        allowed_groups = role_info.get('allowed_group_ids', [])
        student_group = student.academic_group_id.id if student.academic_group_id else None
        return student_group in allowed_groups

    return False
