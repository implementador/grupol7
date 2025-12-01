# -*- coding: utf-8 -*-
import logging
from odoo import api, models

_logger = logging.getLogger(__name__)


class PosOrder(models.Model):
    _inherit = "pos.order"

    @api.model
    def create_from_ui(self, orders, draft=False):
        """
        Cuando se valida un pedido del POS, marcar los cupones de liquidación
        como usados y llenar la trazabilidad (Pos Order / Pos Order Line).

        Estrategia:
        - Llamamos al super para crear los pedidos (res).
        - Por cada pedido creado, recorremos sus líneas (pos.order.line).
        - En cada línea, revisamos pack_lot_ids:
            * cada registro tiene lot_name (el código del cupón).
        - Buscamos el liquidation.coupon correspondiente y:
            * ligamos pos_order_id / pos_order_line_id
            * si está en estado 'new', lo pasamos a 'used'.
        """
        res = super().create_from_ui(orders, draft=draft)

        if not isinstance(res, list):
            # Algo raro: no rompemos el flujo normal del POS
            _logger.warning(
                "[G7][POS-Coupon][BACK] Resultado inesperado de create_from_ui: %s",
                res,
            )
            return res

        Coupon = self.env["liquidation.coupon"]

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
                "[G7][POS-Coupon][BACK] Procesando POS order %s (%s) con %s líneas",
                order.id,
                order.pos_reference,
                len(order.lines),
            )

            for line in order.lines:
                # Cada pack_lot representa un código capturado en el POS
                for pack_lot in line.pack_lot_ids:
                    code = pack_lot.lot_name
                    if not code:
                        continue

                    # Buscar cupón por código y producto
                    coupon = Coupon.search(
                        [
                            ("name", "=", code),
                            ("product_id", "=", line.product_id.id),
                        ],
                        limit=1,
                    )
                    if not coupon:
                        _logger.info(
                            "[G7][POS-Coupon][BACK] No se encontró cupón para código %s y producto %s",
                            code,
                            line.product_id.id,
                        )
                        continue

                    vals = {
                        "pos_order_id": order.id,
                        "pos_order_line_id": line.id,
                    }

                    # Sólo pasamos a 'used' si aún está en 'new'
                    if coupon.state == "new":
                        vals["state"] = "used"

                    _logger.info(
                        "[G7][POS-Coupon][BACK] Cupón %s marcado usado en POS order %s, línea %s",
                        coupon.id,
                        order.id,
                        line.id,
                    )
                    coupon.write(vals)

        return res
