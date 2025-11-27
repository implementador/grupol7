# -*- coding: utf-8 -*-
import logging
from odoo import api, models

_logger = logging.getLogger(__name__)


class PosOrder(models.Model):
    _inherit = 'pos.order'

    @api.model
    def create_from_ui(self, orders, draft=False):
        """
        Marca los cupones de liquidación como usados después de crear los pedidos desde el POS.
        También llena los campos de trazabilidad.
        """
        order_ids = super(PosOrder, self).create_from_ui(orders, draft=draft)

        if not order_ids:
            return order_ids

        Coupon = self.env['liquidation.coupon'].sudo()

        # Si order_ids viene como un solo ID, lo convertimos en lista
        if isinstance(order_ids, int):
            order_ids = [order_ids]

        # Recorremos cada pedido individualmente
        for i, order_id in enumerate(order_ids):
            try:
                pos_order = self.browse(order_id)
                if not pos_order.exists():
                    continue

                ui_order = orders[i] if i < len(orders) else {}
                data = ui_order.get('data') or {}
                ui_lines = data.get('lines') or []

                _logger.info("[LQ POS] Procesando POS Order %s (ID %s)", pos_order.name, pos_order.id)

                for line_data in ui_lines:
                    if not isinstance(line_data, (list, tuple)) or len(line_data) < 3:
                        continue

                    ui_vals = line_data[2] or {}
                    coupon_id = (
                        ui_vals.get('liquidation_coupon_id')
                        or ui_vals.get('liq_coupon_id')
                        or ui_vals.get('coupon_id')
                    )

                    if not coupon_id:
                        continue

                    coupon = Coupon.browse(coupon_id)
                    if not coupon.exists():
                        _logger.warning("[LQ POS] Cupón ID %s no existe", coupon_id)
                        continue

                    # Buscar línea del pedido
                    product_id = ui_vals.get('product_id')
                    qty = ui_vals.get('qty')
                    price_unit = ui_vals.get('price_unit')

                    pos_line = pos_order.lines.filtered(
                        lambda l: l.product_id.id == product_id
                        and abs(l.qty - qty) < 0.0001
                        and abs(l.price_unit - price_unit) < 0.0001
                    )[:1]

                    coupon.write({
                        'state': 'used',
                        'pos_order_id': pos_order.id,
                        'pos_order_line_id': pos_line.id if pos_line else False,
                    })

                    _logger.info("[LQ POS] Cupón %s marcado como usado en pedido %s",
                                 coupon.display_name, pos_order.name)

            except Exception as e:
                _logger.exception("[LQ POS] Error procesando POS Order ID %s: %s", order_id, e)

        return order_ids
