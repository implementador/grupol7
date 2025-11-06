# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class SaleOrderLine(models.Model):
_inherit = "sale.order.line"


x_liq_coupon_id = fields.Many2one("liquidation.coupon", string="Cupón LIQ", copy=False)
x_liq_code = fields.Char("Código LIQ", help="Pega o escanea el código de cupón (sin prefijo LIQ/)")


@api.onchange('x_liq_code')
def _onchange_x_liq_code(self):
if not self.x_liq_code:
return
coupon = self.env['liquidation.coupon'].search([('name', '=', self.x_liq_code)], limit=1)
if not coupon:
raise UserError(_('Código LIQ no encontrado.'))
order = self.order_id
coupon._check_valid(company=order.company_id, product=self.product_id or coupon.product_id)
# Ajustar producto si vacío o distinto
if not self.product_id or self.product_id != coupon.product_id:
self.product_id = coupon.product_id
self.price_unit = coupon.clearance_price
self.x_liq_coupon_id = coupon.id
self.name = f"[LIQ-{coupon.damage_grade}] {self.product_id.display_name}"


def _prepare_invoice_line(self, **optional_values):
vals = super()._prepare_invoice_line(**optional_values)
if self.x_liq_coupon_id:
vals['name'] = (vals.get('name') or '') + f"\n(Cupón LIQ: {self.x_liq_coupon_id.name})"
return vals


class SaleOrder(models.Model):
_inherit = "sale.order"


def action_confirm(self):
res = super().action_confirm()
# marcar cupones como canjeados
for line in self.order_line:
if line.x_liq_coupon_id and line.x_liq_coupon_id.state == 'new':
line.x_liq_coupon_id.write({
'state': 'redeemed',
'sale_order_id': self.id,
'sale_order_line_id': line.id,
})
return res
