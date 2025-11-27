# -*- coding: utf-8 -*-
import logging
from odoo import api, models

_logger = logging.getLogger(__name__)


class PosOrderLine(models.Model):
    _inherit = 'pos.order.line'

    @api.model
    def create(self, vals_list):
        """
        Cuando se crea una línea de POS que tiene un cupón de liquidación,
        marcamos el cupón como usado y guardamos la trazabilidad
        (pedido y línea de POS).
        """

        # Odoo permite create(dict) o create([dict, dict, ...])
        single = False
        if isinstance(vals_list, dict):
            vals_list = [vals_list]
            single = True

        # Crear las líneas normalmente
        lines = super(PosOrderLine, self).create(vals_list)

        Coupon = self.env['liquidation.coupon'].sudo()

        for line, vals in zip(lines, vals_list):
            # El campo que viene desde el POS (ajusta si el tuyo se llama diferente)
            coupon_id = (
                vals.get('liquidation_coupon_id')
                or vals.get('liq_coupon_id')
                or vals.get('coupon_id')
            )

            if not coupon_id:
                continue

            coupon = Coupon.browse(coupon_id)
            if not coupon.exists():
                _logger.warning("[LQ POS] Cupón ID %s no existe", coupon_id)
                continue

            # Actualizamos estado y trazabilidad
            coupon.write({
                'state': 'used',
                'pos_order_id': line.order_id.id,
                'pos_order_line_id': line.id,
            })

            _logger.info(
                "[LQ POS] Cupón %s marcado como usado. POS Order %s, línea %s",
                coupon.display_name,
                line.order_id.name,
                line.id,
            )

        # Respetar la firma de create
        return lines[0] if single else lines
