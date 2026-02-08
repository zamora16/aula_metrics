# -*- coding: utf-8 -*-
"""
Componentes de layout compartidos para dashboards de AulaMetrics
Incluye: sidebar, topbar, footer, etc.
"""


def get_sidebar(role_info=None, active_section='home'):
    """
    Genera el sidebar de navegación.
    
    Args:
        role_info (dict): Información del rol del usuario
        active_section (str): Sección activa ('home', 'quantitative', 'qualitative', 'profiles')
    
    Returns:
        str: HTML del sidebar
    """
    # Perfiles solo visible para counselor/admin
    profiles_item = ''
    if role_info and role_info.get('role') in ['admin', 'counselor']:
        profiles_active = 'active' if active_section == 'profiles' else ''
        profiles_item = f'''
        <a href="/aulametrics/students" class="sidebar-item {profiles_active}">
            <i class="fa-solid fa-users"></i>
            <span>Perfiles de Alumnos</span>
        </a>
        '''
    
    home_active = 'active' if active_section == 'home' else ''
    quant_active = 'active' if active_section == 'quantitative' else ''
    qual_active = 'active' if active_section == 'qualitative' else ''
    
    # Determinar si estamos en la vista de dashboard principal (con navegación interna)
    # o en vistas externas (con enlaces href)
    if active_section in ['home', 'quantitative', 'qualitative']:
        # Dashboard principal: navegación con JavaScript
        home_link = f'<a href="#" class="sidebar-item {home_active}" data-section="home" onclick="navigateTo(\'home\'); return false;">'
        quant_link = f'<a href="#" class="sidebar-item {quant_active}" data-section="quantitative" onclick="navigateTo(\'quantitative\'); return false;">'
        qual_link = f'<a href="#" class="sidebar-item {qual_active}" data-section="qualitative" onclick="navigateTo(\'qualitative\'); return false;">'
    else:
        # Vistas externas (perfiles): enlaces href normales
        home_link = '<a href="/aulametrics/dashboard" class="sidebar-item">'
        quant_link = '<a href="/aulametrics/dashboard" class="sidebar-item">'
        qual_link = '<a href="/aulametrics/dashboard" class="sidebar-item">'
    
    return f"""
    <aside class="sidebar">
        <div class="sidebar-header">
            <i class="fa-solid fa-gauge-high"></i>
            <span>AulaMetrics</span>
        </div>
        
        <nav class="sidebar-nav">
            {home_link}
                <i class="fa-solid fa-house"></i>
                <span>Inicio</span>
            </a>
            
            {quant_link}
                <i class="fa-solid fa-chart-line"></i>
                <span>Datos Cuantitativos</span>
            </a>
            
            {qual_link}
                <i class="fa-solid fa-comments"></i>
                <span>Datos Cualitativos</span>
            </a>
            
            {profiles_item}
        </nav>
        
        <div class="sidebar-footer">
            <a href="/web" class="btn btn-outline-light btn-sm w-100">
                <i class="fa-solid fa-arrow-left me-2"></i>Volver a Odoo
            </a>
        </div>
    </aside>
    """


def get_topbar(title, subtitle='', role_badge='', extra_actions=''):
    """
    Genera la barra superior (topbar).
    
    Args:
        title (str): Título principal
        subtitle (str): Subtítulo o breadcrumbs
        role_badge (str): Badge HTML del rol del usuario
        extra_actions (str): HTML adicional para acciones (botones, enlaces, etc.)
    
    Returns:
        str: HTML del topbar
    """
    subtitle_html = f'<span class="breadcrumbs">{subtitle}</span>' if subtitle else ''
    
    return f"""
    <div class="topbar">
        <div>
            <h3 id="sectionTitle">{title}</h3>
            {subtitle_html}
        </div>
        <div class="topbar-actions">
            {role_badge}
            {extra_actions}
        </div>
    </div>
    """


def get_html_wrapper(title, content, sidebar_html, topbar_html, styles='', scripts='', head_extra=''):
    """
    Envuelve el contenido en la estructura HTML completa del dashboard.
    
    Args:
        title (str): Título de la página
        content (str): Contenido principal HTML
        sidebar_html (str): HTML del sidebar
        topbar_html (str): HTML del topbar
        styles (str): CSS adicional
        scripts (str): JavaScript adicional
        head_extra (str): Enlaces a librerías adicionales (Chart.js, etc.)
    
    Returns:
        str: HTML completo de la página
    """
    return f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{title} - AulaMetrics</title>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        {head_extra}
        {styles}
    </head>
    <body>
        <div class="dashboard-layout">
            {sidebar_html}
            
            <main class="main-content">
                {topbar_html}
                
                <div class="content-wrapper">
                    {content}
                </div>
            </main>
        </div>
        
        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
        {scripts}
    </body>
    </html>
    """


def get_empty_state(icon='chart-line', title='No hay datos disponibles', message='Ajusta los filtros para ver resultados'):
    """
    Genera un estado vacío estándar.
    
    Args:
        icon (str): Clase de icono de Font Awesome (sin 'fa-solid fa-')
        title (str): Título del mensaje
        message (str): Mensaje descriptivo
    
    Returns:
        str: HTML del estado vacío
    """
    return f"""
    <div class="empty-state">
        <i class="fa-solid fa-{icon} fa-4x"></i>
        <h3>{title}</h3>
        <p>{message}</p>
    </div>
    """
