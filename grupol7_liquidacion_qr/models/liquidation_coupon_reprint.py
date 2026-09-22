from odoo import api, fields, models

class LiquidationCoupon(models.Model):
    _inherit = 'liquidation.coupon'

    reprint_count = fields.Integer(string='Reimpresiones', default=0, readonly=True)
    last_printed_at = fields.Datetime(string='Última impresión', readonly=True)
    last_printed_by_id = fields.Many2one('res.users', string='Impreso por', readonly=True)

    def action_print_qr(self):
        """Suma reimpresión y devuelve el reporte QR 205x105 (x2)."""
        now = fields.Datetime.now()
        uid = self.env.user.id
        for rec in self.sudo():
            rec.write({
                'reprint_count': (rec.reprint_count or 0) + 1,
                'last_printed_at': now,
                'last_printed_by_id': uid,
            })
        action = self.env.ref('grupol7_liquidacion_qr.action_liq_coupon_print_label_qr_205x105_double')
        return action.report_action(self)
