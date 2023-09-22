# -*- coding: utf-8 -*-
{
    'name': 'Uso y Forma de Pago por defecto (Localización-Mexicana)',

    'summary': """
    Es posible definir valores por defecto de "Uso" y "Forma de Pago" del cliente.""",

    'description': """
    Al crear una factura y seleccionar el cliente, se heredarán los campos "Uso" y "Forma de Pago" del cliente.
    """,

    'author': 'Lava Studio',
    'support': 'gonzalo@lava.mx',
    'license': 'OPL-1',
    'website': 'http://www.lava.mx',
    'currency': 'USD',
    'price': 17.00,
    'maintainer': 'Gonzalo Jacques',
    # 'live_test_url': 'https://www.youtube.com/watch?v=vWjKCwlyMdE',
    'images': ['static/description/banner.png'],

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/master/odoo/addons/base/module/module_data.xml
    # for the full list
    'category': 'Invoice',
    'version': '16.0.1.0',

    # any module necessary for this one to work correctly
    # TODO: Quitar la dependencia de ventas, dividirlo en dos módulos o tres, base, ventas y facturación, 4to POS
    # Desarrollo: Agregar Cliente en Ticket
    # Investigar: Hacer factura en Punto de Venta
    'depends': ['base', 'account', 'l10n_mx_edi'],

    # always loaded
    'data': [
        'views/res_partner_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'pre_init_hook': 'pre_init_check',
}
