# -*- coding: utf-8 -*-
lot_id = fields.Many2one("stock.lot", string="N. serie/lote")
damage_grade = fields.Selection([
("A", "Rayón leve"),
("B", "Golpe"),
("C", "Detalle serio"),
], string="Daño", required=True)
clearance_price = fields.Monetary("Precio liquidación", required=True)
currency_id = fields.Many2one(related="company_id.currency_id", store=True, readonly=True)


pos_allowed_ids = fields.Many2many("pos.config", string="PdV permitidos")
expiration_date = fields.Date("Vence el")
state = fields.Selection([
("new", "Nuevo"),
("redeemed", "Canjeado"),
("cancelled", "Cancelado"),
("expired", "Expirado"),
], default="new", required=True, index=True)


sale_order_id = fields.Many2one("sale.order", readonly=True)
sale_order_line_id = fields.Many2one("sale.order.line", readonly=True)
pos_order_id = fields.Many2one("pos.order", readonly=True)
pos_order_line_id = fields.Many2one("pos.order.line", readonly=True)


company_id = fields.Many2one("res.company", required=True, default=lambda s: s.env.company)
notes = fields.Char()


_sql_constraints = [
("name_uniq", "unique(name)", "El código de cupón debe ser único."),
]


def _check_valid(self, pos_config=None, company=None, product=None):
self.ensure_one()
if self.state != "new":
raise UserError(_("Cupón ya utilizado o inválido."))
if company and self.company_id != company:
raise UserError(_("Cupón de otra compañía."))
if self.expiration_date and fields.Date.today() > self.expiration_date:
raise UserError(_("Cupón expirado."))
if pos_config and self.pos_allowed_ids and pos_config not in self.pos_allowed_ids:
raise UserError(_("Este PdV no está autorizado para este cupón."))
if product and self.product_id != product:
raise UserError(_("Cupón no corresponde al producto."))
return True


@api.model
def pos_validate_coupon(self, code, pos_config_id):
coupon = self.search([("name", "=", code)], limit=1)
if not coupon:
raise UserError(_("Código no encontrado."))
pos_config = self.env["pos.config"].browse(pos_config_id)
coupon._check_valid(pos_config=pos_config, company=pos_config.company_id)
return {
"product_id": coupon.product_id.id,
"price": coupon.clearance_price,
"name": f"[LIQ-{coupon.damage_grade}] {coupon.product_id.display_name}",
"coupon_id": coupon.id,
}


@api.model
def pos_redeem_coupon(self, code, pos_order_id, pos_order_line_id):
coupon = self.search([("name", "=", code)], limit=1)
if not coupon:
raise UserError(_("Código no encontrado."))
if coupon.state != "new":
raise UserError(_("Cupón ya utilizado."))
order = self.env["pos.order"].browse(pos_order_id)
coupon._check_valid(pos_config=order.config_id, company=order.company_id)
coupon.write({
"state": "redeemed",
"pos_order_id": order.id,
"pos_order_line_id": pos_order_line_id,
})
return True
