{
    "name": "L7 Stock API",
    "version": "16.0.1.3.1",
    "summary": "API externa de existencias de solo lectura por empresa",
    "description": """
L7 Stock API
============

API dedicada de solo lectura para consultar existencias.

Caracteristicas:
- Token independiente por proveedor.
- Empresa fija por token.
- Solo endpoints HTTP GET.
- No expone ORM generico de Odoo.
- No permite POST, PUT, PATCH o DELETE.
- Existencias limitadas a ubicaciones internas.
- Cantidad actual, reservada y disponible.
- Agrupacion por producto y ubicacion.
- Consulta individual por SKU o codigo de barras.
- Consulta de hasta 100 SKU en una sola peticion.
- Consulta de hasta 100 codigos de barras en una sola peticion.
- Resumen de encontrados, sin existencia y no encontrados.
- Paginacion.
- Filtros de consulta.
- Bitacora de accesos.
- Limite de peticiones por minuto.
""",
    "author": "Grupo L7",
    "license": "LGPL-3",
    "depends": [
        "base",
        "stock",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/api_client_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
