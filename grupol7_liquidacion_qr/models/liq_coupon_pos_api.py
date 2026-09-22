# -*- coding: utf-8 -*-
from odoo import models, _
class LiquidationCoupon(models.Model):
    _inherit = 'liquidation.coupon'

    def pos_apply_coupon(self, code, pos_config_id):
        self = self.sudo()
        c = self.search([('code', '=', code)], limit=1)
        if not c:
            return {'error': _('Cupón no encontrado')}
        if getattr(c, 'pos_order_line_id', False) or getattr(c, 'sale_order_line_id', False):
            return {'error': _('El cupón ya fue utilizado')}
        if c.company_id and self.env.company != c.company_id:
            return {'error': _('El cupón pertenece a otra compañía')}
        if getattr(c, 'allowed_pos_ids', False) and pos_config_id not in c.allowed_pos_ids.ids:
            return {'error': _('Cupón no válido en este Punto de Venta')}
        if not c.product_id:
            return {'error': _('El cupón no tiene producto asociado')}
        price = c.clearance_price or 0.0
        if price <= 0.0:
            return {'error': _('El cupón no tiene precio de liquidación')}
        return {'product_id': c.product_id.id, 'price': price}
