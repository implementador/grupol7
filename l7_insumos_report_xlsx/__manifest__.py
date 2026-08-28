{
    "name": "L7 Reporte Gasto de Insumos",
    "version": "16.0.4.2.4",
    "category": "Inventory/Inventory",
    "summary": "Reporte historico y planeacion de gasto de insumos por area",
    "author": "Grupo Linea 7",
    "license": "LGPL-3",
    "depends": [
        "stock",
        "stock_account",
        "purchase",
    ],
    "external_dependencies": {
        "python": ["xlsxwriter"],
    },
    "data": [
        "security/insumos_report_security.xml",
        "security/ir.model.access.csv",
        "views/insumos_report_views.xml",
        "views/insumos_report_wizard_views.xml",
        "views/menu.xml",
    ],
    "installable": True,
    "application": False,
}
