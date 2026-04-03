# -*- coding: utf-8 -*-
"""
Valores por defecto compartidos para gráficos Chart.js.

PROPÓSITO
---------
Centraliza la configuración repetida de plugins (tooltip, legend) y escalas
de Chart.js para que un único cambio aquí se propague a todos los gráficos.

USO EN MÉTODOS DE GRÁFICO
--------------------------
Los métodos de gráfico (dashboard_chart_*.py) deben:

    import json
    from ...utils import chart_defaults

    # Fuera del f-string, calcular las opciones:
    _legend  = json.dumps(chart_defaults.get_legend_series())
    _scale_x = json.dumps(chart_defaults.get_scale_x_categorical())
    _scale_y = json.dumps(chart_defaults.get_scale_y_score(y_min, y_max))
    _tooltip = chart_defaults.tooltip_js(chart_defaults.CALLBACKS_SCORE_LABEL)

    # Y luego en el f-string usar {_legend}, {_scale_x}, etc.

CALLBACKS
---------
Para tooltips con callbacks JS, usar las constantes CALLBACKS_* o componer
manualmente el string de callbacks (ver docstring de tooltip_js).
"""

import json
from . import palette

# ---------------------------------------------------------------------------
# Callbacks JS estándar (strings que se inyectan dentro del bloque callbacks)
# ---------------------------------------------------------------------------

CALLBACKS_SCORE_LABEL = (
    'title: function(ctx) { return ctx[0].label; },'
    'label: function(ctx) { return ctx.dataset.label + ": " + ctx.parsed.y.toFixed(1) + " pts"; }'
)

# Para gráficos de barras horizontales (indexAxis: 'y'): el valor está en ctx.parsed.x
# y el nombre de la categoría está en ctx.label (no en ctx.dataset.label).
CALLBACKS_SCORE_LABEL_HORIZONTAL = (
    'title: function(ctx) { return ctx[0].label; },'
    'label: function(ctx) { return ctx.parsed.x.toFixed(1) + " pts"; }'
)

CALLBACKS_SCORE_LABEL_WITH_GROUP_MEAN = (
    'title: function(ctx) { return ctx[0].label; },'
    'label: function(ctx) {'
    '  if (ctx.dataset.label === "Media del grupo") {'
    '    return "Media: " + ctx.parsed.y.toFixed(1) + " pts";'
    '  }'
    '  return ctx.dataset.label + ": " + ctx.parsed.y.toFixed(1) + " pts";'
    '}'
)


# ---------------------------------------------------------------------------
# Tooltip
# ---------------------------------------------------------------------------

def get_tooltip_base():
    """
    Devuelve el dict Python con la configuración base del tooltip Chart.js.
    Para incrustar sin callbacks: json.dumps(get_tooltip_base())
    """
    return {
        'backgroundColor': palette.UI_TOOLTIP_BG,
        'padding': 12,
        'cornerRadius': 6,
        'titleFont': {'family': palette.CHART_FONT, 'size': 13, 'weight': '600'},
        'bodyFont': {'family': palette.CHART_FONT, 'size': 12},
    }


def tooltip_js(callbacks_js=''):
    """
    Devuelve el bloque completo de tooltip como string JS listo para incrustar
    en un f-string de Chart.js.

    Args:
        callbacks_js: string JS con las propiedades del objeto callbacks
                      (sin llaves externas). Por ejemplo:
                      'label: function(ctx) { return ctx.parsed.y.toFixed(1); }'
                      Usar las constantes CALLBACKS_* para los casos estándar.

    Returns:
        str: objeto JS completo, e.g. '{"backgroundColor": ..., "callbacks": {...}}'
    """
    base = json.dumps(get_tooltip_base())
    if not callbacks_js:
        return base
    # Insertar callbacks antes de la llave de cierre
    return base[:-1] + ', "callbacks": {' + callbacks_js + '}}'


# ---------------------------------------------------------------------------
# Legend
# ---------------------------------------------------------------------------

def get_legend_series(position='top', font_size=10, padding=10):
    """
    Leyenda estándar para gráficos con múltiples series (líneas, barras agrupadas).

    Args:
        position: 'top' | 'bottom' | 'left' | 'right'
        font_size: tamaño de fuente de la leyenda (default 10)
        padding: espaciado entre ítems de leyenda (default 10)
    """
    return {
        'display': True,
        'position': position,
        'labels': {
            'usePointStyle': True,
            'padding': padding,
            'font': {'size': font_size, 'family': palette.CHART_FONT},
            'color': palette.CHART_TICK_COLOR,
            'boxWidth': 8,
        },
    }


# ---------------------------------------------------------------------------
# Escalas
# ---------------------------------------------------------------------------

def get_scale_x_categorical(max_ticks=8):
    """
    Eje X estándar para gráficos con etiquetas categóricas (ej. evaluaciones, grupos).
    Oculta la grid y aplica autoSkip para evitar solapamiento de etiquetas.
    """
    return {
        'grid': {'display': False, 'drawBorder': False},
        'ticks': {
            'font': {'size': 11, 'family': palette.CHART_FONT},
            'color': palette.CHART_TICK_COLOR,
            'maxRotation': 30,
            'autoSkip': True,
            'maxTicksLimit': max_ticks,
        },
    }


def get_scale_y_score(y_min, y_max, title_text='Puntuaci\u00f3n'):
    """
    Eje Y estándar para métricas con rango numérico acotado (ej. 0-100).

    Args:
        y_min: valor mínimo del eje
        y_max: valor máximo del eje
        title_text: etiqueta del eje Y (default 'Puntuación')
    """
    return {
        'min': y_min,
        'max': y_max,
        'title': {
            'display': True,
            'text': title_text,
            'font': {'size': 11, 'family': palette.CHART_FONT},
            'color': palette.CHART_TICK_COLOR,
        },
        'grid': {'color': palette.UI_GRID_LINE, 'drawBorder': False},
        'ticks': {
            'font': {'size': 11, 'family': palette.CHART_FONT},
            'color': palette.CHART_TICK_COLOR,
        },
    }
