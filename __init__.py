# -*- coding: utf-8 -*-

from . import controllers
from . import models
from . import wizards
from . import utils


def _post_init_create_indexes(env):
    """Crea índices compuestos de rendimiento en instalación nueva."""
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
