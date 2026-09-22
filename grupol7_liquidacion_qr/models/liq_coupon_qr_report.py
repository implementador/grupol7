from odoo import models
import re


class LiquidationCoupon(models.Model):
    _inherit = "liquidation.coupon"

    def action_print_qr(self):
        self.ensure_one()
        action = self.env.ref("grupol7_liquidacion_qr.action_liq_coupon_qr_label2")
        res = action.report_action(self)

        # Nombre del archivo: Cupon_<codigo>.pdf solo con letras/números/guiones
        base = "Cupon_%s" % (self.name or "")
        safe = re.sub(r"[^A-Za-z0-9_-]+", "_", base)
        ctx = dict(res.get("context") or {})
        ctx["download_filename"] = safe
        res["context"] = ctx
        return res
