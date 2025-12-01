# -*- coding: utf-8 -*-
from odoo import models, api
import logging

_logger = logging.getLogger(__name__)


class PosOrder(models.Model):
    _inherit = "pos.order"

    @api.model
    def create_from_ui(self, orders, draft=False):
        # 1) Comportamiento estándar: crea los pedidos de POS
        order_ids = super().create_from_ui(orders, draft=draft)

        if not order_ids:
            return order_ids
        if not isinstance(order_ids, (list, tuple)):
            order_ids = [order_ids]

        _logger.info("[G7][POS-Coupon] create_from_ui: %s orders -> %s", len(orders), order_ids)

        # 2) Recorremos cada pedido creado junto con su JSON original
        for data, oid in zip(orders, order_ids):
            order = self.browse(oid)
            if not order:
                continue

            codes = set()

            # 2.1 Leer códigos desde el JSON (pack_lot_ids enviados desde el POS)
            data_lines = data.get("data", {}).get("lines", [])
            for line in data_lines:
                vals = line[2] if len(line) > 2 else {}
                for pl in vals.get("pack_lot_ids", []):
                    # pl normalmente es [0, 0, {lot_name: 'CODIGO_CUPON'}]
                    if isinstance(pl, (list, tuple)) and len(pl) >= 3:
                        lot_vals = pl[2] or {}
                        lot_name = lot_vals.get("lot_name") or lot_vals.get("name")
                        if lot_name:
                            codes.add(lot_name)

            # 2.2 Fallback: por si acaso, leer de las líneas ya creadas en la BD
            if not codes:
                for line in order.lines:
                    for pack in line.pack_lot_ids:
                        if pack.lot_name:
                            codes.add(pack.lot_name)

            _logger.info("[G7][POS-Coupon] order %s codes detectados: %s", order.pos_reference, list(codes))

            # 3) Actualizar cada cupón detectado
            for code in codes:
                coupon = self.env["liquidation.coupon"].search([("name", "=", code)], limit=1)
                if not coupon:
                    _logger.warning("[G7][POS-Coupon] cupón %s no encontrado", code)
                    continue

                # Intentar asociar la línea de POS con el mismo producto del cupón
                line = order.lines.filtered(lambda l: l.product_id == coupon.product_id)[:1]
                if not line:
                    line = order.lines[:1]

                vals = {
                    "pos_order_id": order.id,
                    "pos_order_line_id": line.id if line else False,
                }
                # Solo pasamos a usado si estaba en nuevo
                if coupon.state == "new":
                    vals["state"] = "used"

                coupon.write(vals)
                _logger.info(
                    "[G7][POS-Coupon] Cupón %s (%s) marcado como %s en order %s, línea %s",
                    coupon.id,
                    coupon.name,
                    coupon.state,
                    order.pos_reference,
                    line.id if line else "N/A",
                )

        return order_ids
