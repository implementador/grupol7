# -*- coding: utf-8 -*-
from odoo import models


class PosSession(models.Model):
    _inherit = 'pos.session'
    
    def _get_related_account_moves(self):
        reverse_moves = self.mapped('order_ids.reverse_move')
        result = super(PosSession, self)._get_related_account_moves()
        return result | reverse_moves
