import hashlib
import json

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class L7StockApiClientMovements(models.Model):
    _inherit = "l7.stock.api.client"

    webhook_enabled = fields.Boolean(
        string="Movimientos ClubClap activos",
        default=False,
        help="Habilita el POST de movimientos para este cliente.",
    )

    webhook_token_hash = fields.Char(
        string="Hash token movimientos",
        readonly=True,
        copy=False,
        index=True,
    )

    webhook_token_last4 = fields.Char(
        string="Últimos caracteres token movimientos",
        readonly=True,
        copy=False,
    )

    sold_location_id = fields.Many2one(
        "stock.location",
        string="Ubicación ventas ClubClap",
        ondelete="restrict",
    )

    # Legacy del prototipo anterior.
    webhook_confirmed_statuses = fields.Char()
    webhook_paid_statuses = fields.Char()

    @api.constrains(
        "sold_location_id",
        "company_id",
        "warehouse_id",
    )
    def _check_sold_location(self):

        for rec in self:

            location = rec.sold_location_id

            if not location:
                continue

            if location.usage != "internal":
                raise ValidationError(
                    _("La ubicación de ventas debe ser interna.")
                )

            if (
                location.company_id
                and location.company_id != rec.company_id
            ):
                raise ValidationError(
                    _("La ubicación debe pertenecer a la misma empresa.")
                )

            if rec.warehouse_id:

                stock = rec.warehouse_id.lot_stock_id

                inside = self.env[
                    "stock.location"
                ].sudo().search_count([
                    ("id", "=", location.id),
                    ("id", "child_of", stock.id),
                ])

                if inside:
                    raise ValidationError(
                        _(
                            "La ubicación de ventas no puede estar "
                            "dentro de Existencias."
                        )
                    )

    def set_webhook_bearer_token(self, token):

        self.ensure_one()

        token = (token or "").strip()

        if not token:
            raise ValidationError(
                _("Token de movimientos vacío.")
            )

        self.write({
            "webhook_token_hash": hashlib.sha256(
                token.encode("utf-8")
            ).hexdigest(),
            "webhook_token_last4": token[-4:],
        })

        return True


class L7ClubClapOrderLine(models.Model):
    _name = "l7.clubclap.order.line"
    _description = "Línea ClubClap"
    _order = "order_id, sku"

    client_id = fields.Many2one(
        "l7.stock.api.client",
        required=True,
        ondelete="cascade",
        index=True,
    )

    order_id = fields.Char(required=True, index=True)
    sku = fields.Char(required=True, index=True)

    ordered_qty = fields.Float(default=0.0)
    moved_qty = fields.Float(default=0.0, readonly=True)

    product_id = fields.Many2one(
        "product.product",
        readonly=True,
    )

    last_event_id = fields.Char(readonly=True)

    _sql_constraints = [
        (
            "l7_clubclap_order_sku_unique",
            "unique(client_id, order_id, sku)",
            "SKU duplicado para el pedido.",
        ),
    ]


class L7ClubClapMovement(models.Model):
    _name = "l7.clubclap.webhook.event"
    _description = "Movimiento ClubClap"
    _order = "received_at desc, id desc"

    client_id = fields.Many2one(
        "l7.stock.api.client",
        required=True,
        ondelete="cascade",
        index=True,
    )

    idempotency_key = fields.Char(
        string="Idempotency-Key",
        index=True,
        copy=False,
    )

    event_id = fields.Char(
        required=True,
        index=True,
    )

    event_type = fields.Char()
    order_id = fields.Char(index=True)

    channel = fields.Char()
    shopify_order_id = fields.Char()
    shopify_order_name = fields.Char()
    external_order_id = fields.Char()

    occurred_at_text = fields.Char()

    warehouse_id = fields.Many2one(
        "stock.warehouse",
        readonly=True,
    )

    dry_run = fields.Boolean(readonly=True)

    state = fields.Selection(
        [
            ("received", "Recibido"),
            ("processed", "Procesado"),
            ("partial", "Procesado con incidencias"),
            ("error", "Error"),
        ],
        default="received",
        required=True,
        index=True,
    )

    payload_json = fields.Text(readonly=True)
    response_json = fields.Text(readonly=True)

    remote_ip = fields.Char(readonly=True)

    received_at = fields.Datetime(
        default=fields.Datetime.now,
        required=True,
        readonly=True,
        index=True,
    )

    processed_at = fields.Datetime(readonly=True)
    attempt_count = fields.Integer(default=0, readonly=True)

    picking_id = fields.Many2one(
        "stock.picking",
        readonly=True,
    )

    error_message = fields.Text(readonly=True)

    # Legacy.
    order_status = fields.Char()
    payment_status = fields.Char()

    _sql_constraints = [
        (
            "l7_clubclap_event_unique",
            "unique(client_id, event_id)",
            "event_id duplicado.",
        ),
        (
            "l7_clubclap_idempotency_unique",
            "unique(client_id, idempotency_key)",
            "Idempotency-Key duplicado.",
        ),
    ]

    # ---------------------------------------------------------------------
    # STOCK
    # ---------------------------------------------------------------------

    @api.model
    def _available(self, client, product, location):

        rows = self.env[
            "stock.quant"
        ].sudo().read_group(
            [
                ("company_id", "=", client.company_id.id),
                ("location_id", "child_of", location.id),
                ("location_id.usage", "=", "internal"),
                ("product_id", "=", product.id),
            ],
            [
                "quantity:sum",
                "reserved_quantity:sum",
            ],
            [],
            lazy=False,
        )

        if not rows:
            return 0.0

        qty = float(
            rows[0].get("quantity")
            or 0.0
        )

        reserved = float(
            rows[0].get("reserved_quantity")
            or 0.0
        )

        return qty - reserved

    @api.model
    def _find_product(self, client, sku):

        products = self.env[
            "product.product"
        ].sudo().with_context(
            active_test=False
        ).search([
            ("default_code", "=", sku),
        ])

        products = products.filtered(
            lambda p:
                not p.company_id
                or p.company_id == client.company_id
        )

        if len(products) != 1:
            return self.env["product.product"]

        return products

    @api.model
    def _order_key(self, payload):

        order = payload.get("order") or {}

        return str(
            order.get("external_order_id")
            or order.get("shopify_order_id")
            or order.get("shopify_order_name")
            or ""
        ).strip()

    @api.model
    def _order_line_balance(
        self,
        client,
        order_key,
        sku,
    ):

        line = self.env[
            "l7.clubclap.order.line"
        ].sudo().search(
            [
                ("client_id", "=", client.id),
                ("order_id", "=", order_key),
                ("sku", "=", sku),
            ],
            limit=1,
        )

        balance = (
            float(line.moved_qty or 0.0)
            if line
            else 0.0
        )

        return line, balance

    @api.model
    def _apply_order_ledger(
        self,
        client,
        payload,
        executable,
    ):

        OrderLine = self.env[
            "l7.clubclap.order.line"
        ].sudo()

        order_key = self._order_key(
            payload
        )

        if not order_key:
            raise ValidationError(
                _(
                    "El pedido no tiene un identificador "
                    "válido para controlar la cancelación."
                )
            )

        for item in executable:

            sku = item["sku"]
            product = item["product"]
            quantity = float(
                item["quantity"]
            )

            line = OrderLine.search(
                [
                    ("client_id", "=", client.id),
                    ("order_id", "=", order_key),
                    ("sku", "=", sku),
                ],
                limit=1,
            )

            if payload["event"] == "sale":

                if line:

                    line.write(
                        {
                            "ordered_qty":
                                float(
                                    line.ordered_qty
                                    or 0.0
                                )
                                + quantity,
                            "moved_qty":
                                float(
                                    line.moved_qty
                                    or 0.0
                                )
                                + quantity,
                            "product_id":
                                product.id,
                            "last_event_id":
                                payload["event_id"],
                        }
                    )

                else:

                    OrderLine.create(
                        {
                            "client_id":
                                client.id,
                            "order_id":
                                order_key,
                            "sku":
                                sku,
                            "ordered_qty":
                                quantity,
                            "moved_qty":
                                quantity,
                            "product_id":
                                product.id,
                            "last_event_id":
                                payload["event_id"],
                        }
                    )

            else:

                if not line:
                    raise ValidationError(
                        _(
                            "No existe una venta previa "
                            "de este SKU para el pedido."
                        )
                    )

                balance = float(
                    line.moved_qty
                    or 0.0
                )

                if balance < quantity:

                    raise ValidationError(
                        _(
                            "La cantidad cancelada excede "
                            "la cantidad movida previamente "
                            "para este pedido."
                        )
                    )

                line.write(
                    {
                        "moved_qty":
                            balance - quantity,
                        "last_event_id":
                            payload["event_id"],
                    }
                )

        return True

    # ---------------------------------------------------------------------
    # EVALUAR
    # ---------------------------------------------------------------------

    @api.model
    def evaluate_payload(self, client, payload):

        warehouse = client.warehouse_id
        stock = warehouse.lot_stock_id
        ventas = client.sold_location_id

        if payload["event"] == "sale":
            source = stock
            destination = ventas
        else:
            source = ventas
            destination = stock

        order_key = self._order_key(
            payload
        )

        if not order_key:
            raise ValidationError(
                _(
                    "El pedido debe incluir external_order_id, "
                    "shopify_order_id o shopify_order_name."
                )
            )

        results = []
        executable = []

        virtual_source = {}
        virtual_available = {}
        virtual_order_balance = {}

        for raw in payload["lines"]:

            sku = raw["sku"]
            quantity = float(raw["quantity"])

            product = self._find_product(
                client,
                sku,
            )

            result = {
                "sku": sku,
                "quantity": quantity,
                "status": "",
                "available_after": None,
            }

            if not product:

                result["status"] = "unknown_sku"
                results.append(result)
                continue

            if payload["event"] == "cancel":

                if sku not in virtual_order_balance:

                    _, balance = (
                        self._order_line_balance(
                            client,
                            order_key,
                            sku,
                        )
                    )

                    virtual_order_balance[
                        sku
                    ] = balance

                if (
                    virtual_order_balance[
                        sku
                    ]
                    < quantity
                ):

                    if (
                        product.id
                        not in virtual_available
                    ):

                        virtual_available[
                            product.id
                        ] = self._available(
                            client,
                            product,
                            stock,
                        )

                    result["status"] = (
                        "insufficient_stock"
                    )

                    result[
                        "available_after"
                    ] = round(
                        virtual_available[
                            product.id
                        ],
                        6,
                    )

                    results.append(
                        result
                    )

                    continue

            if product.id not in virtual_source:

                virtual_source[product.id] = self._available(
                    client,
                    product,
                    source,
                )

                virtual_available[product.id] = self._available(
                    client,
                    product,
                    stock,
                )

            source_available = virtual_source[
                product.id
            ]

            if source_available < quantity:

                result["status"] = "insufficient_stock"

                result["available_after"] = round(
                    virtual_available[
                        product.id
                    ],
                    6,
                )

                results.append(result)
                continue

            virtual_source[
                product.id
            ] -= quantity

            if payload["event"] == "cancel":

                virtual_order_balance[
                    sku
                ] -= quantity

            if payload["event"] == "sale":
                virtual_available[
                    product.id
                ] -= quantity
            else:
                virtual_available[
                    product.id
                ] += quantity

            result["status"] = "ok"

            result["available_after"] = round(
                virtual_available[
                    product.id
                ],
                6,
            )

            index = len(results)

            results.append(result)

            executable.append({
                "product": product,
                "sku": sku,
                "quantity": quantity,
                "result_index": index,
            })

        return {
            "source": source,
            "destination": destination,
            "results": results,
            "executable": executable,
        }

    # ---------------------------------------------------------------------
    # DRY RUN
    # ---------------------------------------------------------------------

    @api.model
    def preview_movement(self, client, payload):

        evaluated = self.evaluate_payload(
            client,
            payload,
        )

        return {
            "ok": True,
            "dry_run": True,
            "event_id": payload["event_id"],
            "odoo_reference": "DRY-RUN",
            "lines": evaluated["results"],
        }

    # ---------------------------------------------------------------------
    # PICKING REAL
    # ---------------------------------------------------------------------

    @api.model
    def _set_done(self, move, quantity):

        if hasattr(move, "_set_quantity_done"):
            move._set_quantity_done(quantity)
            return

        if "quantity_done" in move._fields:
            move.quantity_done = quantity
            return

        raise ValidationError(
            _("No fue posible establecer quantity_done.")
        )

    @api.model
    def _validate_picking(
        self,
        picking,
        move_quantities,
    ):

        picking.action_confirm()
        picking.action_assign()

        for move, qty in move_quantities:
            self._set_done(move, qty)

        result = picking.button_validate()

        if isinstance(result, dict):

            model = result.get("res_model")
            res_id = result.get("res_id")

            if (
                model == "stock.immediate.transfer"
                and res_id
            ):
                self.env[model].browse(res_id).process()

            elif (
                model == "stock.backorder.confirmation"
                and res_id
            ):
                wizard = self.env[model].browse(res_id)

                if hasattr(
                    wizard,
                    "process_cancel_backorder",
                ):
                    wizard.process_cancel_backorder()
                else:
                    wizard.process()

        picking.invalidate_recordset()

        if picking.state != "done":
            raise ValidationError(
                _("La transferencia no quedó en estado Hecho.")
            )

    # ---------------------------------------------------------------------
    # PROCESAR REAL
    # ---------------------------------------------------------------------

    @api.model
    def process_movement(
        self,
        client,
        payload,
        idempotency_key,
        remote_ip="",
    ):

        existing = self.sudo().search([
            ("client_id", "=", client.id),
            ("idempotency_key", "=", idempotency_key),
        ], limit=1)

        if existing:

            if not existing.response_json:
                raise ValidationError(
                    _("Idempotency-Key sin respuesta guardada.")
                )

            return (
                json.loads(existing.response_json),
                existing,
                True,
            )

        same_event = self.sudo().search([
            ("client_id", "=", client.id),
            ("event_id", "=", payload["event_id"]),
        ], limit=1)

        if same_event:
            raise ValidationError(
                _(
                    "event_id ya fue recibido con otro "
                    "Idempotency-Key."
                )
            )

        order = payload.get("order") or {}

        order_key = self._order_key(
            payload
        )

        if not order_key:
            raise ValidationError(
                _(
                    "El pedido no tiene un identificador válido."
                )
            )

        event = self.sudo().create({
            "client_id": client.id,
            "idempotency_key": idempotency_key,
            "event_id": payload["event_id"],
            "event_type": payload["event"],
            "occurred_at_text": payload.get("occurred_at") or "",
            "warehouse_id": client.warehouse_id.id,
            "channel": order.get("channel") or "",
            "shopify_order_id": str(
                order.get("shopify_order_id") or ""
            ),
            "shopify_order_name": str(
                order.get("shopify_order_name") or ""
            ),
            "external_order_id": str(
                order.get("external_order_id") or ""
            ),
            "order_id": order_key,
            "payload_json": json.dumps(
                payload,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ),
            "remote_ip": (remote_ip or "")[:128],
            "attempt_count": 1,
        })

        evaluated = self.evaluate_payload(
            client,
            payload,
        )

        picking = False

        if evaluated["executable"]:

            picking = self.env[
                "stock.picking"
            ].sudo().create({
                "picking_type_id":
                    client.warehouse_id.int_type_id.id,
                "location_id":
                    evaluated["source"].id,
                "location_dest_id":
                    evaluated["destination"].id,
                "origin":
                    "CLUBCLAP:%s:%s"
                    % (
                        payload["event"],
                        payload["event_id"],
                    ),
                "company_id":
                    client.company_id.id,
            })

            move_quantities = []

            for item in evaluated["executable"]:

                product = item["product"]
                qty = item["quantity"]

                move = self.env[
                    "stock.move"
                ].sudo().create({
                    "name": product.display_name,
                    "product_id": product.id,
                    "product_uom_qty": qty,
                    "product_uom": product.uom_id.id,
                    "location_id":
                        evaluated["source"].id,
                    "location_dest_id":
                        evaluated["destination"].id,
                    "picking_id": picking.id,
                    "company_id":
                        client.company_id.id,
                })

                move_quantities.append(
                    (move, qty)
                )

            self._validate_picking(
                picking,
                move_quantities,
            )

            self._apply_order_ledger(
                client,
                payload,
                evaluated["executable"],
            )

            for item in evaluated["executable"]:

                index = item["result_index"]

                evaluated["results"][index][
                    "available_after"
                ] = round(
                    self._available(
                        client,
                        item["product"],
                        client.warehouse_id.lot_stock_id,
                    ),
                    6,
                )

        partial = any(
            line["status"] != "ok"
            for line in evaluated["results"]
        )

        response = {
            "ok": True,
            "dry_run": False,
            "event_id": payload["event_id"],
            "odoo_reference":
                picking.name if picking else None,
            "lines": evaluated["results"],
        }

        event.write({
            "state":
                "partial"
                if partial
                else "processed",
            "processed_at": fields.Datetime.now(),
            "picking_id":
                picking.id
                if picking
                else False,
            "response_json": json.dumps(
                response,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ),
        })

        return response, event, False

    @api.model
    def _cron_retry_pending(self):
        # No reintentar movimientos automáticamente
        # hasta cerrar reglas con ClubClap.
        return True
