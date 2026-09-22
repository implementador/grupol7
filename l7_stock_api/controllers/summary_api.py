import hashlib
import hmac
import json
import time
from datetime import datetime, timedelta

from odoo import fields, http
from odoo.http import request


API_VERSION = "1.3"
MAX_PAGE_SIZE = 1000


class L7StockApiSummaryController(http.Controller):

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
                (
                    "Content-Type",
                    "application/json; charset=utf-8",
                ),
                (
                    "Cache-Control",
                    "no-store",
                ),
                (
                    "Pragma",
                    "no-cache",
                ),
                (
                    "X-Content-Type-Options",
                    "nosniff",
                ),
            ],
            status=status,
        )

    def _error(
        self,
        code,
        message,
        status,
    ):
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
    # AUTH
    # -------------------------------------------------------------------------

    def _get_bearer_token(self):
        authorization = (
            request.httprequest.headers.get(
                "Authorization",
                "",
            )
            .strip()
        )

        if not authorization:
            return False

        parts = authorization.split(
            None,
            1,
        )

        if len(parts) != 2:
            return False

        if parts[0].lower() != "bearer":
            return False

        token = parts[1].strip()

        return token or False

    def _authenticate(self):
        token = self._get_bearer_token()

        if not token:
            return False, self._error(
                "missing_token",
                (
                    "Se requiere Authorization: "
                    "Bearer <token>."
                ),
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
                    (
                        "token_hash",
                        "=",
                        token_hash,
                    ),
                    (
                        "active",
                        "=",
                        True,
                    ),
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

    def _check_rate_limit(
        self,
        client,
    ):
        rpm = max(
            client.requests_per_minute
            or 1,
            1,
        )

        since = (
            datetime.utcnow()
            - timedelta(minutes=1)
        )

        count = (
            request.env["l7.stock.api.log"]
            .sudo()
            .search_count(
                [
                    (
                        "client_id",
                        "=",
                        client.id,
                    ),
                    (
                        "requested_at",
                        ">=",
                        fields.Datetime.to_string(
                            since
                        ),
                    ),
                ]
            )
        )

        return count < rpm

    # -------------------------------------------------------------------------
    # LOG
    # -------------------------------------------------------------------------

    def _remote_ip(self):
        try:
            route = (
                request.httprequest
                .access_route
            )

            if route:
                return route[0]

        except Exception:
            pass

        return (
            request.httprequest
            .remote_addr
            or ""
        )

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
                    (
                        time.monotonic()
                        - started_at
                    )
                    * 1000,
                )
            )

        try:
            query_string = (
                request.httprequest
                .query_string
                .decode(
                    "utf-8",
                    "replace",
                )
            )
        except Exception:
            query_string = ""

        request.env[
            "l7.stock.api.log"
        ].sudo().create(
            {
                "client_id": client.id,
                "requested_at": (
                    fields.Datetime.now()
                ),
                "remote_ip": (
                    self._remote_ip()[:128]
                ),
                "method": (
                    request.httprequest
                    .method[:16]
                ),
                "path": (
                    request.httprequest
                    .path[:512]
                ),
                "query_string": (
                    query_string[:2000]
                ),
                "status_code": int(
                    status_code
                ),
                "result_count": int(
                    result_count or 0
                ),
                "duration_ms": (
                    duration_ms
                ),
                "user_agent": (
                    request.httprequest
                    .headers.get(
                        "User-Agent",
                        "",
                    )[:512]
                ),
            }
        )

        client.sudo().write(
            {
                "last_used_at": (
                    fields.Datetime.now()
                ),
            }
        )

    # -------------------------------------------------------------------------
    # PARSING
    # -------------------------------------------------------------------------

    def _parse_int(
        self,
        value,
        default,
        minimum=0,
        maximum=None,
    ):
        try:
            result = int(value)
        except (
            TypeError,
            ValueError,
        ):
            result = default

        result = max(
            result,
            minimum,
        )

        if maximum is not None:
            result = min(
                result,
                maximum,
            )

        return result

    # -------------------------------------------------------------------------
    # SIGNED IMAGE URL
    # -------------------------------------------------------------------------

    def _image_signature(
        self,
        client,
        product_id,
    ):
        message = (
            "l7-stock-image-v1|%s|%s|%s"
            % (
                client.id,
                client.company_id.id,
                product_id,
            )
        ).encode("utf-8")

        key = (
            client.token_hash
            or ""
        ).encode("utf-8")

        return hmac.new(
            key,
            message,
            hashlib.sha256,
        ).hexdigest()

    def _image_url(
        self,
        client,
        product_id,
    ):
        signature = (
            self._image_signature(
                client,
                product_id,
            )
        )

        base_url = (
            request.httprequest
            .host_url
            .rstrip("/")
        )

        return (
            "%s/l7-stock-api/v1/product/%s/image"
            "?client=%s&sig=%s"
            % (
                base_url,
                product_id,
                client.id,
                signature,
            )
        )

    # -------------------------------------------------------------------------
    # SUMMARY
    # -------------------------------------------------------------------------

    @http.route(
        "/l7-stock-api/v1/stock/summary",
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
        sitemap=False,
    )
    def stock_summary(
        self,
        **kwargs,
    ):
        started_at = time.monotonic()

        client, error = (
            self._authenticate()
        )

        if error:
            return error

        if not self._check_rate_limit(
            client
        ):
            self._log_request(
                client,
                429,
                result_count=0,
                started_at=started_at,
            )

            return self._error(
                "rate_limit",
                (
                    "Se excedio el limite "
                    "de peticiones por minuto."
                ),
                429,
            )

        company = client.company_id
        args = request.httprequest.args

        client_max_page_size = max(
            client.max_page_size
            or MAX_PAGE_SIZE,
            1,
        )

        max_limit = min(
            client_max_page_size,
            MAX_PAGE_SIZE,
        )

        limit = self._parse_int(
            args.get("limit"),
            default=max_limit,
            minimum=1,
            maximum=max_limit,
        )

        offset = self._parse_int(
            args.get("offset"),
            default=0,
            minimum=0,
        )

        # ---------------------------------------------------------------------
        # SEGURIDAD
        #
        # company_id SIEMPRE procede del token.
        #
        # Solo ubicaciones internas.
        #
        # Solo productos con cantidad o reserva distinta de cero.
        # ---------------------------------------------------------------------

        domain = [
            (
                "company_id",
                "=",
                company.id,
            ),
            (
                "location_id.usage",
                "=",
                "internal",
            ),
            (
                "product_id.default_code",
                "!=",
                False,
            ),
            "|",
            (
                "quantity",
                "!=",
                0,
            ),
            (
                "reserved_quantity",
                "!=",
                0,
            ),
        ]

        grouped = (
            request.env["stock.quant"]
            .sudo()
            .read_group(
                domain,
                [
                    "product_id",
                    "quantity:sum",
                    (
                        "reserved_quantity:"
                        "sum"
                    ),
                ],
                [
                    "product_id",
                ],
                lazy=False,
            )
        )

        product_ids = []

        for group in grouped:
            product_data = (
                group.get(
                    "product_id"
                )
            )

            if product_data:
                product_ids.append(
                    product_data[0]
                )

        products = (
            request.env[
                "product.product"
            ]
            .sudo()
            .browse(
                list(
                    set(product_ids)
                )
            )
            .exists()
        )

        products_by_id = {
            product.id: product
            for product in products
        }

        # ---------------------------------------------------------------------
        # UNA FILA POR SKU
        # ---------------------------------------------------------------------

        by_sku = {}

        for group in grouped:
            product_data = (
                group.get(
                    "product_id"
                )
            )

            if not product_data:
                continue

            product_id = (
                product_data[0]
            )

            product = (
                products_by_id.get(
                    product_id
                )
            )

            if not product:
                continue

            sku = (
                product.default_code
                or ""
            ).strip()

            if not sku:
                continue

            quantity = float(
                group.get(
                    "quantity"
                )
                or 0.0
            )

            reserved = float(
                group.get(
                    "reserved_quantity"
                )
                or 0.0
            )

            key = sku.casefold()

            if key not in by_sku:
                variant_values = (
                    product
                    .product_template_attribute_value_ids
                    .mapped("name")
                )

                by_sku[key] = {
                    "sku": sku,
                    "product_id": (
                        product.id
                    ),
                    "product": (
                        product.name
                        or ""
                    ),
                    "variant": (
                        ", ".join(
                            variant_values
                        )
                    ),
                    "barcode": (
                        product.barcode
                        or ""
                    ),
                    "uom": (
                        product.uom_id.name
                        if product.uom_id
                        else ""
                    ),
                    "product_count": 0,
                    "quantity": 0.0,
                    "reserved": 0.0,
                    "available": 0.0,
                    "image_url": (
                        self._image_url(
                            client,
                            product.id,
                        )
                        if product.image_128
                        else None
                    ),
                }

            row = by_sku[key]

            # -------------------------------------------------------------
            # Si el primer product.product del SKU no tenia imagen,
            # pero otro producto consolidado con el mismo SKU si tiene,
            # usar la primera imagen disponible.
            # -------------------------------------------------------------

            if (
                not row["image_url"]
                and product.image_128
            ):
                row["image_url"] = (
                    self._image_url(
                        client,
                        product.id,
                    )
                )

            row[
                "product_count"
            ] += 1

            row[
                "quantity"
            ] += quantity

            row[
                "reserved"
            ] += reserved

            row[
                "available"
            ] += (
                quantity
                - reserved
            )

        all_rows = list(
            by_sku.values()
        )

        for row in all_rows:
            row["quantity"] = round(
                row["quantity"],
                6,
            )

            row["reserved"] = round(
                row["reserved"],
                6,
            )

            row["available"] = round(
                row["available"],
                6,
            )

        all_rows.sort(
            key=lambda row: (
                row["sku"].casefold(),
                row["sku"],
            )
        )

        total = len(all_rows)

        page_rows = all_rows[
            offset:offset + limit
        ]

        next_offset = (
            offset + limit
            if offset + limit < total
            else False
        )

        has_more = bool(
            next_offset is not False
        )

        payload = {
            "ok": True,
            "api_version": (
                API_VERSION
            ),
            "snapshot": True,
            "aggregation": "sku",
            "company": {
                "id": company.id,
                "name": company.name,
            },
            "generated_at": (
                datetime.utcnow()
                .replace(
                    microsecond=0
                )
                .isoformat()
                + "Z"
            ),
            "pagination": {
                "offset": offset,
                "limit": limit,
                "count": len(
                    page_rows
                ),
                "total": total,
                "has_more": has_more,
                "next_offset": (
                    next_offset
                ),
            },
            "stock": page_rows,
        }

        self._log_request(
            client,
            200,
            result_count=len(
                page_rows
            ),
            started_at=started_at,
        )

        return self._json_response(
            payload,
            200,
        )
