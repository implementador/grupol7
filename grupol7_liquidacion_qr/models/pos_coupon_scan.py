# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError

class LiquidationCoupon(models.Model):
    _inherit = 'liquidation.coupon'

    @api.model
    def pos_scan_coupon(self, code, pos_config_id=False):
        """Valida un cupón desde el POS y devuelve product_id y price.
        Acepta códigos con o sin prefijo 'LIQ/'.
        """
        code = (code or '').strip()
        if code.upper().startswith('LIQ/'):
            code = code[4:]

        Coupon = self.env['liquidation.coupon'].sudo()
        coupon = Coupon.search([('name', '=', code)], limit=1)
        if not coupon:
            return {'ok': False, 'message': _('Cupón no encontrado.')}

        # Estado/uso
        if coupon.state not in ('new', 'unused', 'draft'):
            return {'ok': False, 'message': _('El cupón ya fue canjeado o no está activo.')}

        # Validar POS permitido si está configurado
        if pos_config_id and coupon.pos_allowed_ids:
            if pos_config_id not in coupon.pos_allowed_ids.ids:
                return {'ok': False, 'message': _('Este cupón no es válido en este Punto de Venta.')}

        if not coupon.product_id:
            return {'ok': False, 'message': _('El cupón no tiene producto asociado.')}

        price = coupon.clearance_price or 0.0
        return {
            'ok': True,
            'product_id': coupon.product_id.id,
            'price': price,
            'code': coupon.name,
        }
