# -*- coding: utf-8 -*-
"""
Funciones auxiliares compartidas para dashboards de AulaMetrics
Incluye: formatters, sanitizers, chart helpers, detección de roles.
"""
from datetime import datetime
import json
from .constants import (
    GROUP_ADMIN, GROUP_COUNSELOR, GROUP_MANAGEMENT,
    ROLE_ADMIN, ROLE_COUNSELOR, ROLE_MANAGEMENT,
)


def format_date(date_obj, format_str='%d/%m/%Y'):
    """
    Formatea una fecha de manera consistente.

    Args:
        date_obj: Objeto date/datetime o string
        format_str (str): Formato de salida

    Returns:
        str: Fecha formateada
    """
    if not date_obj:
        return 'Sin fecha'

    if isinstance(date_obj, str):
        try:
            date_obj = datetime.strptime(date_obj, '%Y-%m-%d')
        except (ValueError, TypeError):
            return date_obj

    try:
        return date_obj.strftime(format_str)
    except (AttributeError, TypeError):
        return str(date_obj)


def format_date_range(date_start, date_end):
    """
    Formatea un rango de fechas como "DD/MM/YYYY - DD/MM/YYYY".
    """
    return f"{format_date(date_start, '%d/%m/%Y')} - {format_date(date_end, '%d/%m/%Y')}"


def format_participation_rate(rate):
    """
    Formatea un porcentaje de participación como "XX.X%".
    """
    try:
        return f"{float(rate):.1f}%"
    except (ValueError, TypeError):
        return "0.0%"


def sanitize_id(text):
    """
    Sanitiza un texto para usarlo como ID HTML válido.
    """
    return (
        text.replace(' ', '_').replace('/', '_')
            .replace('.', '_').replace('(', '').replace(')', '')
    )


# ==================== CHART HELPERS ====================

def get_segment_colors_js():
    """
    Retorna el objeto JavaScript de colores para segmentación por género.
    Usa los valores definidos en `utils.palette` como única fuente de verdad.
    """
    from . import palette
    seg = palette.SEGMENT_COLORS
    default = palette.DEFAULT_PALETTE
    return (
        "const segmentColors = {\n"
        f"  'Masculino': '{seg['Masculino']}',\n"
        f"  'Femenino': '{seg['Femenino']}',\n"
        f"  'Otro': '{seg['Otro']}',\n"
        f"  'Prefiere no decir': '{seg['Prefiere no decir']}',\n"
        f"  'default': {json.dumps(default)}\n"
        "};"
    )


def get_chart_card_styles():
    """
    Retorna los estilos CSS inline para los headers de chart cards.
    """
    return {
        'chart-card-header': (
            'display: flex; justify-content: space-between; align-items: center; '
            'flex-wrap: wrap; gap: 12px;'
        ),
        'chart-segment-selector': (
            'padding: 6px 12px; background: var(--am-bg); border: 1px solid var(--am-border); '
            'border-radius: 6px; cursor: pointer; font-size: 12px; color: var(--am-muted); '
            'font-weight: 500; min-width: 160px;'
        ),
    }


# ==================== ROLE & DATA HELPERS ====================

def detect_user_role(user):
    """
    Detecta el rol del usuario en AulaMetrics.

    Jerarquía: admin > counselor > management > tutor

    Args:
        user: recordset del usuario (res.users)

    Returns:
        dict: {
            'role': str ('admin', 'counselor', 'management', 'tutor'),
            'user_id': int,
            'is_admin': bool,
            'is_counselor': bool,
            'is_management': bool,
            'is_tutor': bool,
            'allowed_group_ids': [],  # Se llena después si es tutor
            'anonymize_students': bool
        }
    """
    role_info = {
        'role': 'tutor',
        'user_id': user.id,
        'user_name': user.name or '',
        'is_admin': False,
        'is_counselor': False,
        'is_management': False,
        'is_tutor': False,
        'allowed_group_ids': [],
        'anonymize_students': False,
    }

    if user.has_group(GROUP_ADMIN):
        role_info.update({
            'role': ROLE_ADMIN,
            'is_admin': True,
            'is_counselor': True,
            'is_management': True,
            'is_tutor': True,
        })
    elif user.has_group(GROUP_COUNSELOR):
        role_info.update({
            'role': ROLE_COUNSELOR,
            'is_counselor': True,
            'is_tutor': True,
        })
    elif user.has_group(GROUP_MANAGEMENT):
        role_info.update({
            'role': ROLE_MANAGEMENT,
            'is_management': True,
            'is_tutor': True,
            'anonymize_students': True,
        })
    else:
        role_info['is_tutor'] = True

    return role_info


def metric_values_to_records(metric_values):
    """
    Convierte un recordset de aula_metrics.metric_value a una lista de dicts
    normalizada, lista para construir un DataFrame de pandas.

    Es el núcleo compartido de prepare_dataframe (dashboard agregado) y
    _prepare_metrics_dataframe (perfil individual de alumno).

    Columnas del dict resultante:
        metric_name, metric_label, metric_type   — identidad de la métrica
        value                                    — valor unificado
        value_numeric, value_json, value_text    — valores por tipo
        timestamp                                — fecha del registro
        evaluation_id, evaluation_name           — evaluación asociada
        student_id, student_name, student_gender — alumno
        group_id, group_name, curso              — grupo académico

    Los registros sin ningún valor (float/json/text) se omiten silenciosamente.
    """
    records = []
    for mv in metric_values:
        if mv.value_float:
            metric_type = 'numeric'
            unified_val = mv.value_float
        elif mv.value_json:
            metric_type = 'json'
            unified_val = mv.value_json
        elif mv.value_text:
            metric_type = 'text'
            unified_val = mv.value_text
        else:
            continue

        records.append({
            'metric_name':    mv.metric_name,
            'metric_label':   mv.metric_label or mv.metric_name.replace('_', ' ').capitalize(),
            'metric_type':    metric_type,
            'value':          unified_val,
            'value_numeric':  mv.value_float if mv.value_float else None,
            'value_json':     mv.value_json  if mv.value_json  else None,
            'value_text':     mv.value_text  if mv.value_text  else None,
            'timestamp':      mv.timestamp,
            'survey_id':      mv.survey_id.id             if mv.survey_id else None,
            'is_aulametrics': mv.survey_id.is_aulametrics if mv.survey_id else False,
            'evaluation_id':   mv.evaluation_id.id   if mv.evaluation_id else None,
            'evaluation_name': mv.evaluation_id.name if mv.evaluation_id else 'Sin evaluación',
            'student_id':     mv.student_id.id     if mv.student_id else None,
            'student_name':   mv.student_id.name   if mv.student_id else None,
            'student_gender': mv.student_id.gender if mv.student_id else None,
            'group_id':   mv.academic_group_id.id           if mv.academic_group_id else None,
            'group_name': mv.academic_group_id.name         if mv.academic_group_id else None,
            'curso':      mv.academic_group_id.course_level if mv.academic_group_id else None,
            'completed_at': (mv.evaluation_id.date_start if mv.evaluation_id and mv.evaluation_id.date_start else mv.timestamp),
        })
    return records
