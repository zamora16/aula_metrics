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

# Alias cómodo
DEFAULT_PALETTE = METRICS_PALETTE

# ==================== UI / THEME TOKENS ====================
# Valores usados por `dashboard_styles.get_common_styles()` (colores del UI)
# Tema: "Educational" — navy principal, verde pizarra y acentos cálidos
UI_BG = '#fbf6e9'                 # papel suave / fondo cálido
UI_SURFACE = '#ffffff'
UI_TEXT = '#0b2545'               # texto: navy suave
UI_PRIMARY = '#0f4c81'            # primary: academic navy
UI_PRIMARY_DARK = '#0b3a66'
UI_PRIMARY_DARKER = '#06263f'
UI_PRIMARY_LIGHT = '#eaf3ff'
UI_PRIMARY_200 = '#cfe6ff'
# RGB tuple as string for rgba() usage in CSS
UI_PRIMARY_RGB = '15, 76, 129'
UI_SUCCESS = '#2f855a'            # chalkboard green
UI_SUCCESS_DARK = '#276c48'
UI_MUTED = '#6b7280'              # texto/leyendas atenuadas
UI_BORDER = '#e6e2d8'             # borde cálido y suave
UI_LIGHT = '#fffaf0'              # superficies claras cálidas
UI_WARNING = '#f6c85f'            # mostaza educacional
UI_DANGER = '#ef4444'
UI_SIDEBAR_START = '#0b3a66'
UI_SIDEBAR_END = '#06263f'
