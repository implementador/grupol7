from odoo import models, fields, api

class LiquidationCouponLoc(models.Model):
    _inherit = 'liquidation.coupon'

    location_id = fields.Many2one(
        'stock.location',
        string='Ubicación POS',
        domain=[('usage', '=', 'internal')],
        help='Ubicación/almacén donde está disponible este cupón.'
    )

    qty_at_location = fields.Float(
        string='Existencia en ubicación',
        compute='_compute_qty_at_location'
    )

    @api.depends('location_id', 'product_id')
    def _compute_qty_at_location(self):
        Quant = self.env['stock.quant']
        for rec in self:
            qty = 0.0
            if rec.location_id and rec.product_id:
                # Suma quantity - reserved_quantity en la ubicación (incluye hijos)
                res = Quant.read_group(
                    domain=[
                        ('location_id', 'child_of', rec.location_id.id),
                        ('product_id', '=', rec.product_id.id)
                    ],
                    fields=['quantity:sum', 'reserved_quantity:sum'],
                    groupby=[]
                )
                if res:
                    qty = (res[0].get('quantity', 0.0) or 0.0) - (res[0].get('reserved_quantity', 0.0) or 0.0)
            rec.qty_at_location = qty
