from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class L7ClubClapWebhookEventQuote(models.Model):
    _inherit = "l7.clubclap.webhook.event"

    sale_order_id = fields.Many2one(
        "sale.order",
        string="Cotización / Pedido",
        readonly=True,
        copy=False,
        index=True,
        ondelete="set null",
    )

    @api.model
    def _clubclap_quote_context(self, client):
        Partner = self.env["res.partner"].sudo()
        Pricelist = self.env[
            "product.pricelist"
        ].sudo()

        customer = Partner.search([
            (
                "name",
                "=",
                "DISTRIBUIDORA E IMPORTADORA GRUPO LINEA 7",
            ),
            ("active", "=", True),
        ])

        if len(customer) != 1:
            raise ValidationError(
                _(
                    "ClubClap requiere exactamente un cliente "
                    "activo 'DISTRIBUIDORA E IMPORTADORA "
                    "GRUPO LINEA 7'."
                )
            )

        shipping = Partner.search([
            ("parent_id", "=", customer.id),
            ("name", "=", "Club Clap"),
            ("type", "=", "delivery"),
            ("active", "=", True),
        ])

        if len(shipping) != 1:
            raise ValidationError(
                _(
                    "ClubClap requiere exactamente una dirección "
                    "de entrega activa 'Club Clap' bajo "
                    "'DISTRIBUIDORA E IMPORTADORA GRUPO LINEA 7'."
                )
            )

        pricelist = Pricelist.search([
            ("name", "=", "PRECIO INTERTIENDA"),
            ("active", "=", True),
        ])

        pricelist = pricelist.filtered(
            lambda p:
                not p.company_id
                or p.company_id == client.company_id
        )

        if len(pricelist) != 1:
            raise ValidationError(
                _(
                    "ClubClap requiere exactamente una lista "
                    "activa 'PRECIO INTERTIENDA' válida para "
                    "la empresa del webhook."
                )
            )

        if not client.sold_location_id:
            raise ValidationError(
                _(
                    "ClubClap no tiene configurada "
                    "la ubicación VentasCC."
                )
            )

        return {
            "customer": customer,
            "shipping": shipping,
            "pricelist": pricelist,
        }

    @api.model
    def _clubclap_quote_route(self, client):
        Route = self.env["stock.route"].sudo()
        Rule = self.env["stock.rule"].sudo()

        warehouse = client.warehouse_id
        ventas = client.sold_location_id

        customers = self.env.ref(
            "stock.stock_location_customers"
        )

        route_name = (
            "ClubClap VentasCC -> Clientes"
        )

        route = Route.search([
            ("name", "=", route_name),
            ("company_id", "=", client.company_id.id),
        ], limit=1)

        if not route:
            route = Route.create({
                "name": route_name,
                "active": True,
                "company_id": client.company_id.id,
                "product_selectable": False,
                "sale_selectable": True,
                "warehouse_selectable": False,
            })

        rule = Rule.search([
            ("route_id", "=", route.id),
            ("location_src_id", "=", ventas.id),
            ("location_dest_id", "=", customers.id),
            (
                "picking_type_id",
                "=",
                warehouse.out_type_id.id,
            ),
            ("company_id", "=", client.company_id.id),
        ], limit=1)

        if not rule:
            Rule.create({
                "name":
                    "ClubClap VentasCC -> Clientes",
                "route_id": route.id,
                "action": "pull",
                "procure_method": "make_to_stock",
                "location_src_id": ventas.id,
                "location_dest_id": customers.id,
                "picking_type_id":
                    warehouse.out_type_id.id,
                "company_id": client.company_id.id,
            })

        return route

    @api.model
    def _clubclap_existing_quote(
        self,
        client,
        order_key,
    ):
        event = self.sudo().search([
            ("client_id", "=", client.id),
            ("order_id", "=", order_key),
            ("sale_order_id", "!=", False),
        ], order="id desc", limit=1)

        return (
            event.sale_order_id
            if event
            else self.env["sale.order"]
        )

    @api.model
    def _clubclap_quote_origin(
        self,
        payload,
    ):
        order = payload.get("order") or {}

        values = [
            "ClubClap",
            str(
                order.get("channel")
                or ""
            ).strip(),
            str(
                order.get("shopify_order_name")
                or ""
            ).strip(),
        ]

        return " / ".join(
            value
            for value in values
            if value
        )

    @api.model
    def _clubclap_create_quote(
        self,
        client,
        payload,
        executable,
        event,
    ):
        context = self._clubclap_quote_context(
            client
        )

        route = self._clubclap_quote_route(
            client
        )

        order_key = self._order_key(payload)

        sale_order = self._clubclap_existing_quote(
            client,
            order_key,
        )

        SaleOrder = self.env[
            "sale.order"
        ].sudo().with_company(
            client.company_id
        )

        SaleLine = self.env[
            "sale.order.line"
        ].sudo().with_company(
            client.company_id
        )

        if sale_order:
            if sale_order.state not in (
                "draft",
                "sent",
            ):
                raise ValidationError(
                    _(
                        "El pedido externo %s ya tiene "
                        "una cotización/pedido %s en estado %s; "
                        "no se agregarán nuevas líneas "
                        "automáticamente."
                    )
                    % (
                        order_key,
                        sale_order.name,
                        sale_order.state,
                    )
                )
        else:
            sale_order = SaleOrder.create({
                "company_id":
                    client.company_id.id,
                "partner_id":
                    context["customer"].id,
                "partner_invoice_id":
                    context["customer"].id,
                "partner_shipping_id":
                    context["shipping"].id,
                "pricelist_id":
                    context["pricelist"].id,
                "warehouse_id":
                    client.warehouse_id.id,
                "client_order_ref":
                    order_key,
                "origin":
                    self._clubclap_quote_origin(
                        payload
                    ),
            })

        for item in executable:
            product = item["product"]
            quantity = float(
                item["quantity"]
            )

            line = sale_order.order_line.filtered(
                lambda l:
                    not l.display_type
                    and l.product_id == product
                    and l.route_id == route
            )[:1]

            if line:
                line.write({
                    "product_uom_qty":
                        float(
                            line.product_uom_qty
                            or 0.0
                        )
                        + quantity,
                })
            else:
                SaleLine.create({
                    "order_id": sale_order.id,
                    "product_id": product.id,
                    "product_uom_qty": quantity,
                    "route_id": route.id,
                })

        event.write({
            "sale_order_id": sale_order.id,
        })

        return sale_order

    @api.model
    def _clubclap_cancel_quote(
        self,
        client,
        payload,
        executable,
        event,
    ):
        order_key = self._order_key(payload)

        sale_order = self._clubclap_existing_quote(
            client,
            order_key,
        )

        # Ventas anteriores a v1.6 no tienen cotización
        # enlazada. Conservamos compatibilidad con ellas.
        if not sale_order:
            return self.env["sale.order"]

        if sale_order.state not in (
            "draft",
            "sent",
        ):
            raise ValidationError(
                _(
                    "No se puede devolver automáticamente "
                    "el pedido externo %s porque %s ya está "
                    "en estado %s. Debe revisarse el flujo "
                    "de devolución/cancelación del pedido."
                )
                % (
                    order_key,
                    sale_order.name,
                    sale_order.state,
                )
            )

        for item in executable:
            product = item["product"]
            quantity = float(
                item["quantity"]
            )

            lines = sale_order.order_line.filtered(
                lambda l:
                    not l.display_type
                    and l.product_id == product
                    and l.product_uom_qty > 0
            )

            remaining = quantity

            for line in lines:
                if remaining <= 0:
                    break

                current = float(
                    line.product_uom_qty
                    or 0.0
                )

                take = min(
                    current,
                    remaining,
                )

                new_qty = current - take
                remaining -= take

                if new_qty <= 0:
                    line.unlink()
                else:
                    line.write({
                        "product_uom_qty":
                            new_qty,
                    })

            if remaining > 0.000001:
                raise ValidationError(
                    _(
                        "La cotización %s no contiene "
                        "cantidad suficiente del SKU %s "
                        "para aplicar la cancelación."
                    )
                    % (
                        sale_order.name,
                        item["sku"],
                    )
                )

        product_lines = (
            sale_order.order_line.filtered(
                lambda l:
                    not l.display_type
                    and l.product_id
                    and l.product_uom_qty > 0
            )
        )

        if not product_lines:
            sale_order.action_cancel()

        event.write({
            "sale_order_id": sale_order.id,
        })

        return sale_order

    @api.model
    def _clubclap_apply_quote(
        self,
        client,
        payload,
        executable,
        event,
    ):
        if not executable:
            return self.env["sale.order"]

        if payload["event"] == "sale":
            return self._clubclap_create_quote(
                client,
                payload,
                executable,
                event,
            )

        if payload["event"] == "cancel":
            return self._clubclap_cancel_quote(
                client,
                payload,
                executable,
                event,
            )

        return self.env["sale.order"]
