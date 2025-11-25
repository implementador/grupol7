# -*- coding: utf-8 -*-
from odoo import api, models
import logging

_logger = logging.getLogger(__name__)


class PosOrder(models.Model):
    _inherit = "pos.order"

    def _liq_get_coupon_field_name(self):
        """
        Detecta dinámicamente el Many2one que apunta a liquidation.coupon
        en pos.order.line, sin importar cómo se llame el campo.
        """
        PosLine = self.env["pos.order.line"]
        for fname, field in PosLine._fields.items():
            if getattr(field, "comodel_name", None) == "liquidation.coupon":
                return fname
        return None

    def _liq_sync_coupons_from_lines(self):
        """
        Para cada línea de PdV que tenga cupón de liquidación:
        - llena pos_order_id y pos_order_line_id en el cupón
        - cambia el estado de 'new' a 'used' (solo si está en new)
        """
        coupon_field = self._liq_get_coupon_field_name()
        if not coupon_field:
            _logger.info(
                "[LiqCoupon] No se encontró campo Many2one a 'liquidation.coupon' en pos.order.line"
            )
            return

        for order in self:
            for line in order.lines:
                coupon = getattr(line, coupon_field, False)
                if not coupon:
                    continue

                for c in coupon:
                    vals = {}
                    # Solo cambiamos a usado si está nuevo
                    if c.state == "new":
                        vals["state"] = "used"
                    # Guardamos trazabilidad solo si aún no está puesta
                    if not c.pos_order_id:
                        vals["pos_order_id"] = order.id
                    if not c.pos_order_line_id:
                        vals["pos_order_line_id"] = line.id

                    if vals:
                        c.write(vals)
                        _logger.info(
                            "[LiqCoupon] Cupón %s marcado como usado por POS %s (línea %s) usando campo %s",
                            c.name,
                            order.name,
                            line.id,
                            coupon_field,
                        )

    @api.model
    def create(self, vals):
        """
        Cuando se crea una orden de PdV (incluyendo las que vienen del POS),
        sincronizamos los cupones de liquidación.
        """
        orders = super().create(vals)
        try:
            orders._liq_sync_coupons_from_lines()
        except Exception:
            _logger.exception(
                "[LiqCoupon] Error al sincronizar cupones de liquidación desde POS"
            )
        return orders
