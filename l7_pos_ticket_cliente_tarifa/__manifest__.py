{
    'name': 'GL7 POS - Cliente y lista de precios',
    'version': '16.0.1.0.0',
    'category': 'Point of Sale',
    'license': 'LGPL-3',
    'depends': [
        'point_of_sale',
        'bi_pos_multi_branch',
        'bi_pos_pay_later',
        'bi_pos_reprint_reorder',
    ],
    'assets': {
        'point_of_sale.assets': [
            'l7_pos_ticket_cliente_tarifa/static/src/xml/receipt_meta.xml',
        ],
    },
    'installable': True,
    'application': False,
}
