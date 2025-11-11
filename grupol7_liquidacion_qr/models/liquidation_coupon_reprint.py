# -*- coding: utf-8 -*-
from odoo import api, fields, models

class LiquidationCoupon(models.Model):
    _inherit = 'liquidation.coupon'

    # --- Nuevos campos de reimpresión ---
    reprint_count = fields.Integer(
        string='Reimpresiones', default=0, readonly=True
    )
    last_printed_by = fields.Many2one(
        'res.users', string='Última impresión por', readonly=True
    )
    last_printed_at = fields.Datetime(
        string='Fecha última impresión', readonly=True
    )

    # --- Botón: imprime QR y cuenta reimpresión ---
    def action_print_qr(self):
        self.ensure_one()
        # Acción del reporte QR ya existente en tu módulo
        report_action = self.env.ref(
            'grupol7_liquidacion_qr.action_liq_coupon_print_label_qr'
        )
        # Actualiza contador y huella
        self.sudo().write({
            'reprint_count': (self.reprint_count or 0) + 1,
            'last_printed_by': self.env.user.id,
            'last_printed_at': fields.Datetime.now(),
        })
        # Lanza el PDF del reporte
        return report_action.report_action(self)
