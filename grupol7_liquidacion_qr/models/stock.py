# -*- coding: utf-8 -*-
from odoo import models

class StockMove(models.Model):
    _inherit = 'stock.move'

    def _action_done(self, cancel_backorder=False):
        res = super()._action_done(cancel_backorder=cancel_backorder)
        for move in self:
            sol = move.sale_line_id
            if sol and sol.x_liq_coupon_id:
                sol.x_liq_coupon_id.write({
                    'picking_id': move.picking_id.id,
                    'move_id': move.id,
                })
        return res
