# -*- coding: utf-8 -*-
"""
Paleta centralizada para los dashboards de métricas.
Usar estas constantes desde charts, controllers y helpers para facilitar pruebas y cambios de estilo.
"""
from .constants import COURSE_LEVEL_MAP as COURSE_LEVEL_LABELS  # única fuente de verdad

# Paleta principal para gráficos de métricas (estilo educativo)
METRICS_PALETTE = [
    '#0f4c81',  # Academic Navy
    '#2f855a',  # Chalkboard Green
    '#f6c85f',  # Mustard Accent
    '#8b5cf6',  # Purple
    '#ec4899',  # Pink/Rose
    '#06b6d4',  # Cyan/Teal
    '#f97316',  # Orange
    '#84cc16',  # Lime/Green
    '#f43f5e',  # Red/Rose
    '#14b8a6',  # Teal
]

# ── Niveles educativos ────────────────────────────────────────────────────────
# COURSE_LEVEL_LABELS se importa desde constants (ver arriba)

# Colores fijos y diferenciados por nivel — sin colisiones de hash
COURSE_LEVEL_COLORS = {
    'eso1':  '#0f4c81',  # Academic Navy
    'eso2':  '#2f855a',  # Chalkboard Green
    'eso3':  '#f97316',  # Orange
    'eso4':  '#8b5cf6',  # Purple
    'bach1': '#ec4899',  # Pink/Rose
    'bach2': '#06b6d4',  # Cyan/Teal
}


def get_label_for_course(key):
    """Devuelve la etiqueta legible para una clave de nivel educativo."""
    return COURSE_LEVEL_LABELS.get(str(key), str(key))


def get_color_for_course(key):
    """Devuelve un color fijo y diferenciado para una clave de nivel educativo."""
    return COURSE_LEVEL_COLORS.get(str(key), get_color_for_label(key))

# Colores específicos para segmentaciones (masculino/femenino/otro/nd)
SEGMENT_COLORS = {
    'Masculino': '#0f4c81',
    'Femenino': '#2f855a',
    'Otro': '#94a3b8',
    'Prefiere no decir': '#64748b',
}

# Colores para bins/histogramas usados en algunos charts
BIN_COLORS = ['#3b82f6', '#60a5fa', '#fb923c', '#f97316']

def get_color_for_label(label):
    """Mapea un nombre de grupo/curso a un color de la paleta de forma estable.

    El mismo nombre siempre produce el mismo color, independientemente de
    cuántos o cuáles grupos aparezcan en el gráfico concreto.  Usa una
    función de hash determinista (suma de ordinales ponderada) que no
    depende de PYTHONHASHSEED.
    """
    h = sum(ord(c) * (i + 1) for i, c in enumerate(str(label)))
    return METRICS_PALETTE[h % len(METRICS_PALETTE)]


# Alias cómodo
DEFAULT_PALETTE = METRICS_PALETTE

# ==================== UI / THEME TOKENS ====================
# Valores usados por `dashboard_styles.get_common_styles()` (colores del UI)
# Tema: Warm Teal Scholarly — harmonises with logo #42bda5 / #f39e35 / #ec712f
UI_BG           = '#F5EEE6'   # warm parchment — signature background
UI_SURFACE      = '#FEFCF8'   # creamy warm-white surface
UI_TEXT         = '#1A1714'   # warm near-black (not cold)
UI_PRIMARY      = '#1A5C52'   # deep professional teal (dark version of logo #42bda5)
UI_PRIMARY_DARK = '#134940'   # deeper teal
UI_PRIMARY_DARKER = '#0C3329'
UI_PRIMARY_LIGHT  = '#EBF6F4'  # light teal tint
UI_PRIMARY_200    = '#B8DED9'  # mid teal
# RGB tuple as string for rgba() usage in CSS
UI_PRIMARY_RGB    = '26, 92, 82'
UI_SUCCESS      = '#1A7A5E'   # teal-green success
UI_SUCCESS_DARK = '#115C47'   # deeper teal-green

# Acento — warm burnt orange (matured from logo #ec712f)
UI_ACCENT       = '#D4621A'   # warm burnt orange
UI_ACCENT_DARK  = '#B0511A'   # deeper burnt orange
UI_MUTED            = '#7A6D65'   # warm sand-gray muted text
UI_TEXT_SECONDARY   = '#5A4E48'   # warm secondary text
UI_SUBTLE           = '#9E918A'   # warm subtle text / chart ticks
UI_SUBTLE_BORDER    = '#CEC7BE'   # warm sand subtle border
UI_CHALKBOARD_GREEN = '#1A7A5E'   # teal-green — referencia de media del centro
UI_BORDER       = '#E0D8CF'   # warm sand border
UI_LIGHT        = '#FAF6F0'   # warm light surface
UI_WARNING      = '#C07E10'   # amber-brown, readable on light bg
UI_WARNING_DARK = '#9A6408'   # deep amber
UI_DANGER        = '#9B2335'   # deep wine red
UI_DANGER_DARK   = '#7A1A28'   # darker wine
UI_DANGER_DARKER = '#5E1320'   # deepest wine for high-severity badges
UI_SIDEBAR_START = '#12332F'  # deep teal sidebar start (harmonises with logo)
UI_SIDEBAR_END   = '#0C211E'  # very deep teal end

# ==================== ROLE / INLINE COLOR TOKENS ====================
# Colores de badges de roles en el sidebar (antes inline en CSS)
UI_ROLE_ADMIN      = '#fca5a5'   # warm red
UI_ROLE_COUNSELOR  = '#93c5fd'   # soft blue
UI_ROLE_MANAGEMENT = '#fde68a'   # warm amber
UI_ROLE_TUTOR      = '#86efac'   # soft green

# Superficie inversa (float bar, tooltip bg, contextos oscuros)
UI_SURFACE_INVERSE = '#12332F'   # deep teal — warm dark surface

# Texto semántico de advertencia sobre fondo claro (antes inline #78350f)
UI_WARNING_TEXT    = '#78350f'   # amber-900 — texto en bloques de interpretación

# Hover de filas de tabla
UI_ROW_HOVER       = '#F0EBE3'   # warm parchment hover

# Gradiente del panel de segmentación global (barra de filtro superior en dashboard de métricas)
UI_SEGMENTATION_BAR_GRADIENT = 'linear-gradient(135deg, #1A5C52 0%, #134940 100%)'

# Tokens compartidos para gráficos Chart.js (interpolados en f-strings)
UI_TOOLTIP_BG      = '#12332F'   # deep teal tooltip background
UI_CHART_EMPHASIS  = '#12332F'   # teal emphasis line — media grupal
UI_GRID_LINE       = '#EDE5DC'   # warm parchment gridlines

# ==================== CHART TYPOGRAPHY ====================
# Fuente y color de etiquetas/ticks usados en TODOS los gráficos Chart.js.
# Cambiar aquí actualiza todos los gráficos automáticamente.
CHART_FONT       = "'Source Sans 3', 'Source Sans Pro', system-ui, sans-serif"
CHART_TICK_COLOR = UI_MUTED        # warm sand-gray — ejes, ticks y leyendas de gráficos

# ==================== ALERT SEVERITY TOKENS ====================
# Colores semánticos para las 3 severidades de alertas manuales.
# Usados en _ALERT_SEV (dashboard_student_sections) para construir badges y bordes.
ALERT_LOW_COLOR  = '#0ea5e9'   # sky-500
ALERT_LOW_BG     = '#f0f9ff'   # sky-50
ALERT_LOW_BORDER = '#bae6fd'   # sky-200

ALERT_MOD_COLOR  = UI_WARNING  # amber-400 — #f59e0b
ALERT_MOD_BG     = '#fffbeb'   # amber-50
ALERT_MOD_BORDER = '#fde68a'   # amber-200

ALERT_HIGH_COLOR  = UI_DANGER  # red-500 — #ef4444 (alias explícito para consistencia)
ALERT_HIGH_BG     = '#fef2f2'  # red-50
ALERT_HIGH_BORDER = '#fecaca'  # red-200

# Colores badge "sin alertas" / participación normal
BADGE_OK_BG     = '#f0fdf4'   # green-50
BADGE_OK_BORDER = '#bbf7d0'   # green-200
