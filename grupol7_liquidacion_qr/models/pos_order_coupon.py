from odoo import models, api
import logging

_logger = logging.getLogger(__name__)


class PosOrder(models.Model):
    _inherit = 'pos.order'

    @api.model
    def _process_order(self, order, draft, existing_order):
        """Después de crear el pedido, buscar cupones en el payload del POS
        y marcar los liquidation.coupon correspondientes como 'used'.
        """
        # Lógica normal de Odoo / otros módulos
        order_rec = super()._process_order(order, draft, existing_order)

        try:
            # order viene como dict desde el POS
            data = order if isinstance(order, dict) else {}
            uid = data.get('uid') or data.get('name') or 'N/A'
            _logger.info("[G7][POS-COUPON] _process_order para uid=%s", uid)

            coupon_codes = set()

            def walk(value, path=""):
                """Recorrer recursivamente el dict/list del POS para encontrar
                cualquier campo cuyo NOMBRE contenga 'coupon' y su valor sea texto.
                """
                if isinstance(value, dict):
                    for k, v in value.items():
                        new_path = f"{path}.{k}" if path else k
                        # si el nombre del campo contiene 'coupon' y el valor es string -> posible código
                        if "coupon" in k.lower() and isinstance(v, str) and v.strip():
                            code = v.strip()
                            coupon_codes.add(code)
                            _logger.info(
                                "[G7][POS-COUPON] Código encontrado en %s: %s",
                                new_path, code
                            )
                        # seguir recorriendo estructuras anidadas
                        if isinstance(v, (dict, list)):
                            walk(v, new_path)
                elif isinstance(value, list):
                    for i, item in enumerate(value):
                        walk(item, f"{path}[{i}]")

            # Recorremos TODO el payload
            walk(data)

            _logger.info(
                "[G7][POS-COUPON] Códigos de cupón detectados en payload POS uid=%s: %s",
                uid, list(coupon_codes)
            )

            if coupon_codes:
                Coupon = self.env['liquidation.coupon']
                coupons = Coupon.search([('name', 'in', list(coupon_codes))])
                _logger.info(
                    "[G7][POS-COUPON] Cupones encontrados para códigos %s: %s",
                    list(coupon_codes),
                    coupons.mapped('name'),
                )

                new_coupons = coupons.filtered(lambda c: c.state == 'new')
                if new_coupons:
                    new_coupons.write({'state': 'used'})
                    _logger.info(
                        "[G7][POS-COUPON] Cupones marcados como usados: %s",
                        new_coupons.mapped('name'),
                    )
                else:
                    _logger.info(
                        "[G7][POS-COUPON] No hay cupones en estado 'new' para estos códigos"
                    )
            else:
                _logger.info(
                    "[G7][POS-COUPON] Ningún código de cupón detectado en el payload POS uid=%s",
                    uid,
                )

        except Exception as e:
            _logger.exception(
                "[G7][POS-COUPON] Error al actualizar estado del cupón desde POS: %s", e
            )

        return order_rec
