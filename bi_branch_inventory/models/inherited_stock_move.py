# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from itertools import groupby
from odoo.tools.float_utils import float_compare, float_is_zero, float_round


class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    branch_id = fields.Many2one('res.branch', related='move_id.branch_id')


class StockMove(models.Model):
    _inherit = 'stock.move'

    branch_id = fields.Many2one('res.branch')

    @api.model
    def default_get(self, default_fields):
        res = super(StockMove, self).default_get(default_fields)
        context = self._context
        current_uid = context.get('uid')
        user = self.env['res.users'].browse(current_uid)
        if user.branch_id:
            res.update({
                'branch_id': user.branch_id.id or False
            })
        return res

    def _assign_picking(self):
        """ Try to assign the moves to an existing picking that has not been
        reserved yet and has the same procurement group, locations and picking
        type (moves should already have them identical). Otherwise, create a new
        picking to assign them to. """
        Picking = self.env['stock.picking']
        grouped_moves = groupby(self, key=lambda m: m._key_assign_picking())
        for group, moves in grouped_moves:
            moves = self.env['stock.move'].concat(*moves)
            new_picking = False
            # Could pass the arguments contained in group but they are the same
            # for each move that why moves[0] is acceptable
            picking = moves[0]._search_picking_for_assignation()
            if picking:
                # If a picking is found, we'll append `move` to its move list and thus its
                # `partner_id` and `ref` field will refer to multiple records. In this
                # case, we chose to wipe them.
                vals = {}
                if any(picking.partner_id.id != m.partner_id.id for m in moves):
                    vals['partner_id'] = False
                if any(picking.origin != m.origin for m in moves):
                    vals['origin'] = False
                if vals:
                    picking.write(vals)
            else:
                # Don't create picking for negative moves since they will be
                # reverse and assign to another picking
                moves = moves.filtered(lambda m: float_compare(
                    m.product_uom_qty, 0.0, precision_rounding=m.product_uom.rounding) >= 0)
                if not moves:
                    continue
                new_picking = True
                picking = Picking.create(moves._get_new_picking_values())

            moves.write({'picking_id': picking.id, 'branch_id': picking.branch_id and picking.branch_id.id or False})
            moves._assign_picking_post_process(new=new_picking)
        return True


    def _prepare_account_move_vals(self, credit_account_id, debit_account_id, journal_id, qty, description, svl_id, cost):
        values = super(StockMove, self)._prepare_account_move_vals(
            credit_account_id, debit_account_id, journal_id, qty, description, svl_id, cost)
        values['branch_id'] = self.picking_id.branch_id.id or self.branch_id.id or False,
        return values

    def _generate_valuation_lines_data(self, partner_id, qty, debit_value, credit_value,
                                       debit_account_id, credit_account_id, description):
        # This method returns a dictionary to provide an easy extension hook to modify the valuation lines (see purchase for an example)
        result = super(StockMove, self)._generate_valuation_lines_data(partner_id, qty, debit_value,
                                                                       credit_value, debit_account_id, credit_account_id, description)

        branch_id = False
        if self.branch_id:
            branch_id = self.branch_id.id
        elif self.env.user.branch_id:
            branch_id = self.env.user.branch_id.id

        for res in result:
            result[res].update({'branch_id': branch_id})

        return result
