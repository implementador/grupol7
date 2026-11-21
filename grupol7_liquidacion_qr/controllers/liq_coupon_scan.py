# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request

class LiqCouponScan(http.Controller):
    @http.route('/grupol7/liq/coupon_scan', type='json', auth='user', methods=['POST'])
    def coupon_scan(self, code=None):
        if not code:
            return {'error': 'no_code'}
        # Aceptar con o sin prefijo "LIQ/"
        name = code.split('/', 1)[1] if '/' in code else code

        Coupon = request.env['liquidation.coupon'].sudo()
        c = Coupon.search([('name', '=', name)], limit=1)
        if not c:
            return {'error': 'not_found'}
        if c.state == 'redeemed':
            return {'error': 'redeemed'}

        return {
            'id': c.id,
            'product_id': c.product_id.id,
            'clearance_price': c.clearance_price or 0.0,
            'name': c.name,
        }
