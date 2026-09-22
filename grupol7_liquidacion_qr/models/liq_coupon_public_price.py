from odoo import models, fields, api


class LiquidationCoupon(models.Model):
    _inherit = "liquidation.coupon"

    # Precio de liquidación con IVA (16%)
    public_clearance_price = fields.Monetary(
        string="Precio liquidación (con IVA)",
        currency_field="currency_id",
        compute="_compute_public_clearance_price",
        store=True,
    )

    @api.depends("clearance_price")
    def _compute_public_clearance_price(self):
        TAX_FACTOR = 1.16  # 16% IVA
        for rec in self:
            base = rec.clearance_price or 0.0
            rec.public_clearance_price = base * TAX_FACTOR
