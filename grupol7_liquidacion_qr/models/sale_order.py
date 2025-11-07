# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError

class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    x_liq_coupon_id = fields.Many2one("liquidation.coupon", string="Cupón LIQ", copy=False)
    x_liq_code = fields.Char("Código LIQ")

    def _apply_liq_code(self, code):
        code = (code or "").strip()
        if code.startswith('LIQ/'):
            code = code[4:]
        if not code:
            return

        coupon = self.env['liquidation.coupon'].search([('name', '=', code)], limit=1)
        if not coupon:
            raise UserError(_('Código LIQ no encontrado.'))

        order = self.order_id

        # Establecer producto correcto si hace falta
        if not self.product_id or self.product_id != coupon.product_id:
            self.product_id = coupon.product_id

        # Impuestos del producto en la compañía de la orden
        product_taxes = self.product_id.taxes_id.filtered(lambda t: t.company_id == order.company_id)
        # Impuestos aplicables en la línea (posición fiscal)
        mapped_taxes = product_taxes
        if order.fiscal_position_id:
            mapped_taxes = order.fiscal_position_id.map_tax(product_taxes, self.product_id, order.partner_id)

        # Precio final del cupón incluye impuestos -> obtener precio sin impuestos para price_unit
        # Firma correcta en Odoo 16: _fix_tax_included_price_company(price, product_taxes, mapped_taxes, company)
        price_excluded = self.env['account.tax']._fix_tax_included_price_company(
            coupon.clearance_price, product_taxes, mapped_taxes, order.company_id
        )

        # Aplicar en la línea
        self.tax_id = mapped_taxes
        self.price_unit = price_excluded
        self.x_liq_coupon_id = coupon.id
        self.x_liq_code = code
        self.name = f"[LIQ-{coupon.damage_grade}] {self.product_id.display_name}"

    @api.onchange('x_liq_code')
    def _onchange_x_liq_code(self):
        for line in self:
            if line.x_liq_code:
                line._apply_liq_code(line.x_liq_code)

    # Soporte para el campo creado con Studio (x_studio_liq_code)
    @api.onchange('x_studio_liq_code')
    def _onchange_x_studio_liq_code(self):
        for line in self:
            code = getattr(line, 'x_studio_liq_code', False)
            if code:
                line._apply_liq_code(code)

class SaleOrder(models.Model):
    _inherit = "sale.order"

    def action_confirm(self):
        res = super().action_confirm()
        for line in self.order_line:
            if line.x_liq_coupon_id and line.x_liq_coupon_id.state == 'new':
                line.x_liq_coupon_id.write({
                    'state': 'redeemed',
                    'sale_order_id': self.id,
                    'sale_order_line_id': line.id,
                })
        return res
