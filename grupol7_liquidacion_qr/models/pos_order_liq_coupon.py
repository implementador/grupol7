# -*- coding: utf-8 -*-
import logging

from odoo import api, models

_logger = logging.getLogger(__name__)


class PosOrder(models.Model):
    _inherit = 'pos.order'

    @api.model
    def create_from_ui(self, orders, draft=False):
        """
        Después de crear los pedidos desde el POS, marcamos los cupones
        de liquidación como usados y llenamos la trazabilidad.

        Se espera que en cada línea del pedido que use cupón venga
        ALGUNO de estos campos en el dict de la línea:
            - liquidation_coupon_id
            - liq_coupon_id
            - coupon_id

        Ejemplo de línea que llega desde el POS (simplificado):
            [0, 0, {
                'product_id': 123,
                'qty': 1,
                'price_unit': 1000.0,
                'liquidation_coupon_id': 45,
            }]
        """
        # Primero dejamos que Odoo haga todo lo normal
        order_ids = super(PosOrder, self).create_from_ui(orders, draft=draft)

        # En teoría esto siempre es una lista de IDs
        if not isinstance(order_ids, list):
            _logger.warning("[LQ POS] create_from_ui devolvió %s en lugar de lista", order_ids)
            return order_ids

        Coupon = self.env['liquidation.coupon'].sudo()

        for order_id, ui_order in zip(order_ids, orders):
            pos_order = self.browse(order_id)
            data = (ui_order or {}).get('data') or {}
            ui_lines = data.get('lines') or []

            _logger.info(
                "[LQ POS] Procesando trazabilidad de cupones para POS Order %s (ID %s)",
                pos_order.name, pos_order.id
            )

            for line_data in ui_lines:
                try:
                    # Cada línea viene como [comando, id, dict_vals]
                    if not isinstance(line_data, (list, tuple)) or len(line_data) < 3:
                        continue

                    ui_vals = line_data[2] or {}

                    coupon_id = (
                        ui_vals.get('liquidation_coupon_id')
                        or ui_vals.get('liq_coupon_id')
                        or ui_vals.get('coupon_id')
                    )

                    if not coupon_id:
                        # Esta línea no trae cupón, la ignoramos
                        continue

                    coupon = Coupon.browse(coupon_id)
                    if not coupon.exists():
                        _logger.warning(
                            "[LQ POS] Cupón ID %s no existe, línea UI: %s",
                            coupon_id, ui_vals,
                        )
                        continue

                    # Intentamos localizar la línea de pos.order correspondiente
                    product_id = ui_vals.get('product_id')
                    qty = ui_vals.get('qty')
                    price_unit = ui_vals.get('price_unit')

                    pos_line = pos_order.lines.filtered(
                        lambda l: l.product_id.id == product_id
                        and l.qty == qty
                        and abs((l.price_unit or 0.0) - (price_unit or 0.0)) < 0.0001
                    )[:1]

                    if not pos_line:
                        # Fallback: primera línea con ese producto
                        pos_line = pos_order.lines.filtered(
                            lambda l: l.product_id.id == product_id
                        )[:1]

                    write_vals = {
                        'state': 'used',  # estados: new, used, cancelled, expired
                        'pos_order_id': pos_order.id,
                        'pos_order_line_id': pos_line.id if pos_line else False,
                    }
                    coupon.write(write_vals)

                    _logger.info(
                        "[LQ POS] Cupón %s (ID %s) marcado como USED en POS %s, línea %s",
                        coupon.display_name, coupon.id,
                        pos_order.name,
                        pos_line.id if pos_line else 'N/A',
                    )
                except Exception as e:
                    _logger.exception(
                        "[LQ POS] Error al marcar cupón desde POS Order %s: %s",
                        pos_order.name, e,
                    )

        return order_ids
