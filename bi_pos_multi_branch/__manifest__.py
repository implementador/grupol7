# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

{
    "name": "POS Multi Branch in Odoo",
    "version": "16.0.0.1",
    "category": "Point of Sale",
    'summary': 'POS Multi Branch user Multiple Branch Management POS Multi Branch Multiple Unit Operating unit pos multiple branch point of Sales branch pos branch unit branch unit for pos Multi Branches multi company point of sale multi branch point of sales multi branch',
    'description': """

        POS Multi Branch in Odoo
        Branch on POS Receipt in odoo,
        Branch on POS Session in odoo,
        Branch on POS Order in odoo,
        Branch on POS Picking in odoo,
        Branch on Invoice in odoo,
        Branch on Journal Entry in odoo,

    """,
    'author': 'BrowseInfo',
    "price": 40,
    "currency": 'EUR',
    'website': 'https://www.browseinfo.in',
    "depends": ['point_of_sale', 'bi_branch_invoice', 'bi_branch_inventory'],
    "data": [
        'security/branch_pos_security.xml',
        'views/pos_branch_view.xml',
    ],
    'qweb': ['static/src/xml/pos.xml'],
    'assets': {
        'point_of_sale.assets': [
            'bi_pos_multi_branch/static/src/xml/**/*',
            'bi_pos_multi_branch/static/src/js/pos_extended.js',
        ]
    },
    'license': 'OPL-1',
    "auto_install": False,
    "installable": True,
    'live_test_url': 'https://youtu.be/oVeEHX_mbvM',
    "images": ['static/description/Banner.png'],
}

