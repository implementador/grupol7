# -*- coding: utf-8 -*-
from odoo import api, models
import logging

_logger = logging.getLogger(__name__)


class PosOrder(models.Model):
    _inherit = "pos.order"

    # Detectar el campo Many2one en pos.order.line que apunta a liquidation.coupon
    def _liq_get_coupon_field_name(self):
        PosLine = self.env["pos.order.line"]
        for fname, field in PosLine._fields.items():
            if getattr(field, "comodel_name", None) == "liquidation.coupon":
                return fname
        return None

    # Sincronizar cupones: poner trazabilidad y marcar como "used"
    def _liq_sync_coupons_from_lines(self):
        coupon_field = self._liq_get_coupon_field_name()
        if not coupon_field:
            _logger.warning(
                "[LiqCoupon] No se encontró campo Many2one a 'liquidation.coupon' en pos.order.line"
            )
            return

        for order in self:
            for line in order.lines:
                coupon = getattr(line, coupon_field, False)
                if not coupon:
                    continue

                # Puede ser recordset (por si es Many2many)
                for c in coupon:
                    vals = {}
                    # Solo cambiamos a usado si está en 'new'
                    if getattr(c, "state", False) == "new":
                        vals["state"] = "used"
                    # Llenar trazabilidad si está vacía
                    if not getattr(c, "pos_order_id", False):
                        vals["pos_order_id"] = order.id
                    if not getattr(c, "pos_order_line_id", False):
                        vals["pos_order_line_id"] = line.id

                    if vals:
                        c.write(vals)
                        _logger.info(
                            "[LiqCoupon] Cupón %s actualizado: %s",
                            c.name,
                            vals,
                        )

    @api.model
    def create_from_ui(self, orders, draft=False):
        # Este método SIEMPRE se ejecuta cuando el PdV manda las órdenes
        _logger.info(
            "[LiqCoupon] create_from_ui llamado con %s órdenes", len(orders)
        )
        res = super().create_from_ui(orders, draft=draft)

        # res suele ser una lista de dicts con 'id'
        order_ids = [r.get("id") for r in res if r.get("id")]
        if order_ids:
            self.browse(order_ids)._liq_sync_coupons_from_lines()
        else:
            _logger.info("[LiqCoupon] create_from_ui sin order_ids en resultado: %s", res)

        return res
