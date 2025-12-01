# -*- coding: utf-8 -*-
from odoo import api, models


class PosOrder(models.Model):
    _inherit = 'pos.order'

    @api.model
    def create_from_ui(self, orders, draft=False):
        """
        Extiende create_from_ui para:
        - Detectar cupones de liquidación usados (por código en pack_lot_ids.lot_name)
        - Llenar trazabilidad en el cupón (POS, venta, picking, movimiento)
        - Cambiar estado del cupón a 'used'
        """
        # Llamamos al flujo normal de Odoo
        result = super().create_from_ui(orders, draft=draft)

        # En Odoo 16 result es una lista de dicts:
        # [{'id': 123, 'pos_reference': 'xxxx', 'account_move': 'xxx'}, ...]
        order_ids = [
            r.get('id')
            for r in (result or [])
            if isinstance(r, dict) and r.get('id')
        ]

        if not order_ids:
            return result

        LiquidationCoupon = self.env['liquidation.coupon']
        pos_orders = self.env['pos.order'].browse(order_ids)

        for order in pos_orders:
            # Solo actuamos en órdenes ya pagadas / finalizadas
            if order.state not in ('paid', 'done', 'invoiced'):
                continue

            sale_order = order.sale_order_id
            picking = order.picking_ids[:1]  # primer picking ligado a la orden

            # Mapeo simple: producto -> primera línea de venta
            sale_line_map = {}
            if sale_order:
                for so_line in sale_order.order_line:
                    sale_line_map.setdefault(so_line.product_id.id, so_line)

            for line in order.lines:
                if not line.pack_lot_ids:
                    continue

                for pack_line in line.pack_lot_ids:
                    coupon_code = pack_line.lot_name
                    if not coupon_code:
                        continue

                    coupon = LiquidationCoupon.search(
                        [('name', '=', coupon_code)],
                        limit=1,
                    )
                    if not coupon:
                        continue

                    values = {
                        # trazabilidad POS
                        'pos_order_id': order.id,
                        'pos_order_line_id': line.id,

                        # trazabilidad venta
                        'sale_order_id': False,
                        'sale_order_line_id': False,

                        # trazabilidad inventario
                        'picking_id': picking.id if picking else False,
                        'move_id': False,

                        # estado
                        'state': 'used',
                    }

                    # Intentar enlazar con SO y movimiento de inventario
                    so_line = sale_line_map.get(line.product_id.id)
                    if so_line:
                        values['sale_order_id'] = so_line.order_id.id
                        values['sale_order_line_id'] = so_line.id
                        move = so_line.move_ids[:1]
                        if move:
                            values['move_id'] = move.id

                    coupon.write(values)

        return result
