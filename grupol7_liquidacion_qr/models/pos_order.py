# -*- coding: utf-8 -*-
from odoo import api, fields, models

class PosOrderLine(models.Model):
    _inherit = 'pos.order.line'
    x_liq_coupon_id = fields.Many2one("liquidation.coupon", string="Cupón LIQ", copy=False)

class PosOrder(models.Model):
    _inherit = 'pos.order'

    @api.model
    def _order_line_fields(self, line, *args, **kwargs):
        """Recibe lines desde el frontend; inyectamos x_liq_coupon_id si viene en extras.coupon_id"""
        res = super()._order_line_fields(line, *args, **kwargs)
        try:
            # v16 suele venir como [0,0,vals]
            vals = res[2] if isinstance(res, (list, tuple)) and len(res) > 2 else res
            data = line[2] if isinstance(line, (list, tuple)) and len(line) > 2 else line
            coupon_id = (data.get('extras') or {}).get('coupon_id')
            if coupon_id:
                vals['x_liq_coupon_id'] = coupon_id
        except Exception:
            pass
        return res

    def action_pos_order_paid(self):
        res = super().action_pos_order_paid()
        for order in self:
            for line in order.lines.filtered(lambda l: l.x_liq_coupon_id and l.x_liq_coupon_id.state == 'new'):
                vals = {
                    'state': 'redeemed',
                    'pos_order_id': order.id,
                    'pos_order_line_id': line.id,
                }
                if order.picking_id:
                    vals['picking_id'] = order.picking_id.id
                line.x_liq_coupon_id.write(vals)
        return res
