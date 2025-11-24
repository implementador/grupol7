from odoo import models

class LiquidationCouponQrReport(models.Model):
    _inherit = 'liquidation.coupon'

    def action_print_qr(self):
        """Usar el nuevo reporte QR (layout corregido y precio con IVA)."""
        self.ensure_one()
        return self.env.ref(
            'grupol7_liquidacion_qr.action_liq_coupon_qr_label2'
        ).report_action(self)
