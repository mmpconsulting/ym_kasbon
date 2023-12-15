# -*- coding: utf-8 -*-
{
    'name': "Kasbon",

    'summary': """
        Modul Kasbon for Odoo 17""",

    'description': """
        Kasbon for Odoo 17
    """,

    'author': "MMP",
    'website': "mmpconsulting.net",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/16.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Uncategorized',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base', 'base_setup', 'account', 'hr', 'analytic', 'account_accountant', 'digest'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'security/security.xml',
        # 'views/report_bukti_bank_keluar.xml',
        # 'views/report_bukti_bank_masuk.xml',
        # 'views/report_bukti_kas_keluar.xml',
        # 'views/report_bukti_kas_masuk.xml',
        'views/views.xml',
        'views/templates.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
    'application': True,
}
