# -*- coding: utf-8 -*-
{
    'name': 'HR Training Request',
    'summary': 'Manage external employee training & certification requests with manager and HR approval workflow',
    'version': '18.0.2.0.0',
    'category': 'Human Resources/Employees',
    'sequence': 20,
    'author': 'Meraj Serker <https://github.com/MerajAlif>',
    'website': 'https://github.com/MerajAlif',
    'license': 'LGPL-3',
    'support': 'https://github.com/MerajAlif',
    'depends': [
        'hr',
        'mail',
    ],
    'data': [
        'security/hr_training_security.xml',
        'security/ir.model.access.csv',
        'wizard/hr_training_reject_wizard_views.xml',
        'views/hr_training_request_views.xml',
        'views/hr_employee_views.xml',
        'views/hr_training_menus.xml',
    ],
    'demo': [
        'data/hr_training_demo.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'hr_training_request/static/src/dashboard/hr_training_dashboard.js',
            'hr_training_request/static/src/dashboard/hr_training_dashboard.xml',
            'hr_training_request/static/src/dashboard/hr_training_dashboard.scss',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
}
