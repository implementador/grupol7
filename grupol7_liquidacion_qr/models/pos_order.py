# -*- coding: utf-8 -*-
from odoo import api, fields, models


class PosOrder(models.Model):
_inherit = "pos.order"


def _order_line_fields(self, line, pos_session_id=None):
vals = super()._order_line_fields(line, pos_session_id=pos_session_id)
# line[2] es el dict de valores que llega del frontend
extras = (line[2] or {}).get('extras') or {}
if extras.get('coupon_id'):
vals[2]['x_liq_coupon_id'] = extras['coupon_id']
# asegurar precio unitario (evitar que el POS lo reevalúe)
if 'price_unit' in line[2]:
vals[2]['price_unit'] = line[2]['price_unit']
return vals


class PosOrderLine(models.Model):
_inherit = "pos.order.line"


x_liq_coupon_id = fields.Many2one("liquidation.coupon", string="Cupón LIQ", readonly=True)


@api.model
def create(self, vals_list):
records = super().create(vals_list)
for line in records:
if line.x_liq_coupon_id:
line.x_liq_coupon_id.pos_redeem_coupon(line.x_liq_coupon_id.name, line.order_id.id, line.id)
return records
