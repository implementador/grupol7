# -*- coding: utf-8 -*-
{
    "name": "Liquidación con QR (Cupones por pieza)",
    "summary": "Cupones QR para liquidación: valida producto y precio, un solo uso, POS y Ventas, reporte por PdV.",
    "version": "16.0.1.46",
    "author": "Grupo L7 / Implementación",
    "depends": ["base", "sale", "point_of_sale", "stock", "barcodes"],
    "data": [
        "security/ir.model.access.csv",
        "report/liquidation_labels.xml",
        "views/liquidation_coupon_views.xml",
          "views/liq_coupon_location_views.xml",
        "views/liq_trace_views.xml",
        "views/menu_liq_root.xml",
        "views/report_liq_sales.xml",
        # "data/barcode_rules.xml",
    ],
    "assets": {
        "point_of_sale.assets": [
            "grupol7_liquidacion_qr/static/src/js/qr_button_ux.js",
            "grupol7_liquidacion_qr/static/src/js/qr_button_action.js",
        "grupol7_liquidacion_qr/static/src/js/rename_note_button_dom_patch.js",
            "grupol7_liquidacion_qr/static/src/js/liq_lock_price.js",
"grupol7_liquidacion_qr/static/src/xml/qr_button.xml",
            "grupol7_liquidacion_qr/static/src/xml/pos_rename_note_button.xml",
        ],
    },
    "license": "LGPL-3",
    "installable": True,
    "application": False,
}
