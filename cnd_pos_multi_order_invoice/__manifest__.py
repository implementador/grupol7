# -*- coding: utf-8 -*-
{
    'name': 'Factura Global POS (Mexico-SAT)',

    'summary': """
    Con este módulo puedes generar una Factura Global de pedidos de Punto de Venta de sesiones abiertas o cerradas.""",

    'description': """
    Factura Global de pedidos de Punto de Venta que cumple con los requisitos del SAT o factura genérica para cualquier cliente.""",

    'author': 'Lava Studio',
    'support': 'gonzalo@lava.mx',
    'license': 'OPL-1',
    'website': 'http://www.lava.mx',
    'currency': 'USD',
    'price': 200.00,
    'maintainer': 'Gonzalo Jacques',
    # 'live_test_url': 'https://www.youtube.com/watch?v=vWjKCwlyMdE',
    'images': ['static/description/banner.png'],

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/master/odoo/addons/base/module/module_data.xml
    # for the full list
    'category': 'Point of Sale',
    'version': '16.0.3.0',

    # Changelog
    # 15.0.1.4: price_subtotal > 0.00 to be included on the global invoice
    # 15.0.1.5: line.price_subtotal < 0.00 and invoice_type == 'out_refund'
    # 15.0.1.6: Al crear la factura global y la nota de crédito con método de pago:
    #           "CUSTOMER ACCOUNT" "pos.payment.method".type = 'pay_later',
    #           automáticamente desvincular la factura de la nota de crédito, la nota de crédito
    #           vincularla con las pólizas de los pedidos de POS y dejar la factura
    #           global lista para registrar el pago y poder generar el complemento de pago.
    # 15.0.1.7: Add the Reverse Move to the Session Journal Items.
    # 15.0.1.8: Add the periodicity node and module configuration for CFDI 4.0.
    # 15.0.2.0: Opcion para facturación con cuentas de orden, repara facturacion en modulo de contabilidad y facturas para ordenes con metodo de pago "Customer Account"


    # TODO:
    # 1. Colocar un campo para indicar que es factura global, en factura y en Nota de crédito
    # 2. Agregar ese campo en el Análisis de Facturas
    # 3. Tener la opción de crear o no la Nota de crédito

    # any module necessary for this one to work correctly
    'depends': [
        'base',
        'uom',
        'point_of_sale',
        'account',
        'l10n_mx_edi_40',
        'cnd_l10n_mx_partner_edi_defaults_invoice',
    ],

    # always loaded
    'data': [
        'security/res_groups.xml',
        'security/ir.model.access.csv',
        'views/account_account_views.xml',
        'views/pos_order_views.xml',
        'views/res_config_setting.xml',
        'views/pos_payment_method_views.xml',
        'views/account_move_views.xml',
        'views/product_template_views.xml',
        'views/l10n_mx_edi_cfdiv33.xml',
        'views/l10n_mx_edi_cfdi_40.xml',
        'wizard/wizard_pos_invoice.xml',
        'data/global_invoice_data.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
    'pre_init_hook': 'pre_init_check',
    'post_init_hook': 'post_init_hook',
}
# https://exdoo.mx/factura-global-de-punto-de-venta-con-odoo/
