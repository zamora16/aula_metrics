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
    'depends': ['base','mail', 'survey'],

    'data': [
        # 1. Seguridad
        'security/security.xml',
        'security/ir.model.access.csv',
        'security/record_rules.xml',
        
        # 2. Datos
        'data/surveys/survey_bullying.xml',
        'data/surveys/survey_who5.xml',
        'data/surveys/survey_asq14.xml',
        'data/cron/cron_jobs.xml',
        'data/dashboard_data.xml',
        'data/demo/users_groups.xml',
        
        # 3. Vistas
        'views/dashboard.xml',
        'views/academic_group_views.xml',
        'views/survey_extension_views.xml',
        'views/evaluation_views.xml',
        'views/participations_views.xml',
        'views/threshold_views.xml',
        'views/alert_views.xml',
        'views/alerts_dashboard.xml',
        'views/templates.xml',
        'views/menu.xml',
        
        # 4. Wizards
        'wizards/resolve_alert_wizard_views.xml',

    ],
    'demo': [
        'demo/demo.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}

