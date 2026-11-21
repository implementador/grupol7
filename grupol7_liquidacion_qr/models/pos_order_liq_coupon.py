# -*- coding: utf-8 -*-
import logging
from odoo import api, models

_logger = logging.getLogger(__name__)


class PosOrder(models.Model):
    _inherit = "pos.order"

    @api.model
    def create_from_ui(self, orders, draft=False):
        """
        Después de crear los pedidos del PdV, localizar los cupones de liquidación
        usados en esas líneas y actualizar su trazabilidad:

        - pos_order_id
        - pos_order_line_id
        - picking_id (si existe)
        - state: 'new' -> 'used'
        """
        res = super().create_from_ui(orders, draft=draft)

        # Normalmente res es una lista de dicts: [{'id': 12, 'name': '...', ...}, ...]
        if not isinstance(res, list):
            _logger.warning(
                "[G7][POS-Coupon] Resultado inesperado de create_from_ui: %s", res
            )
            return res

        Coupon = self.env["liquidation.coupon"].sudo()

        for result in res:
            if not isinstance(result, dict):
                continue
            order_id = result.get("id")
            if not order_id:
                continue

            order = self.browse(order_id)
            if not order:
                continue

            _logger.info(
                "[G7][POS-Coupon] Procesando POS order %s (%s) con %s líneas",
                order.id,
                order.pos_reference,
                len(order.lines),
            )

            for line in order.lines:
                code = None

                # 1) Campo técnico x_liq_code si existe
                if "x_liq_code" in line._fields and line.x_liq_code:
                    code = line.x_liq_code

                # 2) Campo studio x_studio_liq_code si existe
                elif (
                    "x_studio_liq_code" in line._fields
                    and line.x_studio_liq_code
                ):
                    code = line.x_studio_liq_code

                else:
                    # 3) Patrón en el texto de la línea: "LIQ/<codigo> ..."
                    txt = (line.display_name or line.name or "").strip()
                    up = txt.upper()
                    if up.startswith("LIQ/"):
                        resto = txt[4:]  # lo que sigue después de "LIQ/"
                        code = resto.split()[0] if resto else None

                if not code:
                    # Línea sin cupón LIQ
                    continue

                # Buscar el cupón por código
                coupon = Coupon.search([("name", "=", code)], limit=1)
                if not coupon:
                    _logger.info(
                        "[G7][POS-Coupon] No se encontró cupón con código %s para línea %s",
                        code,
                        line.id,
                    )
                    continue

                vals = {
                    "pos_order_id": order.id,
                    "pos_order_line_id": line.id,
                }

                # Sólo cambiamos a 'used' si todavía está en 'new'
                if coupon.state == "new":
                    vals["state"] = "used"

                # Si el pedido POS tiene picking, lo ligamos
                if order.picking_id:
                    vals["picking_id"] = order.picking_id.id

                _logger.info(
                    "[G7][POS-Coupon] Cupón %s (%s) ligado a POS order %s, línea %s, vals=%s",
                    coupon.id,
                    coupon.name,
                    order.id,
                    line.id,
                    vals,
                )

                coupon.write(vals)

        return res
