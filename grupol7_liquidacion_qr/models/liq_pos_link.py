# -*- coding: utf-8 -*-

from odoo import models, api
import logging

_logger = logging.getLogger(__name__)


class PosOrderLine(models.Model):
    _inherit = 'pos.order.line'

    def _liq_link_coupons_on_line(self):
        """Intenta ligar la línea de PdV con un cupón de liquidación
        y marcarlo como usado.
        """
        Coupon = self.env['liquidation.coupon']

        for line in self:
            # 1) Primero intentamos con campos M2O que puedan existir
            coupon = (
                getattr(line, 'liq_coupon_id', False)
                or getattr(line, 'liquidation_coupon_id', False)
                or getattr(line, 'coupon_id', False)
            )

            # 2) Si no hay M2O, intentamos con un código de cupón en char
            if not coupon:
                code_text = (
                    getattr(line, 'liq_coupon_code', False)
                    or getattr(line, 'coupon_code', False)
                    or getattr(line, 'coupon', False)
                )
                if code_text:
                    coupon = Coupon.search([
                        ('name', '=', code_text),
                    ], limit=1)

            if not coupon:
                continue

            # Si el cupón ya está ligado a otra línea distinta, no lo tocamos
            if coupon.pos_order_line_id and coupon.pos_order_line_id != line:
                _logger.info(
                    "[LiqCoupon] Cupón %s ya ligado a línea POS %s, se ignora línea %s",
                    coupon.name, coupon.pos_order_line_id.id, line.id,
                )
                continue

            vals = {
                'pos_order_id': line.order_id.id,
                'pos_order_line_id': line.id,
            }
            if coupon.state == 'new':
                vals['state'] = 'used'

            coupon.sudo().write(vals)
            _logger.info(
                "[LiqCoupon] Cupón %s actualizado: %s",
                coupon.name, vals,
            )

    @api.model
    def create(self, vals):
        line = super().create(vals)
        line._liq_link_coupons_on_line()
        return line

    def write(self, vals):
        res = super().write(vals)
        self._liq_link_coupons_on_line()
        return res
