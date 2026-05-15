# -*- coding: utf-8 -*-

from . import controllers
from . import models
from . import wizards
from . import utils


def _setup_indexes_and_lang(env):
    """Crea índices de rendimiento y activa el idioma Valencià con sus traducciones."""
    # Índices de rendimiento
    cr = env.cr
    indexes = [
        ("idx_participation_eval_state",
         "aulametrics_participation", "(evaluation_id, state)"),
        ("idx_metric_value_student_name",
         "aula_metrics_metric_value", "(student_id, metric_name)"),
        ("idx_alert_student_status",
         "aulametrics_alert", "(student_id, status)"),
        ("idx_survey_result_student_survey",
         "aula_metrics_survey_result", "(student_id, survey_id)"),
        ("idx_qualitative_eval_keywords",
         "aula_metrics_qualitative_response", "(evaluation_id, has_alert_keywords)"),
    ]
    for name, table, columns in indexes:
        cr.execute(
            f"CREATE INDEX IF NOT EXISTS {name} ON {table} {columns}"
        )

    # Activar idioma Valencià y cargar traducciones del módulo automáticamente
    env['res.lang']._activate_lang('ca_ES')
    module = env['ir.module.module'].search([('name', '=', 'aula_metrics')], limit=1)
    if module:
        module._update_translations('ca_ES')


def _set_client_home_action(env):
    """Asigna el dashboard de AulaMetrics como pantalla de inicio
    para todos los usuarios con roles cliente (tutor, orientador, dirección)."""
    action = env.ref('aula_metrics.action_dashboard_home', raise_if_not_found=False)
    if not action:
        return
    admin_group = env.ref('base.group_system')
    client_group_xmlids = [
        'aula_metrics.group_aulametrics_tutor',
        'aula_metrics.group_aulametrics_counselor',
        'aula_metrics.group_aulametrics_management',
    ]
    for xmlid in client_group_xmlids:
        group = env.ref(xmlid, raise_if_not_found=False)
        if not group:
            continue
        client_users = group.users.filtered(lambda u: admin_group not in u.groups_id)
        if client_users:
            client_users.write({'action_id': action.id})


def _post_init_create_indexes(env):
    """Hook de post-instalación."""
    _setup_indexes_and_lang(env)
    _set_client_home_action(env)
