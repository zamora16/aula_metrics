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
        'security/security.xml',
        'views/academic_group_views.xml',
        'views/res_users_views.xml', 
        'views/menu.xml',
        'security/ir.model.access.csv',
        'security/record_rules.xml',
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

