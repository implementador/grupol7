from odoo import models

class PosOrder(models.Model):
    _inherit = 'pos.order'

    def _process_order(self, order, draft, existing_order):
        # Dejar que Odoo cree el pedido normalmente
        order_rec = super()._process_order(order, draft, existing_order)

        # Para cada pedido creado, buscar los cupones ligados a sus líneas
        for rec in order_rec:
            coupon_lines = rec.lines.filtered(lambda l: getattr(l, 'coupon_id', False))
            coupons = coupon_lines.mapped('coupon_id').filtered(lambda c: c.state == 'new')
            if coupons:
                coupons.action_mark_used_from_pos()

        return order_rec
