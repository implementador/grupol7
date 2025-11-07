# -*- coding: utf-8 -*-
{
    "name": "Liquidación con QR (Cupones por pieza)",
    "summary": "Cupones QR para liquidación: valida producto y precio, un solo uso, POS y Ventas, reporte por PdV.",
    "version": "16.0.1.5",
    "author": "Grupo L7 / Implementación",
    "depends": ["base", "sale", "point_of_sale", "stock", "barcodes"],
    "data": [
        "security/ir.model.access.csv",
        "report/liquidation_labels.xml",          # <-- cargar primero el report (define action_liq_coupon_print_labels)
        "views/liquidation_coupon_views.xml",
        "views/wizard_views.xml",
        "views/menu_shortcuts.xml",
        "views/report_liq_sales.xml",
    ],
    "assets": {
        "point_of_sale.assets": [
            "grupol7_liquidacion_qr/static/src/js/liq_coupon_barcode.js",
            "grupol7_liquidacion_qr/static/src/js/liq_lock_price.js",
        ],
    },
    "license": "LGPL-3",
    "installable": True,
    "application": False,
}
