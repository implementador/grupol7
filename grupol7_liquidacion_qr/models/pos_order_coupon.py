from odoo import models
import logging

_logger = logging.getLogger(__name__)


class PosOrder(models.Model):
    _inherit = 'pos.order'

    def _process_order(self, order, draft, existing_order):
        # Lógica normal de Odoo primero
        order_rec = super()._process_order(order, draft, existing_order)

        for rec in order_rec:
            line_model = self.env['pos.order.line']

            # --- Detectar campos coupon en las LÍNEAS ---
            m2o_coupon_fields = []
            char_coupon_fields = []

            for fname, field in line_model._fields.items():
                ftype = getattr(field, 'type', None)
                if ftype == 'many2one' and getattr(field, 'comodel_name', None) == 'liquidation.coupon':
                    m2o_coupon_fields.append(fname)
                elif ftype == 'char' and 'coupon' in fname.lower():
                    char_coupon_fields.append(fname)

            # --- Detectar campos coupon en el PEDIDO ---
            order_char_coupon_fields = []
            for fname, field in self._fields.items():
                if getattr(field, 'type', None) == 'char' and 'coupon' in fname.lower():
                    order_char_coupon_fields.append(fname)

            _logger.info(
                "[G7][POS-COUPON] Campos en pos.order.line -> M2O: %s, CHAR: %s ; "
                "Campos CHAR en pos.order: %s",
                m2o_coupon_fields,
                char_coupon_fields,
                order_char_coupon_fields,
            )

            coupon_ids = set()
            coupon_codes = set()

            # --- Recorrer líneas del pedido ---
            for line in rec.lines:
                # Many2one directos a liquidation.coupon
                for fname in m2o_coupon_fields:
                    coupon = getattr(line, fname, False)
                    if coupon:
                        coupon_ids.add(coupon.id)

                # Códigos de cupón guardados como texto
                for fname in char_coupon_fields:
                    val = getattr(line, fname, False)
                    if isinstance(val, str) and val.strip():
                        coupon_codes.add(val.strip())

            # --- Revisar también campos CHAR tipo coupon en el pedido ---
            for fname in order_char_coupon_fields:
                val = getattr(rec, fname, False)
                if isinstance(val, str) and val.strip():
                    coupon_codes.add(val.strip())

            _logger.info(
                "[G7][POS-COUPON] Pedido %s -> coupon_ids=%s, coupon_codes=%s",
                rec.name,
                list(coupon_ids),
                list(coupon_codes),
            )

            # --- Buscar cupones por ID y por código (name) ---
            Coupon = self.env['liquidation.coupon']
            coupons = Coupon.browse(list(coupon_ids))
            if coupon_codes:
                coupons |= Coupon.search([('name', 'in', list(coupon_codes))])

            if not coupons:
                _logger.info("[G7][POS-COUPON] Pedido %s sin cupones detectados", rec.name)
                continue

            new_coupons = coupons.filtered(lambda c: c.state == 'new')
            _logger.info(
                "[G7][POS-COUPON] Pedido %s -> cupones detectados=%s, nuevos=%s",
                rec.name,
                coupons.mapped('name'),
                new_coupons.mapped('name'),
            )

            if new_coupons:
                new_coupons.write({'state': 'used'})
                _logger.info(
                    "[G7][POS-COUPON] Pedido %s -> cupones marcados como usados=%s",
                    rec.name,
                    new_coupons.mapped('name'),
                )

        return order_rec
