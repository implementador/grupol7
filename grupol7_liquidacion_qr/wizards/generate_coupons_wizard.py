# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class LiqGenerateCouponsWizard(models.TransientModel):
_name = 'liq.generate.coupons.wizard'
_description = 'Generar cupones de liquidación'


product_id = fields.Many2one('product.product', string='Producto')
product_tmpl_id = fields.Many2one('product.template', string='Producto (plantilla)')
quantity = fields.Integer('Cantidad', default=1)
damage_grade = fields.Selection([
("A", "Rayón leve"),
("B", "Golpe"),
("C", "Detalle serio"),
], required=True)
clearance_price = fields.Monetary('Precio liquidación', required=True)
currency_id = fields.Many2one('res.currency', default=lambda s: s.env.company.currency_id.id)
expiration_date = fields.Date('Vigencia (opcional)')
pos_allowed_ids = fields.Many2many('pos.config', string='PdV permitidos')


def action_generate(self):
self.ensure_one()
if not self.product_id and not self.product_tmpl_id:
raise UserError(_('Selecciona un producto o una plantilla.'))
products = self.product_id or self.product_tmpl_id.product_variant_id
coupons = self.env['liquidation.coupon']
for _i in range(self.quantity):
coupons |= coupons.create({
'product_id': products.id,
'damage_grade': self.damage_grade,
'clearance_price': self.clearance_price,
'expiration_date': self.expiration_date,
'pos_allowed_ids': [(6, 0, self.pos_allowed_ids.ids)],
'company_id': self.env.company.id,
})
action = self.env.ref('grupol7_liquidacion_qr.action_liq_coupon').read()[0]
action['domain'] = [('id', 'in', coupons.ids)]
return action
