import base64
import html
import os
import re
import tempfile
from collections import defaultdict

import xlsxwriter

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class L7InsumosReport(models.Model):
    _name = "l7.insumos.report"
    _description = "Reporte de Gasto de Insumos"
    _order = "create_date desc, id desc"

    name = fields.Char(
        string="Reporte",
        required=True,
        readonly=True,
        default=lambda self: self._default_name(),
    )

    date_from = fields.Date(
        string="Desde",
        required=True,
        readonly=True,
    )

    date_to = fields.Date(
        string="Hasta",
        required=True,
        readonly=True,
    )

    requested_by = fields.Many2one(
        "res.users",
        string="Solicitado por",
        required=True,
        default=lambda self: self.env.user,
        readonly=True,
    )

    requested_at = fields.Datetime(
        string="Solicitado",
        required=True,
        default=fields.Datetime.now,
        readonly=True,
    )

    movement_count = fields.Integer(
        string="Movimientos",
        readonly=True,
    )

    picking_count = fields.Integer(
        string="Transferencias",
        readonly=True,
    )

    total_amount = fields.Float(
        string="Gasto total",
        readonly=True,
        digits=(16, 2),
    )

    safety_percent = fields.Float(
        string="Colchon de seguridad (%)",
        readonly=True,
        default=10.0,
        digits=(16, 2),
    )

    attachment_id = fields.Many2one(
        "ir.attachment",
        string="Archivo XLSX",
        readonly=True,
        ondelete="set null",
    )

    state = fields.Selection(
        [
            ("draft", "Pendiente"),
            ("done", "Listo"),
            ("error", "Error"),
        ],
        string="Estado",
        default="draft",
        required=True,
        readonly=True,
    )

    error_message = fields.Text(
        string="Error",
        readonly=True,
    )

    COMPANY_ID = 1
    INSUMOS_LOCATION_ID = 822
    CONSUMO_LOCATION_ID = 829

    # ==================================================================
    # BASICOS
    # ==================================================================

    @api.model
    def _default_name(self):
        now = fields.Datetime.context_timestamp(
            self,
            fields.Datetime.now(),
        )

        return "Gasto de Insumos %s" % now.strftime(
            "%Y-%m-%d %H:%M:%S"
        )

    def action_download(self):
        self.ensure_one()

        if self.state != "done" or not self.attachment_id:
            raise UserError(
                _("El reporte aun no esta listo.")
            )

        return {
            "type": "ir.actions.act_url",
            "url": "/web/content/%s?download=true"
            % self.attachment_id.id,
            "target": "self",
        }

    def _previous_period(self):
        """
        Periodo comparable para planeacion.

        El historico completo puede abarcar varios anos, pero la
        planeacion compara exclusivamente el ano actual hasta la
        fecha de corte contra el mismo periodo del ano anterior.
        """
        cutoff = fields.Date.to_date(
            self.date_to
        )

        current_from = cutoff.replace(
            month=1,
            day=1,
        )

        current_to = cutoff

        previous_from = current_from.replace(
            year=current_from.year - 1
        )

        try:
            previous_to = current_to.replace(
                year=current_to.year - 1
            )
        except ValueError:
            previous_to = current_to.replace(
                year=current_to.year - 1,
                day=28,
            )

        return (
            current_from,
            current_to,
            previous_from,
            previous_to,
        )

    def _to_datetime_range(
        self,
        date_from,
        date_to,
    ):
        start_dt = fields.Datetime.to_datetime(
            "%s 00:00:00" % date_from
        )

        end_dt = fields.Datetime.to_datetime(
            "%s 23:59:59" % date_to
        )

        return start_dt, end_dt

    def _clean_html(self, value):
        if not value:
            return ""

        text = str(value)

        text = re.sub(
            r"<br\s*/?>",
            " ",
            text,
            flags=re.I,
        )

        text = re.sub(
            r"</p>",
            " ",
            text,
            flags=re.I,
        )

        text = re.sub(
            r"<[^>]+>",
            "",
            text,
        )

        text = html.unescape(text)

        text = re.sub(
            r"\s+",
            " ",
            text,
        )

        return text.strip()

    # ==================================================================
    # AREA
    # ==================================================================

    def _normalize_area(
        self,
        partner_name,
        note,
    ):
        partner = (
            partner_name or ""
        ).upper()

        note = (
            note or ""
        ).upper()

        text = "%s %s" % (
            partner,
            note,
        )

        if "TIENDA INSURGENTES" in text:
            return "TIENDA INSURGENTES"

        if "REFACCIONES" in text:
            return "CEDIS REFACCIONES"

        if "LATERAL MEDIA" in text:
            return "CEDIS LATERAL MEDIA"

        if "CEDIS EMPAQUE" in text:
            return "CEDIS EMPAQUE"

        if "COPPEL" in text:
            if "C2" in text or "CALLE 2" in text:
                return "COPPEL C2"
            return "COPPEL"

        if (
            "B-TOYS" in text
            or "B TOYS" in text
            or "BTOYS" in text
        ):
            if "CALLE 11" in text or "C11" in text:
                return "B-TOYS CALLE 11"

            if "CALLE 2" in text or "C2" in text:
                return "B-TOYS CALLE 2"

            return "B-TOYS"

        if "MONK" in text:
            if "CALLE 2" in text or "C2" in text:
                return "MONK CALLE 2"
            return "MONK"

        if "MEM" in text:
            if "ADMIN" in text:
                return "MEM ADMINISTRACION"

            if "CALLE 2" in text or "C2" in text:
                return "MEM CALLE 2"

            return "MEM"

        if "CEDIS ANDEN" in text:
            return "CEDIS ANDEN"

        if "CEDIS TLAHUAC" in text:
            return "CEDIS TLAHUAC"

        if partner_name:
            return partner_name.strip()

        return "SIN AREA IDENTIFICADA"

    # ==================================================================
    # CONVERSIONES UOM / MONEDA
    # ==================================================================

    def _qty_to_base_uom(
        self,
        qty,
        source_uom,
        product,
    ):
        qty = qty or 0.0

        if not source_uom:
            return qty

        try:
            return source_uom._compute_quantity(
                qty,
                product.uom_id,
            )
        except Exception:
            return qty

    def _purchase_line_values_mxn(
        self,
        line,
    ):
        """
        Retorna:
        - cantidad pedida en UOM base del producto
        - importe neto sin impuestos en moneda de empresa
        - costo promedio por UOM base
        """

        product = line.product_id
        order = line.order_id
        company = order.company_id

        ordered_base = self._qty_to_base_uom(
            line.product_qty,
            line.product_uom,
            product,
        )

        original_total = (
            (line.product_qty or 0.0)
            * (line.price_unit or 0.0)
        )

        discount = 0.0

        if "discount" in line._fields:
            discount = (
                line.discount
                or 0.0
            )

        if discount:
            original_total *= (
                1.0
                - discount / 100.0
            )

        conversion_date = (
            fields.Date.to_date(
                order.date_order
            )
            if order.date_order
            else fields.Date.context_today(self)
        )

        currency = order.currency_id

        if (
            currency
            and company.currency_id
            and currency != company.currency_id
        ):
            total_company = currency._convert(
                original_total,
                company.currency_id,
                company,
                conversion_date,
            )
        else:
            total_company = original_total

        unit_company = (
            total_company / ordered_base
            if ordered_base
            else 0.0
        )

        return (
            ordered_base,
            total_company,
            unit_company,
        )

    # ==================================================================
    # COSTO HISTORICO DE SALIDA
    # ==================================================================

    def _get_historical_cost(
        self,
        move,
    ):
        SVL = self.env[
            "stock.valuation.layer"
        ].sudo()

        layers = SVL.search([
            (
                "stock_move_id",
                "=",
                move.id,
            ),
        ])

        qty = sum(
            abs(layer.quantity or 0.0)
            for layer in layers
        )

        value = sum(
            abs(layer.value or 0.0)
            for layer in layers
        )

        if qty > 0 and value > 0:
            return (
                value / qty,
                "VALORACION DEL MOVIMIENTO",
            )

        previous_layer = SVL.search([
            (
                "product_id",
                "=",
                move.product_id.id,
            ),
            (
                "company_id",
                "=",
                move.company_id.id,
            ),
            (
                "create_date",
                "<=",
                move.date,
            ),
            (
                "quantity",
                "!=",
                0,
            ),
        ],
            order="create_date desc, id desc",
            limit=1,
        )

        if previous_layer:

            previous_qty = abs(
                previous_layer.quantity
                or 0.0
            )

            previous_value = abs(
                previous_layer.value
                or 0.0
            )

            if (
                previous_qty > 0
                and previous_value > 0
            ):
                return (
                    previous_value
                    / previous_qty,
                    "ULTIMA VALORACION HISTORICA",
                )

            unit_cost = (
                getattr(
                    previous_layer,
                    "unit_cost",
                    0.0,
                )
                or 0.0
            )

            if unit_cost > 0:
                return (
                    unit_cost,
                    "ULTIMA VALORACION HISTORICA",
                )

        product = (
            move.product_id
            .with_company(
                move.company_id
            )
        )

        return (
            product.standard_price
            or 0.0,
            "COSTO ACTUAL ODOO",
        )

    # ==================================================================
    # SALIDAS DE INSUMOS
    # ==================================================================

    def _get_outgoing_rows(
        self,
        date_from,
        date_to,
    ):
        Move = self.env[
            "stock.move"
        ].sudo()

        start_dt, end_dt = (
            self._to_datetime_range(
                date_from,
                date_to,
            )
        )

        moves = Move.search([
            (
                "company_id",
                "=",
                self.COMPANY_ID,
            ),
            (
                "state",
                "=",
                "done",
            ),
            (
                "location_id",
                "=",
                self.INSUMOS_LOCATION_ID,
            ),
            (
                "location_dest_id",
                "=",
                self.CONSUMO_LOCATION_ID,
            ),
            (
                "date",
                ">=",
                start_dt,
            ),
            (
                "date",
                "<=",
                end_dt,
            ),
        ],
            order="date asc, id asc",
        )

        rows = []

        for move in moves:

            qty = self._qty_to_base_uom(
                move.quantity_done,
                move.product_uom,
                move.product_id,
            )

            if qty <= 0:
                continue

            picking = move.picking_id

            contact = (
                picking.partner_id.display_name
                if (
                    picking
                    and picking.partner_id
                )
                else ""
            )

            note = self._clean_html(
                picking.note
                if picking
                else ""
            )

            area = self._normalize_area(
                contact,
                note,
            )

            unit_cost, cost_source = (
                self._get_historical_cost(
                    move
                )
            )

            rows.append({
                "date": move.date,
                "month": (
                    move.date.strftime(
                        "%Y-%m"
                    )
                ),
                "month_number": move.date.month,
                "picking": (
                    picking.name
                    if picking
                    else ""
                ),
                "area": area,
                "contact": contact,
                "note": note,
                "responsible": (
                    picking.user_id.display_name
                    if (
                        picking
                        and picking.user_id
                    )
                    else ""
                ),
                "move_id": move.id,
                "product_id": (
                    move.product_id.id
                ),
                "sku": (
                    move.product_id.default_code
                    or ""
                ),
                "product": (
                    move.product_id.display_name
                ),
                "qty": qty,
                "uom": (
                    move.product_id.uom_id.name
                ),
                "unit_cost": unit_cost,
                "cost_source": cost_source,
                "amount": (
                    qty * unit_cost
                ),
            })

        return rows

    # ==================================================================
    # ORDENES DE COMPRA - POR FECHA REAL DE OC
    # ==================================================================

    def _get_order_rows(
        self,
        date_from,
        date_to,
    ):
        PurchaseLine = self.env[
            "purchase.order.line"
        ].sudo()

        start_dt, end_dt = (
            self._to_datetime_range(
                date_from,
                date_to,
            )
        )

        lines = PurchaseLine.search([
            (
                "company_id",
                "=",
                self.COMPANY_ID,
            ),
            (
                "order_id.state",
                "in",
                [
                    "purchase",
                    "done",
                ],
            ),
            (
                "order_id.date_order",
                ">=",
                start_dt,
            ),
            (
                "order_id.date_order",
                "<=",
                end_dt,
            ),
            (
                "product_id",
                "!=",
                False,
            ),
            (
                "move_ids.location_dest_id",
                "=",
                self.INSUMOS_LOCATION_ID,
            ),
        ],
            order="order_id asc, id asc",
        )

        rows = []

        for line in lines:

            order = line.order_id
            product = line.product_id

            (
                ordered_qty,
                ordered_value,
                unit_cost_company,
            ) = self._purchase_line_values_mxn(
                line
            )

            received_lifetime = (
                self._qty_to_base_uom(
                    line.qty_received,
                    line.product_uom,
                    product,
                )
            )

            pending_qty = max(
                0.0,
                ordered_qty
                - received_lifetime,
            )

            rows.append({
                "date": order.date_order,
                "month": (
                    order.date_order.strftime(
                        "%Y-%m"
                    )
                ),
                "month_number": (
                    order.date_order.month
                ),
                "po_line_id": line.id,
                "po_id": order.id,
                "po": order.name,
                "supplier": (
                    order.partner_id.display_name
                ),
                "product_id": product.id,
                "sku": (
                    product.default_code
                    or ""
                ),
                "product": product.display_name,
                "ordered_qty": ordered_qty,
                "received_lifetime": (
                    received_lifetime
                ),
                "pending_qty": pending_qty,
                "uom": product.uom_id.name,
                "price_original": (
                    line.price_unit
                    or 0.0
                ),
                "currency": (
                    order.currency_id.name
                    or ""
                ),
                "unit_cost_company": (
                    unit_cost_company
                ),
                "ordered_value_company": (
                    ordered_value
                ),
            })

        return rows

    # ==================================================================
    # RECEPCIONES REALES - POR FECHA DE RECEPCION
    # ==================================================================

    def _get_receipt_rows(
        self,
        date_from,
        date_to,
    ):
        Move = self.env[
            "stock.move"
        ].sudo()

        start_dt, end_dt = (
            self._to_datetime_range(
                date_from,
                date_to,
            )
        )

        moves = Move.search([
            (
                "company_id",
                "=",
                self.COMPANY_ID,
            ),
            (
                "state",
                "=",
                "done",
            ),
            (
                "location_dest_id",
                "=",
                self.INSUMOS_LOCATION_ID,
            ),
            (
                "purchase_line_id",
                "!=",
                False,
            ),
            (
                "date",
                ">=",
                start_dt,
            ),
            (
                "date",
                "<=",
                end_dt,
            ),
        ],
            order="date asc, id asc",
        )

        rows = []

        for move in moves:

            line = move.purchase_line_id
            order = line.order_id
            product = move.product_id

            qty = self._qty_to_base_uom(
                move.quantity_done,
                move.product_uom,
                product,
            )

            if qty <= 0:
                continue

            (
                ordered_qty,
                ordered_value,
                unit_cost_company,
            ) = self._purchase_line_values_mxn(
                line
            )

            rows.append({
                "date": move.date,
                "month": (
                    move.date.strftime(
                        "%Y-%m"
                    )
                ),
                "month_number": move.date.month,
                "move_id": move.id,
                "picking": (
                    move.picking_id.name
                    if move.picking_id
                    else ""
                ),
                "po_line_id": line.id,
                "po": order.name,
                "supplier": (
                    order.partner_id.display_name
                ),
                "product_id": product.id,
                "sku": (
                    product.default_code
                    or ""
                ),
                "product": product.display_name,
                "received_qty": qty,
                "uom": product.uom_id.name,
                "unit_cost_company": (
                    unit_cost_company
                ),
                "received_value_company": (
                    qty
                    * unit_cost_company
                ),
            })

        return rows

    # ==================================================================
    # STOCK DISPONIBLE ACTUAL
    # ==================================================================

    def _get_current_stock(
        self,
        product_ids,
    ):
        Quant = self.env[
            "stock.quant"
        ].sudo()

        result = defaultdict(
            lambda: {
                "quantity": 0.0,
                "reserved": 0.0,
                "available": 0.0,
            }
        )

        if not product_ids:
            return result

        quants = Quant.search([
            (
                "company_id",
                "=",
                self.COMPANY_ID,
            ),
            (
                "location_id",
                "=",
                self.INSUMOS_LOCATION_ID,
            ),
            (
                "product_id",
                "in",
                list(product_ids),
            ),
        ])

        for quant in quants:

            quantity = (
                quant.quantity
                or 0.0
            )

            reserved = (
                quant.reserved_quantity
                or 0.0
            )

            result[
                quant.product_id.id
            ]["quantity"] += quantity

            result[
                quant.product_id.id
            ]["reserved"] += reserved

            result[
                quant.product_id.id
            ]["available"] += (
                quantity
                - reserved
            )

        return result

    # ==================================================================
    # PENDIENTE POR RECIBIR ACTUAL
    # ==================================================================

    def _get_open_purchase_pending(
        self,
        product_ids,
    ):
        PurchaseLine = self.env[
            "purchase.order.line"
        ].sudo()

        result = defaultdict(float)

        if not product_ids:
            return result

        lines = PurchaseLine.search([
            (
                "company_id",
                "=",
                self.COMPANY_ID,
            ),
            (
                "order_id.state",
                "=",
                "purchase",
            ),
            (
                "product_id",
                "in",
                list(product_ids),
            ),
            (
                "move_ids.location_dest_id",
                "=",
                self.INSUMOS_LOCATION_ID,
            ),
        ])

        for line in lines:

            ordered = self._qty_to_base_uom(
                line.product_qty,
                line.product_uom,
                line.product_id,
            )

            received = self._qty_to_base_uom(
                line.qty_received,
                line.product_uom,
                line.product_id,
            )

            pending = max(
                0.0,
                ordered - received,
            )

            result[
                line.product_id.id
            ] += pending

        return result

    # ==================================================================
    # AGREGAR MES + PRODUCTO
    # ==================================================================

    def _aggregate_month_product(
        self,
        order_rows,
        receipt_rows,
        outgoing_rows,
    ):
        result = defaultdict(
            lambda: {
                "ordered_qty": 0.0,
                "ordered_value": 0.0,
                "received_qty": 0.0,
                "received_value": 0.0,
                "outgoing_qty": 0.0,
                "outgoing_value": 0.0,
                "uom": "",
            }
        )

        for row in order_rows:

            key = (
                row["month_number"],
                row["product_id"],
                row["sku"],
                row["product"],
            )

            values = result[key]

            values["ordered_qty"] += (
                row["ordered_qty"]
            )

            values["ordered_value"] += (
                row["ordered_value_company"]
            )

            values["uom"] = row["uom"]

        for row in receipt_rows:

            key = (
                row["month_number"],
                row["product_id"],
                row["sku"],
                row["product"],
            )

            values = result[key]

            values["received_qty"] += (
                row["received_qty"]
            )

            values["received_value"] += (
                row["received_value_company"]
            )

            values["uom"] = row["uom"]

        for row in outgoing_rows:

            key = (
                row["month_number"],
                row["product_id"],
                row["sku"],
                row["product"],
            )

            values = result[key]

            values["outgoing_qty"] += (
                row["qty"]
            )

            values["outgoing_value"] += (
                row["amount"]
            )

            values["uom"] = row["uom"]

        return result

    # ==================================================================
    # GENERAR
    # ==================================================================

    def _get_full_history_period(self):
        """
        Obtiene automaticamente todo el periodo confiable de
        CEDIS INSUMOS.

        Se limita estrictamente a movimientos DONE de los tipos
        de operacion del almacen CEDIS INSUMOS.

        731 = Recepciones
        732 = Ordenes de entrega
        735 = Traslados internos
        740 = Ordenes de PdV
        736 = Devoluciones
        """
        Move = self.env["stock.move"].sudo()

        moves = Move.search(
            [
                ("company_id", "=", self.COMPANY_ID),
                ("state", "=", "done"),
                ("picking_type_id", "in", [731, 732, 735, 740, 736]),
            ],
            order="date asc, id asc",
        )

        if not moves:
            raise UserError(
                _(
                    "No existen movimientos terminados en el "
                    "almacen CEDIS INSUMOS."
                )
            )

        first_date = fields.Date.to_date(moves[0].date)
        today = fields.Date.context_today(self)

        return first_date, today

    def generate_report(self):
        self.ensure_one()

        # ==============================================================
        # HISTORICO COMPLETO
        # ==============================================================

        history_from, history_to = (
            self._get_full_history_period()
        )

        self.write({
            "date_from": history_from,
            "date_to": history_to,
        })

        try:

            (
                current_from,
                current_to,
                previous_from,
                previous_to,
            ) = self._previous_period()

            # ==========================================================
            # HISTORICO COMPLETO CEDIS INSUMOS
            # ==========================================================

            history_from = fields.Date.to_date(
                self.date_from
            )

            history_to = fields.Date.to_date(
                self.date_to
            )

            history_orders = self._get_order_rows(
                history_from,
                history_to,
            )

            history_receipts = self._get_receipt_rows(
                history_from,
                history_to,
            )

            history_out = self._get_outgoing_rows(
                history_from,
                history_to,
            )

            # ==========================================================
            # PERIODO DE PLANEACION ACTUAL
            # ==========================================================

            current_orders = self._get_order_rows(
                current_from,
                current_to,
            )

            current_receipts = (
                self._get_receipt_rows(
                    current_from,
                    current_to,
                )
            )

            current_out = self._get_outgoing_rows(
                current_from,
                current_to,
            )

            # ==========================================================
            # ANTERIOR
            # ==========================================================

            previous_orders = self._get_order_rows(
                previous_from,
                previous_to,
            )

            previous_receipts = (
                self._get_receipt_rows(
                    previous_from,
                    previous_to,
                )
            )

            previous_out = self._get_outgoing_rows(
                previous_from,
                previous_to,
            )

            current_agg = (
                self._aggregate_month_product(
                    current_orders,
                    current_receipts,
                    current_out,
                )
            )

            previous_agg = (
                self._aggregate_month_product(
                    previous_orders,
                    previous_receipts,
                    previous_out,
                )
            )

            # ==========================================================
            # PRODUCTOS INVOLUCRADOS
            # ==========================================================

            product_ids = set()

            for collection in [
                current_orders,
                current_receipts,
                current_out,
                previous_orders,
                previous_receipts,
                previous_out,
            ]:
                product_ids.update(
                    row["product_id"]
                    for row in collection
                )

            current_stock = (
                self._get_current_stock(
                    product_ids
                )
            )

            pending_purchase = (
                self._get_open_purchase_pending(
                    product_ids
                )
            )

            Product = self.env[
                "product.product"
            ].sudo()

            # ==========================================================
            # TOTAL CONSUMO POR PRODUCTO
            # ==========================================================

            current_consumption = defaultdict(float)
            previous_consumption = defaultdict(float)

            current_purchase_qty = defaultdict(float)
            current_received_qty = defaultdict(float)

            current_purchase_value = defaultdict(float)
            current_received_value = defaultdict(float)

            for row in current_out:
                current_consumption[
                    row["product_id"]
                ] += row["qty"]

            for row in previous_out:
                previous_consumption[
                    row["product_id"]
                ] += row["qty"]

            for row in current_orders:
                current_purchase_qty[
                    row["product_id"]
                ] += row["ordered_qty"]

                current_purchase_value[
                    row["product_id"]
                ] += row["ordered_value_company"]

            for row in current_receipts:
                current_received_qty[
                    row["product_id"]
                ] += row["received_qty"]

                current_received_value[
                    row["product_id"]
                ] += row["received_value_company"]

            # ==========================================================
            # AREA
            # ==========================================================

            by_area_product = defaultdict(
                lambda: {
                    "qty": 0.0,
                    "amount": 0.0,
                    "pickings": set(),
                    "uom": "",
                }
            )

            by_area_month_product = defaultdict(
                lambda: {
                    "qty": 0.0,
                    "amount": 0.0,
                    "pickings": set(),
                    "uom": "",
                }
            )

            for row in history_out:

                key = (
                    row["area"],
                    row["product_id"],
                    row["sku"],
                    row["product"],
                )

                values = by_area_product[key]

                values["qty"] += row["qty"]
                values["amount"] += row["amount"]
                values["uom"] = row["uom"]

                if row["picking"]:
                    values["pickings"].add(
                        row["picking"]
                    )

                key_month = (
                    row["month"],
                    row["area"],
                    row["product_id"],
                    row["sku"],
                    row["product"],
                )

                values = (
                    by_area_month_product[
                        key_month
                    ]
                )

                values["qty"] += row["qty"]
                values["amount"] += row["amount"]
                values["uom"] = row["uom"]

                if row["picking"]:
                    values["pickings"].add(
                        row["picking"]
                    )

            # ==========================================================
            # XLSX
            # ==========================================================

            fd, filepath = tempfile.mkstemp(
                prefix="planeacion_insumos_",
                suffix=".xlsx",
            )

            os.close(fd)

            workbook = None

            try:

                workbook = xlsxwriter.Workbook(
                    filepath
                )

                fmt_header = workbook.add_format({
                    "bold": True,
                    "bg_color": "#002060",
                    "font_color": "#FFFFFF",
                    "border": 1,
                    "valign": "vcenter",
                })

                fmt_money = workbook.add_format({
                    "num_format": '$#,##0.00',
                })

                fmt_qty = workbook.add_format({
                    "num_format": '#,##0.00',
                })

                fmt_pct = workbook.add_format({
                    "num_format": '0.0%',
                })

                fmt_title = workbook.add_format({
                    "bold": True,
                    "font_size": 14,
                })

                # ======================================================
                # 1. RESUMEN EJECUTIVO
                # ======================================================

                sheet = workbook.add_worksheet(
                    "Resumen Ejecutivo"
                )

                sheet.write(
                    0,
                    0,
                    "Planeacion de compras y consumo de insumos",
                    fmt_title,
                )

                summary = [
                    (
                        "Historico completo",
                        "%s a %s"
                        % (
                            history_from,
                            history_to,
                        ),
                    ),
                    (
                        "Planeacion actual",
                        "%s a %s"
                        % (
                            current_from,
                            current_to,
                        ),
                    ),
                    (
                        "Comparable anterior",
                        "%s a %s"
                        % (
                            previous_from,
                            previous_to,
                        ),
                    ),
                    (
                        "Colchon seguridad",
                        "%.2f%%"
                        % self.safety_percent,
                    ),
                    (
                        "OC actuales",
                        len(
                            set(
                                row["po"]
                                for row
                                in current_orders
                                if row["po"]
                            )
                        ),
                    ),
                    (
                        "Recepciones actuales",
                        len(
                            set(
                                row["picking"]
                                for row
                                in current_receipts
                                if row["picking"]
                            )
                        ),
                    ),
                    (
                        "Transferencias consumo",
                        len(
                            set(
                                row["picking"]
                                for row
                                in current_out
                                if row["picking"]
                            )
                        ),
                    ),
                    (
                        "Productos con actividad",
                        len(product_ids),
                    ),
                    (
                        "Valor OC actual MXN",
                        sum(
                            row["ordered_value_company"]
                            for row
                            in current_orders
                        ),
                    ),
                    (
                        "Valor recibido actual MXN",
                        sum(
                            row["received_value_company"]
                            for row
                            in current_receipts
                        ),
                    ),
                    (
                        "Gasto consumo actual",
                        sum(
                            row["amount"]
                            for row
                            in current_out
                        ),
                    ),
                    (
                        "Gasto consumo anterior",
                        sum(
                            row["amount"]
                            for row
                            in previous_out
                        ),
                    ),
                ]

                row_num = 2

                money_labels = {
                    "Valor OC actual MXN",
                    "Valor recibido actual MXN",
                    "Gasto consumo actual",
                    "Gasto consumo anterior",
                }

                for label, value in summary:

                    sheet.write(
                        row_num,
                        0,
                        label,
                        fmt_header,
                    )

                    if label in money_labels:
                        sheet.write_number(
                            row_num,
                            1,
                            value,
                            fmt_money,
                        )
                    elif isinstance(
                        value,
                        (int, float)
                    ):
                        sheet.write_number(
                            row_num,
                            1,
                            value,
                        )
                    else:
                        sheet.write(
                            row_num,
                            1,
                            value,
                        )

                    row_num += 1

                sheet.set_column(
                    "A:A",
                    32,
                )

                sheet.set_column(
                    "B:B",
                    35,
                )

                # ======================================================
                # 2. PLANEACION DE COMPRA
                # ======================================================

                sheet = workbook.add_worksheet(
                    "Planeacion Compra"
                )

                headers = [
                    "SKU",
                    "Producto",
                    "Unidad",
                    "Consumo Anterior",
                    "Consumo Actual",
                    "Tendencia %",
                    "Proyeccion Proxima",
                    "Colchon %",
                    "Necesidad con Colchon",
                    "Stock Fisico 822",
                    "Reservado 822",
                    "Disponible 822",
                    "Pendiente por Recibir",
                    "Cobertura Disponible + Pendiente",
                    "Compra Sugerida",
                    "Costo Prom Compra Actual",
                    "Presupuesto Compra Sugerida",
                ]

                for col, header in enumerate(
                    headers
                ):
                    sheet.write(
                        0,
                        col,
                        header,
                        fmt_header,
                    )

                planning_rows = []

                for product_id in sorted(
                    product_ids
                ):

                    product = Product.browse(
                        product_id
                    )

                    previous_qty = (
                        previous_consumption[
                            product_id
                        ]
                    )

                    current_qty = (
                        current_consumption[
                            product_id
                        ]
                    )

                    if previous_qty:
                        trend = (
                            current_qty
                            - previous_qty
                        ) / previous_qty
                    else:
                        trend = (
                            1.0
                            if current_qty > 0
                            else 0.0
                        )

                    # La temporada actual comparable
                    # ya contiene la tendencia observada.
                    # Por seguridad usamos el mayor consumo
                    # de ambos periodos.
                    projection = max(
                        previous_qty,
                        current_qty,
                    )

                    need_with_safety = (
                        projection
                        * (
                            1.0
                            + (
                                self.safety_percent
                                / 100.0
                            )
                        )
                    )

                    stock_values = (
                        current_stock[
                            product_id
                        ]
                    )

                    physical = stock_values[
                        "quantity"
                    ]

                    reserved = stock_values[
                        "reserved"
                    ]

                    available = max(
                        0.0,
                        stock_values[
                            "available"
                        ],
                    )

                    pending = max(
                        0.0,
                        pending_purchase[
                            product_id
                        ],
                    )

                    coverage = (
                        available
                        + pending
                    )

                    suggested = max(
                        0.0,
                        need_with_safety
                        - coverage,
                    )

                    received_qty = (
                        current_received_qty[
                            product_id
                        ]
                    )

                    received_value = (
                        current_received_value[
                            product_id
                        ]
                    )

                    avg_cost = (
                        received_value
                        / received_qty
                        if received_qty
                        else (
                            product
                            .with_company(
                                self.COMPANY_ID
                            )
                            .standard_price
                            or 0.0
                        )
                    )

                    budget = (
                        suggested
                        * avg_cost
                    )

                    planning_rows.append({
                        "product": product,
                        "previous_qty": previous_qty,
                        "current_qty": current_qty,
                        "trend": trend,
                        "projection": projection,
                        "need": need_with_safety,
                        "physical": physical,
                        "reserved": reserved,
                        "available": available,
                        "pending": pending,
                        "coverage": coverage,
                        "suggested": suggested,
                        "avg_cost": avg_cost,
                        "budget": budget,
                    })

                planning_rows.sort(
                    key=lambda row: (
                        -row["budget"],
                        row["product"].display_name,
                    )
                )

                row_num = 1

                for row in planning_rows:

                    product = row["product"]

                    sheet.write(
                        row_num,
                        0,
                        product.default_code
                        or "",
                    )

                    sheet.write(
                        row_num,
                        1,
                        product.display_name,
                    )

                    sheet.write(
                        row_num,
                        2,
                        product.uom_id.name,
                    )

                    sheet.write_number(
                        row_num,
                        3,
                        row["previous_qty"],
                        fmt_qty,
                    )

                    sheet.write_number(
                        row_num,
                        4,
                        row["current_qty"],
                        fmt_qty,
                    )

                    sheet.write_number(
                        row_num,
                        5,
                        row["trend"],
                        fmt_pct,
                    )

                    sheet.write_number(
                        row_num,
                        6,
                        row["projection"],
                        fmt_qty,
                    )

                    sheet.write_number(
                        row_num,
                        7,
                        self.safety_percent / 100.0,
                        fmt_pct,
                    )

                    sheet.write_number(
                        row_num,
                        8,
                        row["need"],
                        fmt_qty,
                    )

                    sheet.write_number(
                        row_num,
                        9,
                        row["physical"],
                        fmt_qty,
                    )

                    sheet.write_number(
                        row_num,
                        10,
                        row["reserved"],
                        fmt_qty,
                    )

                    sheet.write_number(
                        row_num,
                        11,
                        row["available"],
                        fmt_qty,
                    )

                    sheet.write_number(
                        row_num,
                        12,
                        row["pending"],
                        fmt_qty,
                    )

                    sheet.write_number(
                        row_num,
                        13,
                        row["coverage"],
                        fmt_qty,
                    )

                    sheet.write_number(
                        row_num,
                        14,
                        row["suggested"],
                        fmt_qty,
                    )

                    sheet.write_number(
                        row_num,
                        15,
                        row["avg_cost"],
                        fmt_money,
                    )

                    sheet.write_number(
                        row_num,
                        16,
                        row["budget"],
                        fmt_money,
                    )

                    row_num += 1

                sheet.set_column(
                    "A:A",
                    20,
                )

                sheet.set_column(
                    "B:B",
                    60,
                )

                sheet.set_column(
                    "C:C",
                    14,
                )

                sheet.set_column(
                    "D:Q",
                    20,
                )

                sheet.freeze_panes(
                    1,
                    0,
                )

                sheet.autofilter(
                    0,
                    0,
                    max(
                        row_num - 1,
                        1,
                    ),
                    16,
                )

                # ======================================================
                # 3. COMPRAS VS SALIDAS MES
                # ======================================================

                sheet = workbook.add_worksheet(
                    "Compras vs Salidas Mes"
                )

                headers = [
                    "Mes",
                    "SKU",
                    "Producto",
                    "Pedido OC",
                    "Recibido",
                    "Consumido",
                    "Recibido - Consumido",
                    "Unidad",
                    "Valor OC MXN",
                    "Valor Recibido MXN",
                    "Gasto Consumo",
                    "Costo Prom Recibido",
                ]

                for col, header in enumerate(
                    headers
                ):
                    sheet.write(
                        0,
                        col,
                        header,
                        fmt_header,
                    )

                row_num = 1

                current_year = (
                    current_from.year
                )

                for key in sorted(
                    current_agg.keys(),
                    key=lambda item: (
                        item[0],
                        item[3],
                    ),
                ):

                    (
                        month_number,
                        product_id,
                        sku,
                        product_name,
                    ) = key

                    values = (
                        current_agg[key]
                    )

                    avg_received = (
                        values["received_value"]
                        / values["received_qty"]
                        if values[
                            "received_qty"
                        ]
                        else 0.0
                    )

                    product = Product.browse(
                        product_id
                    )

                    sheet.write(
                        row_num,
                        0,
                        "%04d-%02d"
                        % (
                            current_year,
                            month_number,
                        ),
                    )

                    sheet.write(
                        row_num,
                        1,
                        sku,
                    )

                    sheet.write(
                        row_num,
                        2,
                        product_name,
                    )

                    sheet.write_number(
                        row_num,
                        3,
                        values["ordered_qty"],
                        fmt_qty,
                    )

                    sheet.write_number(
                        row_num,
                        4,
                        values["received_qty"],
                        fmt_qty,
                    )

                    sheet.write_number(
                        row_num,
                        5,
                        values["outgoing_qty"],
                        fmt_qty,
                    )

                    sheet.write_number(
                        row_num,
                        6,
                        (
                            values["received_qty"]
                            - values["outgoing_qty"]
                        ),
                        fmt_qty,
                    )

                    sheet.write(
                        row_num,
                        7,
                        product.uom_id.name,
                    )

                    sheet.write_number(
                        row_num,
                        8,
                        values["ordered_value"],
                        fmt_money,
                    )

                    sheet.write_number(
                        row_num,
                        9,
                        values["received_value"],
                        fmt_money,
                    )

                    sheet.write_number(
                        row_num,
                        10,
                        values["outgoing_value"],
                        fmt_money,
                    )

                    sheet.write_number(
                        row_num,
                        11,
                        avg_received,
                        fmt_money,
                    )

                    row_num += 1

                sheet.set_column(
                    "A:A",
                    12,
                )

                sheet.set_column(
                    "B:B",
                    20,
                )

                sheet.set_column(
                    "C:C",
                    60,
                )

                sheet.set_column(
                    "D:L",
                    20,
                )

                sheet.freeze_panes(
                    1,
                    0,
                )

                sheet.autofilter(
                    0,
                    0,
                    max(row_num - 1, 1),
                    11,
                )

                # ======================================================
                # 4. ACTUAL VS ANTERIOR
                # ======================================================

                sheet = workbook.add_worksheet(
                    "Actual vs Anterior"
                )

                headers = [
                    "Mes",
                    "SKU",
                    "Producto",
                    "Pedido Anterior",
                    "Recibido Anterior",
                    "Consumo Anterior",
                    "Pedido Actual",
                    "Recibido Actual",
                    "Consumo Actual",
                    "Var Consumo %",
                    "Var Recibido %",
                    "Unidad",
                ]

                for col, header in enumerate(
                    headers
                ):
                    sheet.write(
                        0,
                        col,
                        header,
                        fmt_header,
                    )

                all_keys = sorted(
                    set(
                        current_agg.keys()
                    )
                    | set(
                        previous_agg.keys()
                    ),
                    key=lambda item: (
                        item[0],
                        item[3],
                    ),
                )

                row_num = 1

                for key in all_keys:

                    (
                        month_number,
                        product_id,
                        sku,
                        product_name,
                    ) = key

                    current_values = (
                        current_agg.get(
                            key,
                            {}
                        )
                    )

                    previous_values = (
                        previous_agg.get(
                            key,
                            {}
                        )
                    )

                    c_order = (
                        current_values.get(
                            "ordered_qty",
                            0.0,
                        )
                    )

                    c_received = (
                        current_values.get(
                            "received_qty",
                            0.0,
                        )
                    )

                    c_out = (
                        current_values.get(
                            "outgoing_qty",
                            0.0,
                        )
                    )

                    p_order = (
                        previous_values.get(
                            "ordered_qty",
                            0.0,
                        )
                    )

                    p_received = (
                        previous_values.get(
                            "received_qty",
                            0.0,
                        )
                    )

                    p_out = (
                        previous_values.get(
                            "outgoing_qty",
                            0.0,
                        )
                    )

                    var_out = (
                        (c_out - p_out)
                        / p_out
                        if p_out
                        else (
                            1.0
                            if c_out
                            else 0.0
                        )
                    )

                    var_received = (
                        (
                            c_received
                            - p_received
                        )
                        / p_received
                        if p_received
                        else (
                            1.0
                            if c_received
                            else 0.0
                        )
                    )

                    product = Product.browse(
                        product_id
                    )

                    sheet.write(
                        row_num,
                        0,
                        "%02d"
                        % month_number,
                    )

                    sheet.write(
                        row_num,
                        1,
                        sku,
                    )

                    sheet.write(
                        row_num,
                        2,
                        product_name,
                    )

                    for col, value in [
                        (3, p_order),
                        (4, p_received),
                        (5, p_out),
                        (6, c_order),
                        (7, c_received),
                        (8, c_out),
                    ]:
                        sheet.write_number(
                            row_num,
                            col,
                            value,
                            fmt_qty,
                        )

                    sheet.write_number(
                        row_num,
                        9,
                        var_out,
                        fmt_pct,
                    )

                    sheet.write_number(
                        row_num,
                        10,
                        var_received,
                        fmt_pct,
                    )

                    sheet.write(
                        row_num,
                        11,
                        product.uom_id.name,
                    )

                    row_num += 1

                sheet.set_column(
                    "A:A",
                    10,
                )

                sheet.set_column(
                    "B:B",
                    20,
                )

                sheet.set_column(
                    "C:C",
                    60,
                )

                sheet.set_column(
                    "D:L",
                    18,
                )

                sheet.freeze_panes(
                    1,
                    0,
                )

                sheet.autofilter(
                    0,
                    0,
                    max(row_num - 1, 1),
                    11,
                )

                # ======================================================
                # 5. PRODUCTO POR AREA
                # ======================================================

                sheet = workbook.add_worksheet(
                    "Producto por Area"
                )

                headers = [
                    "Area",
                    "SKU",
                    "Producto",
                    "Cantidad",
                    "Unidad",
                    "Transferencias",
                    "Gasto",
                ]

                for col, header in enumerate(
                    headers
                ):
                    sheet.write(
                        0,
                        col,
                        header,
                        fmt_header,
                    )

                row_num = 1

                for key, values in sorted(
                    by_area_product.items(),
                    key=lambda item: (
                        item[0][0],
                        item[0][3],
                    ),
                ):

                    (
                        area,
                        product_id,
                        sku,
                        product_name,
                    ) = key

                    product = Product.browse(
                        product_id
                    )

                    sheet.write(
                        row_num,
                        0,
                        area,
                    )

                    sheet.write(
                        row_num,
                        1,
                        sku,
                    )

                    sheet.write(
                        row_num,
                        2,
                        product_name,
                    )

                    sheet.write_number(
                        row_num,
                        3,
                        values["qty"],
                        fmt_qty,
                    )

                    sheet.write(
                        row_num,
                        4,
                        product.uom_id.name,
                    )

                    sheet.write_number(
                        row_num,
                        5,
                        len(
                            values["pickings"]
                        ),
                    )

                    sheet.write_number(
                        row_num,
                        6,
                        values["amount"],
                        fmt_money,
                    )

                    row_num += 1

                sheet.set_column(
                    "A:A",
                    35,
                )

                sheet.set_column(
                    "B:B",
                    20,
                )

                sheet.set_column(
                    "C:C",
                    60,
                )

                sheet.set_column(
                    "D:G",
                    18,
                )

                sheet.freeze_panes(
                    1,
                    0,
                )

                # ======================================================
                # 6. AREA PRODUCTO MES
                # ======================================================

                sheet = workbook.add_worksheet(
                    "Area Producto Mes"
                )

                headers = [
                    "Mes",
                    "Area",
                    "SKU",
                    "Producto",
                    "Cantidad",
                    "Unidad",
                    "Transferencias",
                    "Gasto",
                ]

                for col, header in enumerate(
                    headers
                ):
                    sheet.write(
                        0,
                        col,
                        header,
                        fmt_header,
                    )

                row_num = 1

                for key, values in sorted(
                    by_area_month_product.items(),
                    key=lambda item: (
                        item[0][0],
                        item[0][1],
                        item[0][4],
                    ),
                ):

                    (
                        month,
                        area,
                        product_id,
                        sku,
                        product_name,
                    ) = key

                    product = Product.browse(
                        product_id
                    )

                    sheet.write(
                        row_num,
                        0,
                        month,
                    )

                    sheet.write(
                        row_num,
                        1,
                        area,
                    )

                    sheet.write(
                        row_num,
                        2,
                        sku,
                    )

                    sheet.write(
                        row_num,
                        3,
                        product_name,
                    )

                    sheet.write_number(
                        row_num,
                        4,
                        values["qty"],
                        fmt_qty,
                    )

                    sheet.write(
                        row_num,
                        5,
                        product.uom_id.name,
                    )

                    sheet.write_number(
                        row_num,
                        6,
                        len(
                            values["pickings"]
                        ),
                    )

                    sheet.write_number(
                        row_num,
                        7,
                        values["amount"],
                        fmt_money,
                    )

                    row_num += 1

                sheet.set_column(
                    "A:A",
                    12,
                )

                sheet.set_column(
                    "B:B",
                    35,
                )

                sheet.set_column(
                    "C:C",
                    20,
                )

                sheet.set_column(
                    "D:D",
                    60,
                )

                sheet.set_column(
                    "E:H",
                    18,
                )

                sheet.freeze_panes(
                    1,
                    0,
                )

                # ======================================================
                # 7. COMPRAS DETALLE - OC
                # ======================================================

                sheet = workbook.add_worksheet(
                    "Compras Detalle"
                )

                headers = [
                    "Fecha OC",
                    "Mes",
                    "OC",
                    "Proveedor",
                    "SKU",
                    "Producto",
                    "Pedido",
                    "Recibido Acumulado OC",
                    "Pendiente OC",
                    "Unidad",
                    "Precio Original",
                    "Moneda",
                    "Costo Unitario MXN",
                    "Valor OC MXN",
                ]

                for col, header in enumerate(
                    headers
                ):
                    sheet.write(
                        0,
                        col,
                        header,
                        fmt_header,
                    )

                row_num = 1

                for row in history_orders:

                    sheet.write(
                        row_num,
                        0,
                        row["date"].strftime(
                            "%Y-%m-%d"
                        ),
                    )

                    sheet.write(
                        row_num,
                        1,
                        row["month"],
                    )

                    sheet.write(
                        row_num,
                        2,
                        row["po"],
                    )

                    sheet.write(
                        row_num,
                        3,
                        row["supplier"],
                    )

                    sheet.write(
                        row_num,
                        4,
                        row["sku"],
                    )

                    sheet.write(
                        row_num,
                        5,
                        row["product"],
                    )

                    sheet.write_number(
                        row_num,
                        6,
                        row["ordered_qty"],
                        fmt_qty,
                    )

                    sheet.write_number(
                        row_num,
                        7,
                        row["received_lifetime"],
                        fmt_qty,
                    )

                    sheet.write_number(
                        row_num,
                        8,
                        row["pending_qty"],
                        fmt_qty,
                    )

                    sheet.write(
                        row_num,
                        9,
                        row["uom"],
                    )

                    sheet.write_number(
                        row_num,
                        10,
                        row["price_original"],
                        fmt_money,
                    )

                    sheet.write(
                        row_num,
                        11,
                        row["currency"],
                    )

                    sheet.write_number(
                        row_num,
                        12,
                        row["unit_cost_company"],
                        fmt_money,
                    )

                    sheet.write_number(
                        row_num,
                        13,
                        row["ordered_value_company"],
                        fmt_money,
                    )

                    row_num += 1

                sheet.set_column(
                    "A:B",
                    12,
                )

                sheet.set_column(
                    "C:C",
                    18,
                )

                sheet.set_column(
                    "D:D",
                    40,
                )

                sheet.set_column(
                    "E:E",
                    20,
                )

                sheet.set_column(
                    "F:F",
                    60,
                )

                sheet.set_column(
                    "G:N",
                    20,
                )

                sheet.freeze_panes(
                    1,
                    0,
                )

                # ======================================================
                # 8. RECEPCIONES DETALLE
                # ======================================================

                sheet = workbook.add_worksheet(
                    "Recepciones Detalle"
                )

                headers = [
                    "Fecha Recepcion",
                    "Mes",
                    "OC",
                    "Proveedor",
                    "Recepcion",
                    "SKU",
                    "Producto",
                    "Recibido",
                    "Unidad",
                    "Costo Unitario MXN",
                    "Valor Recibido MXN",
                ]

                for col, header in enumerate(
                    headers
                ):
                    sheet.write(
                        0,
                        col,
                        header,
                        fmt_header,
                    )

                row_num = 1

                for row in history_receipts:

                    sheet.write(
                        row_num,
                        0,
                        row["date"].strftime(
                            "%Y-%m-%d"
                        ),
                    )

                    sheet.write(
                        row_num,
                        1,
                        row["month"],
                    )

                    sheet.write(
                        row_num,
                        2,
                        row["po"],
                    )

                    sheet.write(
                        row_num,
                        3,
                        row["supplier"],
                    )

                    sheet.write(
                        row_num,
                        4,
                        row["picking"],
                    )

                    sheet.write(
                        row_num,
                        5,
                        row["sku"],
                    )

                    sheet.write(
                        row_num,
                        6,
                        row["product"],
                    )

                    sheet.write_number(
                        row_num,
                        7,
                        row["received_qty"],
                        fmt_qty,
                    )

                    sheet.write(
                        row_num,
                        8,
                        row["uom"],
                    )

                    sheet.write_number(
                        row_num,
                        9,
                        row["unit_cost_company"],
                        fmt_money,
                    )

                    sheet.write_number(
                        row_num,
                        10,
                        row["received_value_company"],
                        fmt_money,
                    )

                    row_num += 1

                sheet.set_column(
                    "A:B",
                    12,
                )

                sheet.set_column(
                    "C:C",
                    18,
                )

                sheet.set_column(
                    "D:D",
                    40,
                )

                sheet.set_column(
                    "E:E",
                    20,
                )

                sheet.set_column(
                    "F:F",
                    20,
                )

                sheet.set_column(
                    "G:G",
                    60,
                )

                sheet.set_column(
                    "H:K",
                    20,
                )

                sheet.freeze_panes(
                    1,
                    0,
                )

                # ======================================================
                # 9. SALIDAS DETALLE
                # ======================================================

                sheet = workbook.add_worksheet(
                    "Salidas Detalle"
                )

                headers = [
                    "Fecha",
                    "Mes",
                    "Transferencia",
                    "Area",
                    "Contacto",
                    "Notas",
                    "Responsable",
                    "SKU",
                    "Producto",
                    "Cantidad",
                    "Unidad",
                    "Costo Unitario",
                    "Fuente Costo",
                    "Gasto",
                ]

                for col, header in enumerate(
                    headers
                ):
                    sheet.write(
                        0,
                        col,
                        header,
                        fmt_header,
                    )

                row_num = 1

                for row in history_out:

                    sheet.write(
                        row_num,
                        0,
                        row["date"].strftime(
                            "%Y-%m-%d"
                        ),
                    )

                    sheet.write(
                        row_num,
                        1,
                        row["month"],
                    )

                    sheet.write(
                        row_num,
                        2,
                        row["picking"],
                    )

                    sheet.write(
                        row_num,
                        3,
                        row["area"],
                    )

                    sheet.write(
                        row_num,
                        4,
                        row["contact"],
                    )

                    sheet.write(
                        row_num,
                        5,
                        row["note"],
                    )

                    sheet.write(
                        row_num,
                        6,
                        row["responsible"],
                    )

                    sheet.write(
                        row_num,
                        7,
                        row["sku"],
                    )

                    sheet.write(
                        row_num,
                        8,
                        row["product"],
                    )

                    sheet.write_number(
                        row_num,
                        9,
                        row["qty"],
                        fmt_qty,
                    )

                    sheet.write(
                        row_num,
                        10,
                        row["uom"],
                    )

                    sheet.write_number(
                        row_num,
                        11,
                        row["unit_cost"],
                        fmt_money,
                    )

                    sheet.write(
                        row_num,
                        12,
                        row["cost_source"],
                    )

                    sheet.write_number(
                        row_num,
                        13,
                        row["amount"],
                        fmt_money,
                    )

                    row_num += 1

                sheet.set_column(
                    "A:B",
                    12,
                )

                sheet.set_column(
                    "C:C",
                    20,
                )

                sheet.set_column(
                    "D:E",
                    35,
                )

                sheet.set_column(
                    "F:F",
                    60,
                )

                sheet.set_column(
                    "G:G",
                    30,
                )

                sheet.set_column(
                    "H:H",
                    20,
                )

                sheet.set_column(
                    "I:I",
                    60,
                )

                sheet.set_column(
                    "J:N",
                    20,
                )

                sheet.freeze_panes(
                    1,
                    0,
                )

                # ======================================================
                # 10. METODOLOGIA
                # ======================================================

                sheet = workbook.add_worksheet(
                    "Metodologia"
                )

                methodology = [
                    (
                        "Empresa",
                        "CEDIS GRUPO L7",
                    ),
                    (
                        "Ubicacion insumos",
                        "CEDIN/Existencias (822)",
                    ),
                    (
                        "Destino consumo",
                        "Traspaso Entrega Insumos (829)",
                    ),
                    (
                        "Periodo actual",
                        "%s a %s"
                        % (
                            current_from,
                            current_to,
                        ),
                    ),
                    (
                        "Periodo anterior",
                        "%s a %s"
                        % (
                            previous_from,
                            previous_to,
                        ),
                    ),
                    (
                        "Pedido OC",
                        (
                            "Se toma una sola vez desde "
                            "purchase.order.line usando "
                            "la fecha real de la orden."
                        ),
                    ),
                    (
                        "Recepcion",
                        (
                            "Movimiento DONE con "
                            "purchase_line_id y destino "
                            "CEDIN/Existencias."
                        ),
                    ),
                    (
                        "Consumo",
                        (
                            "Movimiento DONE desde "
                            "CEDIN/Existencias (822) "
                            "a Traspaso Entrega "
                            "Insumos (829)."
                        ),
                    ),
                    (
                        "Stock disponible",
                        (
                            "stock.quant quantity menos "
                            "reserved_quantity solamente "
                            "en ubicacion 822."
                        ),
                    ),
                    (
                        "Pendiente por recibir",
                        (
                            "Ordenes de compra confirmadas: "
                            "cantidad pedida menos "
                            "cantidad recibida."
                        ),
                    ),
                    (
                        "Proyeccion proxima",
                        (
                            "Mayor entre consumo del periodo "
                            "anterior y consumo del periodo "
                            "actual comparable."
                        ),
                    ),
                    (
                        "Necesidad con colchon",
                        (
                            "Proyeccion multiplicada por "
                            "1 + porcentaje de seguridad."
                        ),
                    ),
                    (
                        "Compra sugerida",
                        (
                            "Necesidad con colchon menos "
                            "stock disponible menos "
                            "pendiente por recibir. "
                            "Nunca menor a cero."
                        ),
                    ),
                    (
                        "Valores de compra",
                        (
                            "Sin impuestos. Convertidos a "
                            "moneda de la empresa usando "
                            "el tipo de cambio de la OC."
                        ),
                    ),
                ]

                row_num = 0

                for label, value in methodology:

                    sheet.write(
                        row_num,
                        0,
                        label,
                        fmt_header,
                    )

                    sheet.write(
                        row_num,
                        1,
                        value,
                    )

                    row_num += 1

                sheet.set_column(
                    "A:A",
                    32,
                )

                sheet.set_column(
                    "B:B",
                    110,
                )

                workbook.close()
                workbook = None

                with open(
                    filepath,
                    "rb",
                ) as fh:
                    binary_data = fh.read()

            finally:

                if workbook:
                    workbook.close()

                if os.path.isfile(
                    filepath
                ):
                    os.unlink(
                        filepath
                    )

            # ==========================================================
            # ADJUNTO
            # ==========================================================

            if self.attachment_id:
                self.attachment_id.sudo().unlink()

            filename = (
                "historico_planeacion_insumos_%s_a_%s.xlsx"
                % (
                    history_from,
                    history_to,
                )
            )

            attachment = (
                self.env[
                    "ir.attachment"
                ]
                .sudo()
                .create({
                    "name": filename,
                    "type": "binary",
                    "datas": base64.b64encode(
                        binary_data
                    ),
                    "mimetype": (
                        "application/vnd."
                        "openxmlformats-"
                        "officedocument."
                        "spreadsheetml.sheet"
                    ),
                    "res_model": self._name,
                    "res_id": self.id,
                })
            )

            total_amount = sum(
                row["amount"]
                for row in history_out
            )

            self.write({
                "state": "done",
                "movement_count": len(
                    history_out
                ),
                "picking_count": len(
                    set(
                        row["picking"]
                        for row in history_out
                        if row["picking"]
                    )
                ),
                "total_amount": total_amount,
                "attachment_id": (
                    attachment.id
                ),
                "error_message": False,
            })

            return {
                "type": "ir.actions.act_window",
                "name": _(
                    "Reporte de planeacion de insumos"
                ),
                "res_model": self._name,
                "view_mode": "form",
                "res_id": self.id,
                "target": "current",
            }

        except Exception as exc:

            self.write({
                "state": "error",
                "error_message": str(
                    exc
                ),
            })

            raise