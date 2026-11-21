from odoo import models, fields

class LiquidationCoupon(models.Model):
    _inherit = 'liquidation.coupon'

    # Campo almacenado en BD (creará columna al actualizar el módulo)
    print_count = fields.Integer(string="Reimpresiones", default=0)
