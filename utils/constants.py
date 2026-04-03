# -*- coding: utf-8 -*-
"""
Constantes centralizadas para AulaMetrics.

Toda cadena "magic" referida a grupos de seguridad, límites operacionales,
etiquetas de severidad o colores debe importarse desde aquí.  Así, un
cambio en el nombre de un grupo o en los colores del sistema se aplica en
un único lugar.
"""

# ─────────────────────────────────────────────────────────────────────────────
# Grupos de seguridad de Odoo (XML IDs)
# ─────────────────────────────────────────────────────────────────────────────
GROUP_ADMIN      = 'aula_metrics.group_aulametrics_admin'
GROUP_COUNSELOR  = 'aula_metrics.group_aulametrics_counselor'
GROUP_MANAGEMENT = 'aula_metrics.group_aulametrics_management'
GROUP_TUTOR      = 'aula_metrics.group_aulametrics_tutor'

# ─────────────────────────────────────────────────────────────────────────────
# Jerarquía de roles (de mayor a menor privilegio)
# ─────────────────────────────────────────────────────────────────────────────
ROLE_ADMIN      = 'admin'
ROLE_COUNSELOR  = 'counselor'
ROLE_MANAGEMENT = 'management'
ROLE_TUTOR      = 'tutor'

ROLE_HIERARCHY = [ROLE_ADMIN, ROLE_COUNSELOR, ROLE_MANAGEMENT, ROLE_TUTOR]

# ─────────────────────────────────────────────────────────────────────────────
# Niveles de severidad (enteros estructurales del sistema de baremos)
#
# IMPORTANTE: Las *etiquetas* y *colores* de severidad NO son constantes
# globales; cada cuestionario oficial define los suyos propios en los
# registros SurveyBaremoRange (campos `label` y `color`).
# Solo el índice numérico es fijo: 0 = normal, 1 = límite/borderline, 2 = anormal.
# Recuperar etiquetas/colores: BaremoRange.get_severity_mapping(survey_id)
# ─────────────────────────────────────────────────────────────────────────────
SEV_NORMAL = 0   # Dentro de rango esperado
SEV_LIMITE = 1   # Borderline / en el límite
SEV_ANORMAL = 2  # Clínicamente relevante / anormal

# Colores de fallback cuando un baremo no tiene color definido en BD
SEV_FALLBACK_COLOR = '#cccccc'   # Gris neutro para color de trazo
SEV_FALLBACK_BG    = '#ffffff'   # Blanco para fondo de badge

# Severidad de alertas manuales (campo `severity` en aula_metrics.alert)
# Estos SÍ son constantes: el rango de opciones está fijo en el selection field.
SEVERITY_LOW      = 'low'
SEVERITY_MODERATE = 'moderate'
SEVERITY_HIGH     = 'high'

# ─────────────────────────────────────────────────────────────────────────────
# Límites operacionales
# ─────────────────────────────────────────────────────────────────────────────
# Número máximo de registros devueltos en búsquedas de dashboard
QUERY_LIMIT_QUALITATIVE  = 500
QUERY_LIMIT_ALERTS       = 200
QUERY_LIMIT_STUDENTS     = 1000

# ─────────────────────────────────────────────────────────────────────────────
# Estados de evaluación
# ─────────────────────────────────────────────────────────────────────────────
# Todos los estados visibles en dashboards (excluye solo 'cancelled')
EVAL_STATES_ACTIVE = ['draft', 'scheduled', 'active', 'closed', 'done']

# ─────────────────────────────────────────────────────────────────────────────
# Colores semáforo para KPIs (umbral de valor 0-100)
# ─────────────────────────────────────────────────────────────────────────────
SEMAPHORE_GREEN  = '#10b981'
SEMAPHORE_BLUE   = '#3b82f6'
SEMAPHORE_YELLOW = '#f59e0b'
SEMAPHORE_RED    = '#ef4444'
SEMAPHORE_THRESHOLD_HIGH   = 80
SEMAPHORE_THRESHOLD_MEDIUM = 60
SEMAPHORE_THRESHOLD_LOW    = 40

# ─────────────────────────────────────────────────────────────────────────────
# Niveles educativos: clave de selección → etiqueta legible
# ─────────────────────────────────────────────────────────────────────────────
COURSE_LEVEL_MAP = {
    'eso1': '1º ESO',
    'eso2': '2º ESO',
    'eso3': '3º ESO',
    'eso4': '4º ESO',
    'bach1': '1º Bachillerato',
    'bach2': '2º Bachillerato',
}
