from odoo import models

class LiquidationCoupon(models.Model):
    _inherit = 'liquidation.coupon'

    def action_mark_used_from_pos(self):
        """Marcar cupones como usados cuando se consumen en el PdV."""
        for coupon in self:
            if coupon.state == 'new':
                coupon.state = 'used'
