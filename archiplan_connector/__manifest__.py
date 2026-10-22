{
    'name': 'ArchiPlan Connector',
    'version': '20.0.1.0.0',
    'license': 'LGPL-3',
    'author': 'ArchiPlan',
    'website': 'https://archiplan.io',
    'category': 'Manufacturing/Manufacturing',
    'summary': 'Plan production from Odoo sales orders with people and machine schedules',
    'images': ['static/description/cover.gif'],
    'depends': ['base_setup', 'mrp', 'sale'],
    'data': [
        'security/archiplan_security.xml',
        'security/ir.access.csv',
        'views/res_config_settings_views.xml',
        'wizard/access_wizard_views.xml',
        'views/schedule_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'archiplan_connector/static/src/js/schedule.js',
            'archiplan_connector/static/src/xml/schedule.xml',
        ],
    },
    'installable': True,
    'application': False,
}
