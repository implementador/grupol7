import base64
import hashlib
import hmac

from odoo import http
from odoo.http import request


class L7StockApiImageController(http.Controller):

    # -------------------------------------------------------------------------
    # RESPONSE
    # -------------------------------------------------------------------------

    def _text_response(self, text, status):
        return request.make_response(
            text,
            headers=[
                (
                    "Content-Type",
                    "text/plain; charset=utf-8",
                ),
                (
                    "Cache-Control",
                    "no-store",
                ),
                (
                    "X-Content-Type-Options",
                    "nosniff",
                ),
            ],
            status=status,
        )

    # -------------------------------------------------------------------------
    # SIGNATURE
    #
    # El token original NO se usa ni se expone.
    #
    # La llave HMAC es el hash SHA-256 almacenado del token.
    #
    # Si el cliente se desactiva o se rota su token:
    # - cambia token_hash
    # - las firmas anteriores dejan de funcionar
    # -------------------------------------------------------------------------

    def _expected_signature(
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

    # -------------------------------------------------------------------------
    # IMAGE TYPE
    # -------------------------------------------------------------------------

    def _detect_mimetype(self, content):
        if content.startswith(
            b"\xff\xd8\xff"
        ):
            return "image/jpeg"

        if content.startswith(
            b"\x89PNG\r\n\x1a\n"
        ):
            return "image/png"

        if content.startswith(
            b"GIF87a"
        ) or content.startswith(
            b"GIF89a"
        ):
            return "image/gif"

        if (
            len(content) >= 12
            and content[0:4] == b"RIFF"
            and content[8:12] == b"WEBP"
        ):
            return "image/webp"

        return "application/octet-stream"

    # -------------------------------------------------------------------------
    # IMAGE
    # -------------------------------------------------------------------------

    @http.route(
        "/l7-stock-api/v1/product/<int:product_id>/image",
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
        sitemap=False,
    )
    def product_image(
        self,
        product_id,
        **kwargs,
    ):
        args = request.httprequest.args

        raw_client_id = (
            args.get("client")
            or ""
        ).strip()

        signature = (
            args.get("sig")
            or ""
        ).strip().lower()

        try:
            client_id = int(
                raw_client_id
            )
        except (TypeError, ValueError):
            return self._text_response(
                "Forbidden",
                403,
            )

        if client_id <= 0:
            return self._text_response(
                "Forbidden",
                403,
            )

        if not signature:
            return self._text_response(
                "Forbidden",
                403,
            )

        client = (
            request.env["l7.stock.api.client"]
            .sudo()
            .browse(client_id)
            .exists()
        )

        if not client or not client.active:
            return self._text_response(
                "Forbidden",
                403,
            )

        if not client.token_hash:
            return self._text_response(
                "Forbidden",
                403,
            )

        expected = self._expected_signature(
            client,
            product_id,
        )

        if not hmac.compare_digest(
            signature,
            expected,
        ):
            return self._text_response(
                "Forbidden",
                403,
            )

        product = (
            request.env["product.product"]
            .sudo()
            .with_context(active_test=False)
            .browse(product_id)
            .exists()
        )

        if not product:
            return self._text_response(
                "Not Found",
                404,
            )

        # ---------------------------------------------------------------------
        # Seguridad adicional de empresa.
        #
        # Producto permitido:
        # - global
        # - o expresamente ligado a la empresa del cliente
        # ---------------------------------------------------------------------

        if (
            product.company_id
            and product.company_id.id
            != client.company_id.id
        ):
            return self._text_response(
                "Forbidden",
                403,
            )

        # ---------------------------------------------------------------------
        # La imagen solo se entrega si el producto forma parte del universo
        # de inventario interno de la empresa autorizada.
        #
        # Esto evita que una URL firmada se use para productos fuera del
        # inventario del cliente.
        # ---------------------------------------------------------------------

        quant_exists = (
            request.env["stock.quant"]
            .sudo()
            .search_count(
                [
                    (
                        "company_id",
                        "=",
                        client.company_id.id,
                    ),
                    (
                        "location_id.usage",
                        "=",
                        "internal",
                    ),
                    (
                        "product_id",
                        "=",
                        product.id,
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
            )
        )

        if not quant_exists:
            return self._text_response(
                "Not Found",
                404,
            )

        image_b64 = product.image_512

        if not image_b64:
            return self._text_response(
                "Not Found",
                404,
            )

        try:
            if isinstance(
                image_b64,
                str,
            ):
                image_b64 = image_b64.encode(
                    "ascii"
                )

            content = base64.b64decode(
                image_b64
            )

        except Exception:
            return self._text_response(
                "Invalid Image",
                500,
            )

        if not content:
            return self._text_response(
                "Not Found",
                404,
            )

        mimetype = self._detect_mimetype(
            content
        )

        return request.make_response(
            content,
            headers=[
                (
                    "Content-Type",
                    mimetype,
                ),
                (
                    "Content-Length",
                    str(len(content)),
                ),
                (
                    "Content-Disposition",
                    (
                        'inline; filename="product-%s-image"'
                        % product.id
                    ),
                ),
                (
                    "Cache-Control",
                    "private, max-age=3600",
                ),
                (
                    "X-Content-Type-Options",
                    "nosniff",
                ),
            ],
            status=200,
        )
