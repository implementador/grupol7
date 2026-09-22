from odoo import models, fields

class LiquidationCoupon(models.Model):
    _inherit = 'liquidation.coupon'

    picking_id = fields.Many2one('stock.picking', string='Salida de inventario', readonly=True, copy=False)
    move_id    = fields.Many2one('stock.move',    string='Movimiento',          readonly=True, copy=False)
