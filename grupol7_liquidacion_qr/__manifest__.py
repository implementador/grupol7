# -*- coding: utf-8 -*-
{
    "name": "Liquidación con QR (Cupones por pieza)",
    "summary": "Cupones QR para liquidación: valida producto y precio, un solo uso, POS y Ventas, reporte por PdV.",
    "version": "16.0.1.18",
    "author": "Grupo L7 / Implementación",
    "license": "LGPL-3",
    "depends": [
        "base",
        "sale",
        "point_of_sale",
        "stock",
        "barcodes",
    ],
    "data": [
        "security/ir.model.access.csv",
        # Reportes primero (declaran acciones usadas en vistas)
        "report/liquidation_labels.xml",
        # Vistas y menús
        "views/liquidation_coupon_views.xml",
        "views/liq_trace_views.xml",
        "views/menu_liq_root.xml",
        "views/report_liq_sales.xml",
    ],
    "assets": {
        # Carga los JS del POS (acepta archivos en static/src/js y/o static/src/pos)
        "point_of_sale.assets": [
            "grupol7_liquidacion_qr/static/src/js/*.js",
            "grupol7_liquidacion_qr/static/src/pos/*.js",
        ],
    },
    "installable": True,
    "application": False,
}
