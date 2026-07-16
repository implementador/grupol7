from odoo import models, fields

class LiquidationCouponPrint(models.Model):
    _inherit = 'liquidation.coupon'

    print_count = fields.Integer('Veces impreso', default=0, readonly=True)
    last_printed_by = fields.Many2one('res.users', 'Último que imprimió', readonly=True)
    last_printed_at = fields.Datetime('Última impresión', readonly=True)

    def action_print_qr_205x105_double(self):
        # Incrementa contador antes de renderizar para que la etiqueta muestre "Reimpresión #1" a partir de la segunda
        for rec in self:
            rec.write({
                'print_count': (rec.print_count or 0) + 1,
                'last_printed_by': self.env.user.id,
                'last_printed_at': fields.Datetime.now(),
            })
        # Lanza el reporte QR 205x105 (ajusta el xml_id si el tuyo difiere)
        return self.env.ref(
            'grupol7_liquidacion_qr.action_liq_coupon_print_label_qr_205x105_double'
        ).report_action(self)
