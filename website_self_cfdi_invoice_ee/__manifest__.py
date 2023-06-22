# -*- coding: utf-8 -*-
{
    'name': "Portal de Auto-Facturacion CFDI",

    'summary': """
        Portal de Cliente diseñado para generar facturas desde la Web.""",

    'description': """

Portal Auto-Facturacion CFDI
================================

Permite al Cliente poder generar su Factura mediante la Parte Web.

    """,

    'author': "Lava Studio",
    'website': "www.lava.mx",
    'category': 'Facturacion Electronica',
    'version': '16.02',
    'depends': [
        'website_sale_stock',
        'website_crm',
        'sale_management',
        'l10n_mx_edi',
        'point_of_sale',
    ],
    'assets': {
        'web.assets_common': [
            '/website_self_cfdi_invoice_ee/static/src/**/*',
        ],
    },
    'data': [
        'security/ir.model.access.csv',
        'views/templates.xml',
        'views/point_of_sale_view.xml',
        'views/sale_order_view.xml',
    ],

}
