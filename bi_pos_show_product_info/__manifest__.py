# -*- coding: utf-8 -*-
# Part of Lava. See LICENSE file for full copyright and licensing details.
{
    'name': "POS Show Product Info",
    'version': '16.0.0.0',
    'category': 'Point of Sale',
    'summary': "POS Show Product Info",
    'description': """ 

        POS show Product Info in odoo,
        Configure show Product Info in odoo,
        Enable show Product Info in odoo

    """,
    "author": "Lava Studio",
    "price": 0,
    "currency": 'EUR',
    "website" : "https://www.lava.mx",
    'depends': ['base', 'point_of_sale'],
    'data': [
        'views/pos_config.xml',
    ],
    'assets': {
        'point_of_sale.assets': [
            'bi_pos_show_product_info/static/src/xml/Screens/ProductScreen/ProductItem.xml',
            'bi_pos_show_product_info/static/src/js/Screens/ProductScreen/ProductScreen.js',
            'bi_pos_show_product_info/static/src/css/pos.css',
        ],
    },
    'license': 'OPL-1',
    "auto_install": False,
    "installable": True,
    'live_test_url':'',
    "images":['static/description/Banner.gif'],
}

