# -*- coding: utf-8 -*-
{
    'name': "Cantidad 0 en Entradas",

    'summary': """
        Este modulo simplemente permite que las entradas de productos tengan cantidad 0 en transferencias de entrada""",

    'description': """
        Este modulo simplemente permite que las entradas de productos tengan cantidad 0 en transferencias de entrada
    """,

    'author': "GonzaOdoo",
    'website': "https://github.com/GonzaOdoo",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/master/odoo/addons/base/module/module_data.xml
    # for the full list
    'category': 'Stock',
    'version': '1.0',

    # any module necessary for this one to work correctly
    'depends': ['stock','purchase','l10n_xma_einvoice','helpdesk'],
    'data':['security/ir.model.access.csv',
            'views/stock_picking.xml',
            'views/res_users.xml',
            'views/purchase_pending.xml',
            'views/stock_uom.xml',
            'views/purchase_requirements.xml'],
    
}