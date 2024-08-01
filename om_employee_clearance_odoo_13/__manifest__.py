# -*- coding: utf-8 -*-
{
    'name': "Employee Clearance",

    'summary': """
        Short (1 phrase/line) summary of the module's purpose, used as
        subtitle on modules listing or apps.openerp.com""",

    'description': """
        Long description of module's purpose
    """,
    'sequence': -100,
    'author': "My Company",
    'website': "http://www.yourcompany.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/13.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Uncategorized',
    'version': '1.0.0',

    # any module necessary for this one to work correctly
    'depends': ['base', 'hr'],

    # always loaded
    'data': [

        'security/ir.model.access.csv',
        'security/security.xml',
        'data/sequence.xml',
        'views/menu.xml',
        'views/employee_clearance_view.xml',
        'views/approval_clearance_view.xml',
        'views/pending_approval_view.xml',
        'views/employee_view.xml',
        'report/employee_clearance_report.xml',
        'report/report.xml',

    ],
    # only loaded in demonstration mode
    'assets': {
        'web.assets_backend': [
            '/om_employee_clearance/static/src/css/style.css',
        ]},
    'demo': [
        'demo/demo.xml',
    ],

    'installable': True,
    "application": True,
    'auto_install': False,
    'license': 'LGPL-3',
}
