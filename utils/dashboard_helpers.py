# -*- coding: utf-8 -*-
"""
Funciones auxiliares compartidas para dashboards de AulaMetrics
Incluye: badges, formatters, validadores, etc.
"""
from datetime import datetime


def get_role_badge(role_info):
    """
    Genera el badge HTML del rol del usuario.
    
    Args:
        role_info (dict): Información del rol con clave 'role'
    
    Returns:
        str: HTML del badge
    """
    role = role_info.get('role', 'tutor') if role_info else 'tutor'
    
    badges = {
        'admin': '<span class="badge bg-danger"><i class="fa-solid fa-shield-halved"></i> Administrador</span>',
        'counselor': '<span class="badge bg-primary"><i class="fa-solid fa-user-tie"></i> Orientador/a</span>',
        'management': '<span class="badge bg-warning text-dark"><i class="fa-solid fa-briefcase"></i> Equipo Directivo</span>',
        'tutor': '<span class="badge bg-success"><i class="fa-solid fa-chalkboard-user"></i> Tutor/a</span>',
    }
    
    return badges.get(role, badges['tutor'])


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


def get_alert_count_badge(count):
    """
    Genera un badge para mostrar el conteo de alertas.
    
    Args:
        count (int): Número de alertas
    
    Returns:
        str: HTML del badge
    """
    if count > 0:
        return f'<span class="badge bg-danger">{count} alerta(s)</span>'
    return '<span class="badge bg-success">Sin alertas</span>'


def get_semaphore_color(value):
    """
    Retorna un color tipo semáforo según el valor (0-100).
    
    Args:
        value (float): Valor normalizado 0-100
    
    Returns:
        str: Código de color hex
    """
    if value >= 80:
        return '#10b981'  # Verde
    elif value >= 60:
        return '#3b82f6'  # Azul
    elif value >= 40:
        return '#f59e0b'  # Amarillo/Naranja
    else:
        return '#ef4444'  # Rojo


def truncate_text(text, max_length=50, suffix='...'):
    """
    Trunca un texto a una longitud máxima.
    
    Args:
        text (str): Texto a truncar
        max_length (int): Longitud máxima
        suffix (str): Sufijo a agregar si se trunca
    
    Returns:
        str: Texto truncado
    """
    if not text:
        return ''
    
    text = str(text)
    if len(text) <= max_length:
        return text
    
    return text[:max_length - len(suffix)] + suffix


def get_chart_js_libraries():
    """
    Retorna los enlaces a las librerías de Chart.js.
    
    Returns:
        str: HTML con links a CDN
    """
    return """
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chartjs-adapter-date-fns@3.0.0/dist/chartjs-adapter-date-fns.bundle.min.js"></script>
    """


def get_d3_libraries():
    """
    Retorna los enlaces a las librerías de D3.js y d3-cloud.
    
    Returns:
        str: HTML con links a CDN
    """
    return """
    <script src="https://d3js.org/d3.v7.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/d3-cloud@1.2.7/build/d3.layout.cloud.min.js"></script>
    """


def build_checkbox_options(items, checked_ids=None, name_prefix='item', id_field='id', label_field='name'):
    """
    Genera HTML de checkboxes para filtros.
    
    Args:
        items (list): Lista de items (dicts o recordsets)
        checked_ids (list): IDs de items marcados
        name_prefix (str): Prefijo para el name del checkbox
        id_field (str): Campo que contiene el ID
        label_field (str): Campo que contiene el label
    
    Returns:
        str: HTML de checkboxes
    """
    if checked_ids is None:
        checked_ids = []
    
    html = ''
    for item in items:
        # Manejar tanto dicts como recordsets
        item_id = item[id_field] if isinstance(item, dict) else getattr(item, id_field)
        item_label = item[label_field] if isinstance(item, dict) else getattr(item, label_field)
        
        checked = 'checked' if item_id in checked_ids else ''
        
        html += f'''
        <label>
            <input type="checkbox" class="{name_prefix}-check" name="{name_prefix}[]" 
                   value="{item_id}" {checked}>
            {item_label}
        </label>
        '''
    
    return html


def format_number(value, decimals=1):
    """
    Formatea un número con decimales.
    
    Args:
        value: Valor numérico
        decimals (int): Número de decimales
    
    Returns:
        str: Número formateado
    """
    try:
        return f"{float(value):.{decimals}f}"
    except (ValueError, TypeError):
        return str(value)


def safe_division(numerator, denominator, default=0):
    """
    División segura que evita división por cero.
    
    Args:
        numerator: Numerador
        denominator: Denominador
        default: Valor por defecto si denominador es 0
    
    Returns:
        float: Resultado de la división o default
    """
    try:
        return numerator / denominator if denominator != 0 else default
    except (TypeError, ValueError):
        return default


def get_gender_label(gender_code):
    """
    Convierte código de género a etiqueta legible.
    
    Args:
        gender_code (str): Código ('male', 'female', 'other', 'prefer_not_say')
    
    Returns:
        str: Etiqueta en español
    """
    gender_map = {
        'male': 'Masculino',
        'female': 'Femenino',
        'other': 'Otro',
        'prefer_not_say': 'Prefiere no decir'
    }
    return gender_map.get(gender_code, gender_code)


def sanitize_id(text):
    """
    Sanitiza un texto para usarlo como ID HTML válido.
    
    Args:
        text (str): Texto a sanitizar
    
    Returns:
        str: ID válido
    """
    return text.replace(' ', '_').replace('/', '_').replace('.', '_').replace('(', '').replace(')', '')


# ==================== HTML BUILDER HELPERS ====================

def build_chart_card_header(label, subtitle, chart_id, segment_options_html=''):
    """
    Genera el header de una card de chart con título, subtítulo y selector de segmentación.
    
    Args:
        label (str): Título de la card
        subtitle (str): Subtítulo/descripción
        chart_id (str): ID único del chart (para vincular al selector)
        segment_options_html (str): HTML de opciones de segmentación (opcional)
    
    Returns:
        str: HTML del card-header completo
    """
    segment_selector = ''
    if segment_options_html:
        segment_selector = f'''
                <select id="segment_{chart_id}" class="chart-segment-selector">
                    {segment_options_html}
                </select>'''
    
    return f'''
            <div class="card-header chart-card-header">
                <div>
                    <h5 class="card-title">{label}</h5>
                    <p class="card-subtitle">{subtitle}</p>
                </div>{segment_selector}
            </div>'''


def get_segment_colors_js():
    """
    Retorna el objeto JavaScript de colores para segmentación.
    Esta es la paleta estándar usada en todos los charts.
    
    Returns:
        str: Código JavaScript del objeto segmentColors
    """
    return """const segmentColors = {
                'Masculino': '#3b82f6',
                'Femenino': '#ec4899',
                'Otro': '#94a3b8',
                'Prefiere no decir': '#64748b',
                'default': ['#3b82f6', '#10b981', '#f59e0b', '#8b5cf6', '#ec4899', '#06b6d4', '#f97316', '#14b8a6']
            };"""


def get_chart_card_styles():
    """
    Retorna los estilos CSS para elementos de chart cards.
    Estos estilos se aplican inline para charts dinámicos.
    
    Returns:
        dict: Diccionario con clases CSS como keys y estilos como values
    """
    return {
        'chart-card-header': 'display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px;',
        'chart-segment-selector': 'padding: 6px 12px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; cursor: pointer; font-size: 12px; color: #475569; font-weight: 500; min-width: 160px;'
    }


def format_participation_rate(rate):
    """
    Formatea un porcentaje de participación.
    
    Args:
        rate (float): Porcentaje (0-100)
    
    Returns:
        str: Porcentaje formateado como "XX.X%"
    """
    try:
        return f"{float(rate):.1f}%"
    except (ValueError, TypeError):
        return "0.0%"


def format_date_range(date_start, date_end):
    """
    Formatea un rango de fechas.
    
    Args:
        date_start: Fecha de inicio (date, datetime o string)
        date_end: Fecha de fin (date, datetime o string)
    
    Returns:
        str: Rango formateado como "DD/MM/YYYY - DD/MM/YYYY"
    """
    start_formatted = format_date(date_start, '%d/%m/%Y')
    end_formatted = format_date(date_end, '%d/%m/%Y')
    return f"{start_formatted} - {end_formatted}"
