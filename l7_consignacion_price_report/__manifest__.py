# -*- coding: utf-8 -*-

{
    "name": "L7 Lista de Consignacion",
    "version": "16.0.1.0.1",
    "summary": "Reporte Excel de consignaciones con precio mayoreo y empleado",
    "category": "Inventory/Inventory",
    "author": "Grupo Linea 7",
    "license": "LGPL-3",
    "depends": [
        "stock",
        "product",
    ],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "views/consignacion_report_wizard_views.xml",
    ],
    "post_init_hook": "post_init_hook",
    "installable": True,
    "application": False,
}
