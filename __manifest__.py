# -*- coding: utf-8 -*-
{
    'name': "AulaMetrics",
    'version': '1.0.0',
    'summary': "Sistema de evaluación psicosocial para centros educativos",

    'description': """
        Módulo base de AulaMetrics que proporciona:
        - Gestión de grupos académicos
        - Extensión de roles y permisos
        - Configuración global del sistema
    """,

    'author': "Angel Zamora",
    'category': 'Education',
    # any module necessary for this one to work correctly
    'depends': ['base','mail', 'survey'],

    # always loaded
    'data': [
        # 1. Seguridad
        'security/security.xml',
        'security/ir.model.access.csv',
        'security/record_rules.xml',
        
        # 2. Datos (surveys)
        'data/surveys_data.xml',
        'data/cron_jobs.xml',
        'data/demo/users_groups.xml',
        
        # 3. Vistas
        'views/dashboard.xml',
        'views/academic_group_views.xml',
        'views/survey_extension_views.xml',
        'views/evaluation_views.xml',
        'views/participations_views.xml',
        'views/templates.xml',
        'views/menu.xml',

    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}

