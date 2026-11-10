import hashlib
import json

from odoo import http
from odoo.exceptions import ValidationError
from odoo.http import request


class L7ClubClapMovementController(http.Controller):

    def _response(self, payload, status=200):

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
            ],
            status=status,
        )

    def _error(
        self,
        status,
        error,
        field=None,
        message=None,
    ):

        data = {
            "ok": False,
            "error": error,
        }

        if field:
            data["field"] = field

        if message:
            data["message"] = message

        return self._response(
            data,
            status,
        )

    def _bearer(self):

        value = (
            request.httprequest.headers.get(
                "Authorization",
                "",
            )
            or ""
        ).strip()

        parts = value.split(None, 1)

        if (
            len(parts) != 2
            or parts[0].casefold() != "bearer"
        ):
            return False

        return parts[1].strip() or False

    def _authenticate(self):

        token = self._bearer()

        if not token:
            return False

        token_hash = hashlib.sha256(
            token.encode("utf-8")
        ).hexdigest()

        return request.env[
            "l7.stock.api.client"
        ].sudo().search([
            ("active", "=", True),
            (
                "webhook_token_hash",
                "=",
                token_hash,
            ),
        ], limit=1)

    def _dry_run(self):

        raw = (
            request.httprequest.headers.get(
                "X-L7-Dry-Run",
                "",
            )
            or ""
        ).strip().casefold()

        if not raw:
            return False, False

        if raw in ("true", "1", "yes"):
            return True, False

        if raw in ("false", "0", "no"):
            return False, False

        return False, True

    def _remote_ip(self):

        try:
            route = request.httprequest.access_route

            if route:
                return route[0]
        except Exception:
            pass

        return (
            request.httprequest.remote_addr
            or ""
        )

    def _validate_payload(self, payload):

        if not isinstance(payload, dict):
            return "body", "Debe ser un objeto JSON."

        event = str(
            payload.get("event") or ""
        ).strip().casefold()

        if event not in ("sale", "cancel"):
            return "event", "Debe ser sale o cancel."

        payload["event"] = event

        event_id = str(
            payload.get("event_id") or ""
        ).strip()

        if not event_id:
            return "event_id", "Campo requerido."

        payload["event_id"] = event_id

        if not payload.get("occurred_at"):
            return "occurred_at", "Campo requerido."

        try:
            warehouse_id = int(
                payload.get("warehouse_id")
            )
        except (TypeError, ValueError):
            return "warehouse_id", "Debe ser entero."

        payload["warehouse_id"] = warehouse_id

        order = payload.get("order")

        if not isinstance(order, dict):
            return "order", "Debe ser objeto."

        order_key = str(
            order.get("external_order_id")
            or order.get("shopify_order_id")
            or order.get("shopify_order_name")
            or ""
        ).strip()

        if not order_key:
            return (
                "order",
                (
                    "Debe incluir external_order_id, "
                    "shopify_order_id o shopify_order_name."
                ),
            )

        lines = payload.get("lines")

        if not isinstance(lines, list) or not lines:
            return (
                "lines",
                "Debe contener al menos una línea.",
            )

        normalized = []

        for index, line in enumerate(lines):

            if not isinstance(line, dict):
                return (
                    "lines[%s]" % index,
                    "Debe ser objeto.",
                )

            sku = str(
                line.get("sku") or ""
            ).strip()

            if not sku:
                return (
                    "lines[%s].sku" % index,
                    "Campo requerido.",
                )

            try:
                quantity = float(
                    line.get("quantity")
                )
            except (TypeError, ValueError):
                return (
                    "lines[%s].quantity" % index,
                    "Debe ser numérico.",
                )

            if quantity <= 0:
                return (
                    "lines[%s].quantity" % index,
                    "Debe ser mayor a cero.",
                )

            normalized.append({
                "sku": sku,
                "quantity": quantity,
                "name": str(
                    line.get("name") or ""
                ),
            })

        payload["lines"] = normalized

        return False

    @http.route(
        "/l7-stock-api/v1/stock/movements",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
        sitemap=False,
    )
    def stock_movements(self, **kwargs):

        client = self._authenticate()

        if not client:
            return self._error(
                401,
                "unauthorized",
            )

        if not client.webhook_enabled:
            return self._error(
                503,
                "integration_disabled",
            )

        if (
            not client.warehouse_id
            or not client.sold_location_id
        ):
            return self._error(
                503,
                "integration_not_configured",
            )

        key = (
            request.httprequest.headers.get(
                "Idempotency-Key",
                "",
            )
            or ""
        ).strip()

        if not key:
            return self._error(
                422,
                "validation_error",
                "Idempotency-Key",
                "Header requerido.",
            )

        if len(key) > 255:
            return self._error(
                422,
                "validation_error",
                "Idempotency-Key",
                "Máximo 255 caracteres.",
            )

        dry_run, invalid_dry = self._dry_run()

        if invalid_dry:
            return self._error(
                422,
                "validation_error",
                "X-L7-Dry-Run",
                "Use true o false.",
            )

        try:

            raw = request.httprequest.get_data(
                cache=False,
                as_text=True,
            )

            payload = json.loads(
                raw or ""
            )

        except Exception:

            return self._error(
                422,
                "validation_error",
                "body",
                "JSON mal formado.",
            )

        validation = self._validate_payload(
            payload
        )

        if validation:

            field, message = validation

            return self._error(
                422,
                "validation_error",
                field,
                message,
            )

        if (
            payload["warehouse_id"]
            != client.warehouse_id.id
        ):
            return self._error(
                403,
                "warehouse_forbidden",
                "warehouse_id",
                "Token sin permiso para ese almacén.",
            )

        Event = request.env[
            "l7.clubclap.webhook.event"
        ].sudo()

        if dry_run:

            response = Event.preview_movement(
                client,
                payload,
            )

            return self._response(
                response,
                200,
            )

        try:

            response, event, duplicate = (
                Event.process_movement(
                    client,
                    payload,
                    key,
                    remote_ip=self._remote_ip(),
                )
            )

        except ValidationError as exc:

            request.env.cr.rollback()

            return self._error(
                422,
                "validation_error",
                message=str(exc),
            )

        return self._response(
            response,
            200,
        )
