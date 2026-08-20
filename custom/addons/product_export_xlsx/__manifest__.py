{
    "name": "Product XLSX Export",
    "summary": "Generacion y descarga del catalogo completo de productos",
    "version": "16.0.1.5.0",
    "category": "Inventory/Inventory",
    "author": "Grupo Linea 7",
    "license": "LGPL-3",
    "depends": [
        "base",
        "product",
        "stock",
    ],
    "external_dependencies": {
        "python": ["xlsxwriter"],
    },
    "data": [
        "security/product_export_security.xml",
        "security/ir.model.access.csv",
        "views/product_export_views.xml",
        "views/product_export_wizard_views.xml",
        "views/menu.xml",
        "data/ir_cron.xml",
    ],
    "installable": True,
    "application": False,
}
