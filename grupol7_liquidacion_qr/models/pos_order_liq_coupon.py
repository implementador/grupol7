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
        - Recorremos en paralelo:
            * orders  -> datos originales que llegaron del POS
            * res     -> info de los pedidos creados ({'id', 'pos_reference', ...})
        - Por cada línea, revisamos pack_lot_ids del JSON (ahí va el código
          del cupón en 'lot_name').
        - Buscamos el liquidation.coupon correspondiente y:
            * ligamos pos_order_id / pos_order_line_id
            * si está en estado 'new', lo pasamos a 'used'
        """
        res = super().create_from_ui(orders, draft=draft)

        # Si algo raro pasa, no rompemos create_from_ui
        if not isinstance(res, list):
            _logger.warning(
                "[G7][POS-Coupon][BACK] Resultado inesperado de create_from_ui: %s",
                res,
            )
            return res

        Coupon = self.env["liquidation.coupon"]

        for ui_order, result in zip(orders, res):
            if not isinstance(result, dict):
                continue

            order_id = result.get("id")
            if not order_id:
                continue

            order = self.browse(order_id)
            if not order:
                continue

            data = ui_order.get("data") or {}
            ui_lines = [line[2] for line in data.get("lines", []) if len(line) >= 3]

            # Normalmente order.lines está en el mismo orden que ui_lines.
            # Filtramos por si hubiera líneas de sección/notas.
            db_lines = order.lines.filtered(lambda l: not l.display_type)

            _logger.info(
                "[G7][POS-Coupon][BACK] Procesando POS order %s (%s) con %s líneas",
                order.id,
                order.pos_reference,
                len(db_lines),
            )

            for idx, ui_line in enumerate(ui_lines):
                if idx >= len(db_lines):
                    break

                db_line = db_lines[idx]
                pack_lots = ui_line.get("pack_lot_ids") or []

                for cmd in pack_lots:
                    # Formato típico: [0, 0, {'lot_name': 'CODIGO'}]
                    if not (isinstance(cmd, (list, tuple)) and len(cmd) >= 3):
                        continue
                    values = cmd[2] or {}
                    lot_name = values.get("lot_name")
                    if not lot_name:
                        continue

                    # Buscar cupón por código y producto
                    coupon = Coupon.search(
                        [
                            ("name", "=", lot_name),
                            ("product_id", "=", db_line.product_id.id),
                        ],
                        limit=1,
                    )
                    if not coupon:
                        _logger.info(
                            "[G7][POS-Coupon][BACK] No se encontró cupón para código %s y producto %s",
                            lot_name,
                            db_line.product_id.id,
                        )
                        continue

                    vals = {
                        "pos_order_id": order.id,
                        "pos_order_line_id": db_line.id,
                    }

                    # Sólo pasamos a 'used' si aún está en 'new'
                    if coupon.state == "new":
                        vals["state"] = "used"

                    _logger.info(
                        "[G7][POS-Coupon][BACK] Cupón %s marcado usado en POS order %s, línea %s",
                        coupon.id,
                        order.id,
                        db_line.id,
                    )
                    coupon.write(vals)

        return res
