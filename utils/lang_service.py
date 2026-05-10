# -*- coding: utf-8 -*-
"""
Servicio de idioma para el portal de encuestas de AulaMetrics.

Gestiona la detección y persistencia del idioma seleccionado por el alumno.

Para añadir un nuevo idioma basta con:
  1. Instalar el idioma en Odoo (Ajustes → Idiomas).
  2. Añadir su código y etiqueta a SUPPORTED_LANGS.
  3. Traducir el contenido de los cuestionarios con las herramientas estándar de Odoo.
"""

# ── Idiomas soportados en el portal de encuestas ──────────────────────────────
# Clave  : código de idioma Odoo (formato ll_CC)
# Valor  : etiqueta mostrada al alumno en el selector
SUPPORTED_LANGS = {
    'es_ES': 'Castellano',
    'ca_ES': 'Valencià',
}

# Idioma por defecto cuando no hay preferencia almacenada
DEFAULT_LANG = 'es_ES'

# Nombre de la cookie que persiste la elección del alumno
_LANG_COOKIE = 'am_survey_lang'

# Tiempo de vida de la cookie (1 año en segundos)
_COOKIE_MAX_AGE = 365 * 24 * 3600


def get_request_lang(request) -> str:
    """Devuelve el código de idioma activo para la petición actual.

    Orden de precedencia:
      1. Cookie ``am_survey_lang`` (preferencia guardada vía /am/lang).
      2. ``DEFAULT_LANG`` ('es_ES').

    El parámetro GET ``lang`` se acepta como fallback para pruebas manuales,
    pero el mecanismo normal de cambio de idioma es el endpoint POST /am/lang.
    """
    lang = request.params.get('lang')
    if lang not in SUPPORTED_LANGS:
        lang = request.httprequest.cookies.get(_LANG_COOKIE)
    if lang not in SUPPORTED_LANGS:
        lang = DEFAULT_LANG
    return lang


def set_lang_cookie(response, lang: str):
    """Escribe la cookie de idioma en la respuesta y la devuelve."""
    response.set_cookie(
        _LANG_COOKIE,
        lang,
        max_age=_COOKIE_MAX_AGE,
        httponly=False,   # accesible desde JS si se necesitase
        samesite='Lax',
    )
    return response
