# -*- coding: utf-8 -*-
"""
Paleta centralizada para los dashboards de métricas.
Usar estas constantes desde charts, controllers y helpers para facilitar pruebas y cambios de estilo.
"""

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
# Tema: Professional Educational — neutral warm, deep navy, sky accent
UI_BG           = '#f4f5f7'   # neutral warm background (menos tinte azul)
UI_SURFACE      = '#ffffff'
UI_TEXT         = '#0f1e36'   # deep navy text
UI_PRIMARY      = '#0f4c81'   # primary: academic navy
UI_PRIMARY_DARK = '#0b3a66'
UI_PRIMARY_DARKER = '#06263f'
UI_PRIMARY_LIGHT  = '#eff6ff'
UI_PRIMARY_200    = '#bfdbfe'
# RGB tuple as string for rgba() usage in CSS
UI_PRIMARY_RGB    = '15, 76, 129'
UI_SUCCESS      = '#059669'   # emerald-600 — más profundo, más confianza
UI_SUCCESS_DARK = '#047857'   # emerald-700

# Acento secundario — interactivo, sky-500/600 (separa de amber semántico)
UI_ACCENT       = '#0ea5e9'   # sky-500
UI_ACCENT_DARK  = '#0284c7'   # sky-600
UI_MUTED            = '#64748b'   # texto/leyendas atenuadas
UI_TEXT_SECONDARY   = '#475569'   # texto secundario — slate-600
UI_SUBTLE           = '#94a3b8'   # texto muy atenuado / chart ticks — slate-400
UI_SUBTLE_BORDER    = '#cbd5e1'   # bordes sutiles — slate-300
UI_CHALKBOARD_GREEN = '#2f855a'   # verde pizarra — referencia de media del centro
UI_BORDER       = '#e4eaf3'   # cooler, bluer border
UI_LIGHT        = '#f8fafc'   # light surface
UI_WARNING      = '#f59e0b'   # amber accent
UI_WARNING_DARK = '#d97706'   # amber-600 — texto sobre fondo claro
UI_DANGER        = '#e53e3e'   # red más cálido (menos alarma, más profesional)
UI_DANGER_DARK   = '#c53030'   # red-700 — texto sobre fondo claro
UI_DANGER_DARKER = '#9b2c2c'   # red-800 — texto en badges de alta severidad
UI_SIDEBAR_START = '#0f1e36'  # deep sidebar
UI_SIDEBAR_END   = '#0d1b30'   # sutil gradiente inferior

# ==================== ROLE / INLINE COLOR TOKENS ====================
# Colores de badges de roles en el sidebar (antes inline en CSS)
UI_ROLE_ADMIN      = '#fca5a5'   # red-300
UI_ROLE_COUNSELOR  = '#93c5fd'   # blue-300
UI_ROLE_MANAGEMENT = '#fde68a'   # amber-200
UI_ROLE_TUTOR      = '#86efac'   # green-300

# Superficie inversa (float bar, tooltip bg, contextos oscuros)
UI_SURFACE_INVERSE = '#1e293b'   # slate-800

# Texto semántico de advertencia sobre fondo claro (antes inline #78350f)
UI_WARNING_TEXT    = '#78350f'   # amber-900 — texto en bloques de interpretación

# Hover de filas de tabla (antes inline #fbfcfe)
UI_ROW_HOVER       = '#f7f8fa'

# Gradiente del panel de segmentación global (barra de filtro superior en dashboard de métricas)
UI_SEGMENTATION_BAR_GRADIENT = 'linear-gradient(135deg, #1e4a8a 0%, #0f4c81 100%)'

# Tokens compartidos para gráficos Chart.js (interpolados en f-strings)
UI_TOOLTIP_BG      = '#1e293b'   # fondo de tooltip — slate-800
UI_CHART_EMPHASIS  = '#1e293b'   # línea de énfasis (media grupal) — slate-800
UI_GRID_LINE       = '#f1f5f9'   # color de gridlines — slate-100

# ==================== CHART TYPOGRAPHY ====================
# Fuente y color de etiquetas/ticks usados en TODOS los gráficos Chart.js.
# Cambiar aquí actualiza todos los gráficos automáticamente.
CHART_FONT       = "'Plus Jakarta Sans', sans-serif"
CHART_TICK_COLOR = UI_MUTED        # #64748b — ejes, ticks y leyendas de gráficos

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
