# -*- coding: utf-8 -*-
import logging
from odoo import api, models

_logger = logging.getLogger(__name__)


class PosOrder(models.Model):
    _inherit = "pos.order"

    @api.model
    def create_from_ui(self, orders, draft=False):
        """Después de crear los pedidos de POS, marcar los cupones como usados
        según el lot_name capturado en el POS.
        """
        # Llamamos al comportamiento estándar
        res = super().create_from_ui(orders, draft=draft)

        # Normalizar el resultado de create_from_ui:
        # a veces es lista de ids, a veces lista de dicts con 'id'
        order_ids = []
        if isinstance(res, list):
            for item in res:
                if isinstance(item, dict):
                    oid = item.get("id")
                    if oid:
                        order_ids.append(oid)
                else:
                    order_ids.append(item)

        if not order_ids:
            return res

        orders_rs = self.browse(order_ids)
        Coupon = self.env["liquidation.coupon"]

        for order in orders_rs:
            _logger.info(
                "[G7][POS-Coupon][PY] Procesando POS %s (%s)", order.name, order.id
            )
            for line in order.lines:
                # pack_lot_ids = lotes / QR capturados en la línea del POS
                for pack_lot in line.pack_lot_ids:
                    code = (pack_lot.lot_name or "").strip()
                    if not code:
                        continue

                    coupon = Coupon.search([("name", "=", code)], limit=1)
                    if not coupon:
                        _logger.info(
                            "[G7][POS-Coupon][PY] No se encontró cupón con código %s",
                            code,
                        )
                        continue

                    vals = {
                        "pos_order_id": order.id,
                        "pos_order_line_id": line.id,
                    }
                    # Solo cambiar a usado si está nuevo
                    if coupon.state == "new":
                        vals["state"] = "used"

                    _logger.info(
                        "[G7][POS-Coupon][PY] Actualizando cupón %s -> vals=%s",
                        coupon.name,
                        vals,
                    )
                    coupon.write(vals)

        return res
