import hashlib
import json
import time
from datetime import datetime, timedelta

from odoo import fields, http
from odoo.http import request
from odoo.osv import expression


API_VERSION = "1.3"
MAX_MULTI_VALUES = 100


class L7StockApiController(http.Controller):

    # -------------------------------------------------------------------------
    # JSON
    # -------------------------------------------------------------------------

    def _json_response(self, payload, status=200):
        return request.make_response(
            json.dumps(
                payload,
                ensure_ascii=False,
                separators=(",", ":"),
            ),
            headers=[
                ("Content-Type", "application/json; charset=utf-8"),
                ("Cache-Control", "no-store"),
                ("Pragma", "no-cache"),
                ("X-Content-Type-Options", "nosniff"),
            ],
            status=status,
        )

    def _error(self, code, message, status):
        return self._json_response(
            {
                "ok": False,
                "error": {
                    "code": code,
                    "message": message,
                },
                "api_version": API_VERSION,
            },
            status=status,
        )

    # -------------------------------------------------------------------------
    # REQUEST
    # -------------------------------------------------------------------------

    def _get_remote_ip(self):
        http_request = request.httprequest

        try:
            route = http_request.access_route
            if route:
                return route[0]
        except Exception:
            pass

        return http_request.remote_addr or ""

    def _get_bearer_token(self):
        authorization = request.httprequest.headers.get(
            "Authorization",
            "",
        ).strip()

        if not authorization:
            return False

        parts = authorization.split(None, 1)

        if len(parts) != 2:
            return False

        if parts[0].lower() != "bearer":
            return False

        token = parts[1].strip()

        if not token:
            return False

        return token

    # -------------------------------------------------------------------------
    # AUTH
    # -------------------------------------------------------------------------

    def _authenticate(self):
        token = self._get_bearer_token()

        if not token:
            return False, self._error(
                "missing_token",
                "Se requiere Authorization: Bearer <token>.",
                401,
            )

        token_hash = hashlib.sha256(
            token.encode("utf-8")
        ).hexdigest()

        client = (
            request.env["l7.stock.api.client"]
            .sudo()
            .search(
                [
                    ("token_hash", "=", token_hash),
                    ("active", "=", True),
                ],
                limit=1,
            )
        )

        if not client:
            return False, self._error(
                "invalid_token",
                "Token invalido o inactivo.",
                401,
            )

        return client, False

    # -------------------------------------------------------------------------
    # RATE LIMIT
    # -------------------------------------------------------------------------

    def _check_rate_limit(self, client):
        rpm = max(
            client.requests_per_minute or 1,
            1,
        )

        since = datetime.utcnow() - timedelta(minutes=1)

        count = (
            request.env["l7.stock.api.log"]
            .sudo()
            .search_count(
                [
                    ("client_id", "=", client.id),
                    (
                        "requested_at",
                        ">=",
                        fields.Datetime.to_string(since),
                    ),
                ]
            )
        )

        return count < rpm

    # -------------------------------------------------------------------------
    # LOG
    # -------------------------------------------------------------------------

    def _log_request(
        self,
        client,
        status_code,
        result_count=0,
        started_at=None,
    ):
        duration_ms = 0

        if started_at is not None:
            duration_ms = int(
                max(
                    0,
                    (time.monotonic() - started_at) * 1000,
                )
            )

        http_request = request.httprequest

        try:
            query_string = http_request.query_string.decode(
                "utf-8",
                "replace",
            )
        except Exception:
            query_string = ""

        query_string = query_string[:2000]

        request.env["l7.stock.api.log"].sudo().create(
            {
                "client_id": client.id,
                "requested_at": fields.Datetime.now(),
                "remote_ip": self._get_remote_ip()[:128],
                "method": http_request.method[:16],
                "path": http_request.path[:512],
                "query_string": query_string,
                "status_code": int(status_code),
                "result_count": int(result_count or 0),
                "duration_ms": duration_ms,
                "user_agent": (
                    http_request.headers.get(
                        "User-Agent",
                        "",
                    )[:512]
                ),
            }
        )

        client.sudo().write(
            {
                "last_used_at": fields.Datetime.now(),
            }
        )

    # -------------------------------------------------------------------------
    # PARSING
    # -------------------------------------------------------------------------

    def _parse_positive_int(
        self,
        value,
        default,
        minimum=0,
        maximum=None,
    ):
        try:
            result = int(value)
        except (TypeError, ValueError):
            result = default

        result = max(result, minimum)

        if maximum is not None:
            result = min(result, maximum)

        return result

    def _parse_multi_values(self, raw_value):
        if not raw_value:
            return []

        values = []
        seen = set()

        for raw_item in raw_value.split(","):
            value = raw_item.strip()

            if not value:
                continue

            normalized = value.casefold()

            if normalized in seen:
                continue

            seen.add(normalized)
            values.append(value)

        return values

    def _exact_or_domain(self, field_name, values):
        if not values:
            return []

        return expression.OR(
            [
                [
                    (
                        field_name,
                        "=ilike",
                        value,
                    )
                ]
                for value in values
            ]
        )

    # -------------------------------------------------------------------------
    # WAREHOUSE
    # -------------------------------------------------------------------------

    def _warehouse_map(self, company):
        warehouses = (
            request.env["stock.warehouse"]
            .sudo()
            .search(
                [
                    ("company_id", "=", company.id),
                ]
            )
        )

        result = []

        for warehouse in warehouses:
            if not warehouse.view_location_id:
                continue

            result.append(
                {
                    "id": warehouse.id,
                    "name": warehouse.name,
                    "view_location_id": (
                        warehouse.view_location_id.id
                    ),
                }
            )

        return result

    def _warehouse_for_location(
        self,
        location,
        warehouses,
    ):
        parent_path = location.parent_path or ""

        ancestor_ids = set()

        for value in parent_path.strip("/").split("/"):
            if value.isdigit():
                ancestor_ids.add(int(value))

        ancestor_ids.add(location.id)

        matches = [
            warehouse
            for warehouse in warehouses
            if warehouse["view_location_id"] in ancestor_ids
        ]

        if not matches:
            return False

        return matches[-1]

    # -------------------------------------------------------------------------
    # REQUESTED ITEM SUMMARY
    # -------------------------------------------------------------------------

    def _requested_product_summary(
        self,
        company,
        field_name,
        requested_values,
    ):
        if not requested_values:
            return []

        Product = (
            request.env["product.product"]
            .sudo()
            .with_context(active_test=False)
        )

        company_domain = [
            "|",
            ("company_id", "=", False),
            ("company_id", "=", company.id),
        ]

        requested_domain = self._exact_or_domain(
            field_name,
            requested_values,
        )

        product_domain = expression.AND(
            [
                company_domain,
                requested_domain,
            ]
        )

        products = Product.search(product_domain)

        products_by_value = {}

        for product in products:
            value = getattr(product, field_name, False)

            if not value:
                continue

            key = str(value).casefold()

            products_by_value.setdefault(
                key,
                [],
            ).append(product)

        product_ids = products.ids

        qty_by_product = {}

        if product_ids:
            summary_domain = [
                ("company_id", "=", company.id),
                ("location_id.usage", "=", "internal"),
                ("quantity", ">", 0),
                ("product_id", "in", product_ids),
            ]

            grouped = (
                request.env["stock.quant"]
                .sudo()
                .read_group(
                    summary_domain,
                    [
                        "product_id",
                        "quantity:sum",
                        "reserved_quantity:sum",
                    ],
                    [
                        "product_id",
                    ],
                    lazy=False,
                )
            )

            for row in grouped:
                product_data = row.get("product_id")

                if not product_data:
                    continue

                product_id = product_data[0]

                quantity = float(
                    row.get("quantity") or 0.0
                )

                reserved = float(
                    row.get("reserved_quantity") or 0.0
                )

                qty_by_product[product_id] = {
                    "quantity": quantity,
                    "reserved": reserved,
                    "available": quantity - reserved,
                }

        result = []

        response_key = (
            "sku"
            if field_name == "default_code"
            else "barcode"
        )

        for requested_value in requested_values:
            key = requested_value.casefold()

            matching_products = products_by_value.get(
                key,
                [],
            )

            quantity = 0.0
            reserved = 0.0
            available = 0.0

            names = []

            for product in matching_products:
                names.append(product.name or "")

                quantities = qty_by_product.get(
                    product.id,
                    {
                        "quantity": 0.0,
                        "reserved": 0.0,
                        "available": 0.0,
                    },
                )

                quantity += quantities["quantity"]
                reserved += quantities["reserved"]
                available += quantities["available"]

            result.append(
                {
                    response_key: requested_value,
                    "found": bool(matching_products),
                    "product_count": len(
                        matching_products
                    ),
                    "products": list(
                        dict.fromkeys(names)
                    ),
                    "quantity": round(
                        quantity,
                        6,
                    ),
                    "reserved": round(
                        reserved,
                        6,
                    ),
                    "available": round(
                        available,
                        6,
                    ),
                }
            )

        return result

    # -------------------------------------------------------------------------
    # HEALTH
    # -------------------------------------------------------------------------

    @http.route(
        "/l7-stock-api/v1/health",
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
        sitemap=False,
    )
    def health(self, **kwargs):
        started_at = time.monotonic()

        client, error = self._authenticate()

        if error:
            return error

        if not self._check_rate_limit(client):
            self._log_request(
                client,
                429,
                result_count=0,
                started_at=started_at,
            )

            return self._error(
                "rate_limit",
                "Se excedio el limite de peticiones por minuto.",
                429,
            )

        payload = {
            "ok": True,
            "api_version": API_VERSION,
            "service": "L7 Stock API",
            "company": {
                "id": client.company_id.id,
                "name": client.company_id.name,
            },
            "capabilities": {
                "single_sku": True,
                "multiple_skus": True,
                "single_barcode": True,
                "multiple_barcodes": True,
                "full_stock_summary": True,
                "summary_aggregation": "sku",
                "signed_image_urls": True,
                "image_size": 512,
                "image_auth": "signed_url",
                "max_multi_values": MAX_MULTI_VALUES,
                "write": False,
            },
            "max_page_size": client.max_page_size,
            "generated_at": (
                datetime.utcnow()
                .replace(microsecond=0)
                .isoformat()
                + "Z"
            ),
        }

        self._log_request(
            client,
            200,
            result_count=0,
            started_at=started_at,
        )

        return self._json_response(
            payload,
            200,
        )

    # -------------------------------------------------------------------------
    # STOCK
    # -------------------------------------------------------------------------

    @http.route(
        "/l7-stock-api/v1/stock",
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
        sitemap=False,
    )
    def stock(self, **kwargs):
        started_at = time.monotonic()

        client, error = self._authenticate()

        if error:
            return error

        if not self._check_rate_limit(client):
            self._log_request(
                client,
                429,
                result_count=0,
                started_at=started_at,
            )

            return self._error(
                "rate_limit",
                "Se excedio el limite de peticiones por minuto.",
                429,
            )

        company = client.company_id
        args = request.httprequest.args

        max_page_size = max(
            client.max_page_size or 1000,
            1,
        )

        limit = self._parse_positive_int(
            args.get("limit"),
            default=min(
                500,
                max_page_size,
            ),
            minimum=1,
            maximum=max_page_size,
        )

        offset = self._parse_positive_int(
            args.get("offset"),
            default=0,
            minimum=0,
        )

        sku = (
            args.get("sku") or ""
        ).strip()

        barcode = (
            args.get("barcode") or ""
        ).strip()

        skus = self._parse_multi_values(
            args.get("skus")
        )

        barcodes = self._parse_multi_values(
            args.get("barcodes")
        )

        product_name = (
            args.get("product") or ""
        ).strip()

        location_name = (
            args.get("location") or ""
        ).strip()

        # ---------------------------------------------------------------------
        # Validaciones de filtros
        # ---------------------------------------------------------------------

        if sku and skus:
            self._log_request(
                client,
                400,
                result_count=0,
                started_at=started_at,
            )

            return self._error(
                "invalid_filters",
                "Usa sku o skus, pero no ambos.",
                400,
            )

        if barcode and barcodes:
            self._log_request(
                client,
                400,
                result_count=0,
                started_at=started_at,
            )

            return self._error(
                "invalid_filters",
                "Usa barcode o barcodes, pero no ambos.",
                400,
            )

        if len(skus) > MAX_MULTI_VALUES:
            self._log_request(
                client,
                400,
                result_count=0,
                started_at=started_at,
            )

            return self._error(
                "too_many_skus",
                (
                    "Se permiten maximo %s SKU por peticion."
                    % MAX_MULTI_VALUES
                ),
                400,
            )

        if len(barcodes) > MAX_MULTI_VALUES:
            self._log_request(
                client,
                400,
                result_count=0,
                started_at=started_at,
            )

            return self._error(
                "too_many_barcodes",
                (
                    "Se permiten maximo %s codigos de barras "
                    "por peticion."
                    % MAX_MULTI_VALUES
                ),
                400,
            )

        # ---------------------------------------------------------------------
        # Dominio base
        #
        # IMPORTANTE:
        # company_id NO procede del request.
        # Siempre procede del token.
        # ---------------------------------------------------------------------

        domain = [
            ("company_id", "=", company.id),
            ("location_id.usage", "=", "internal"),
            ("quantity", ">", 0),
        ]

        # ---------------------------------------------------------------------
        # SKU individual: compatibilidad V1.0
        # Busqueda parcial.
        # ---------------------------------------------------------------------

        if sku:
            domain.append(
                (
                    "product_id.default_code",
                    "ilike",
                    sku,
                )
            )

        # ---------------------------------------------------------------------
        # SKU multiples: coincidencia exacta, case-insensitive
        # ---------------------------------------------------------------------

        if skus:
            domain = expression.AND(
                [
                    domain,
                    self._exact_or_domain(
                        "product_id.default_code",
                        skus,
                    ),
                ]
            )

        # ---------------------------------------------------------------------
        # Barcode individual
        # ---------------------------------------------------------------------

        if barcode:
            domain.append(
                (
                    "product_id.barcode",
                    "ilike",
                    barcode,
                )
            )

        # ---------------------------------------------------------------------
        # Barcodes multiples
        # ---------------------------------------------------------------------

        if barcodes:
            domain = expression.AND(
                [
                    domain,
                    self._exact_or_domain(
                        "product_id.barcode",
                        barcodes,
                    ),
                ]
            )

        if product_name:
            domain.append(
                (
                    "product_id.name",
                    "ilike",
                    product_name,
                )
            )

        if location_name:
            domain.append(
                (
                    "location_id.complete_name",
                    "ilike",
                    location_name,
                )
            )

        Quant = request.env["stock.quant"].sudo()

        # Solicitamos uno extra para saber si existe pagina siguiente.
        grouped = Quant.read_group(
            domain,
            [
                "product_id",
                "location_id",
                "quantity:sum",
                "reserved_quantity:sum",
            ],
            [
                "product_id",
                "location_id",
            ],
            offset=offset,
            limit=limit + 1,
            orderby="product_id,location_id",
            lazy=False,
        )

        has_more = len(grouped) > limit
        grouped = grouped[:limit]

        product_ids = []
        location_ids = []

        for row in grouped:
            product = row.get("product_id")
            location = row.get("location_id")

            if product:
                product_ids.append(
                    product[0]
                )

            if location:
                location_ids.append(
                    location[0]
                )

        products = (
            request.env["product.product"]
            .sudo()
            .browse(
                list(set(product_ids))
            )
            .exists()
        )

        locations = (
            request.env["stock.location"]
            .sudo()
            .browse(
                list(set(location_ids))
            )
            .exists()
        )

        products_by_id = {
            product.id: product
            for product in products
        }

        locations_by_id = {
            location.id: location
            for location in locations
        }

        warehouses = self._warehouse_map(
            company
        )

        rows = []

        for group in grouped:
            product_data = group.get(
                "product_id"
            )

            location_data = group.get(
                "location_id"
            )

            if not product_data or not location_data:
                continue

            product_id = product_data[0]
            location_id = location_data[0]

            product = products_by_id.get(
                product_id
            )

            location = locations_by_id.get(
                location_id
            )

            if not product or not location:
                continue

            quantity = float(
                group.get("quantity") or 0.0
            )

            reserved = float(
                group.get(
                    "reserved_quantity"
                ) or 0.0
            )

            available = quantity - reserved

            warehouse = (
                self._warehouse_for_location(
                    location,
                    warehouses,
                )
            )

            variant_values = (
                product
                .product_template_attribute_value_ids
                .mapped("name")
            )

            rows.append(
                {
                    "product_id": product.id,
                    "sku": (
                        product.default_code
                        or ""
                    ),
                    "barcode": (
                        product.barcode
                        or ""
                    ),
                    "product": (
                        product.name
                        or ""
                    ),
                    "variant": ", ".join(
                        variant_values
                    ),
                    "uom": (
                        product.uom_id.name
                        if product.uom_id
                        else ""
                    ),
                    "location_id": (
                        location.id
                    ),
                    "location": (
                        location.complete_name
                        or location.name
                    ),
                    "warehouse_id": (
                        warehouse["id"]
                        if warehouse
                        else False
                    ),
                    "warehouse": (
                        warehouse["name"]
                        if warehouse
                        else ""
                    ),
                    "quantity": round(
                        quantity,
                        6,
                    ),
                    "reserved": round(
                        reserved,
                        6,
                    ),
                    "available": round(
                        available,
                        6,
                    ),
                }
            )

        # ---------------------------------------------------------------------
        # Resumen de solicitudes multiples
        #
        # Este resumen NO depende de la paginacion y permite saber:
        # - found=true + available > 0
        # - found=true + available = 0
        # - found=false
        # ---------------------------------------------------------------------

        requested_sku_summary = (
            self._requested_product_summary(
                company,
                "default_code",
                skus,
            )
            if skus
            else []
        )

        requested_barcode_summary = (
            self._requested_product_summary(
                company,
                "barcode",
                barcodes,
            )
            if barcodes
            else []
        )

        payload = {
            "ok": True,
            "api_version": API_VERSION,
            "company": {
                "id": company.id,
                "name": company.name,
            },
            "generated_at": (
                datetime.utcnow()
                .replace(microsecond=0)
                .isoformat()
                + "Z"
            ),
            "pagination": {
                "offset": offset,
                "limit": limit,
                "count": len(rows),
                "has_more": has_more,
                "next_offset": (
                    offset + limit
                    if has_more
                    else False
                ),
            },
            "filters": {
                "sku": sku,
                "skus": skus,
                "barcode": barcode,
                "barcodes": barcodes,
                "product": product_name,
                "location": location_name,
            },
            "requested": {
                "skus": requested_sku_summary,
                "barcodes": requested_barcode_summary,
            },
            "stock": rows,
        }

        self._log_request(
            client,
            200,
            result_count=len(rows),
            started_at=started_at,
        )

        return self._json_response(
            payload,
            200,
        )
