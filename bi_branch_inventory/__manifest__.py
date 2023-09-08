# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Inventory Multi Branch in Odoo',
    'version': '16.0.0.0',
    'category': 'Warehouse',
    'summary': 'Multi Branch Inventory Multiple Branch warehouse multi branch stock multi branch warehouse multiple branch stock multiple branch inventory multi unit warehouse multi unit inventory multi operation multi branch transfer multi branch operation multi branches',
    "description": """
       
       Inventory Multi Branch in odoo,
       multiple Branch for incoming shipment in odoo,
       multiple Branch for outgoing shipment in odoo,
       multiple Branch for warehouse in odoo,
       multiple Branch for stock location in odoo,
       multiple Branch for Inventory Adjustment in odoo,
       multiple Branch for stock move in odoo,
       multiple Branch for product move in odoo,

    """,
    'author': 'BrowseInfo',
    "price": 30,
    "currency": 'EUR',
    'website': 'https://www.browseinfo.in',
    'depends': ['stock', 'bi_branch_base'],
    'data': [
        'security/branch_security.xml',
        'security/ir.model.access.csv',
        'views/inherited_stock_picking.xml',
        'views/inherited_stock_move.xml',
        'views/inherited_stock_warehouse.xml',
        'views/inherited_stock_location.xml',
        'views/inherited_product.xml',
    ],
    'license': 'OPL-1',
    'installable': True,
    'auto_install': False,
    'live_test_url': 'https://youtu.be/q3Xcs26RXdM',
    "images": ['static/description/Banner.gif'],
}

