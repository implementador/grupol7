from odoo import api, models, _
from odoo.exceptions import UserError


class PosOrderLiquidationCoupon(models.Model):
    _inherit = 'pos.order'

    # ---------------------------------------------------------------------
    # CREACIÓN Y PROCESADO DE LA ORDEN
    # ---------------------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        """Al crear la orden, ligamos cupones con pedido y líneas."""
        orders = super().create(vals_list)
        orders._g7_link_liquidation_coupons(stage='create')
        return orders

    def action_pos_order_done(self):
        """
        Cuando Odoo procesa la orden (crea picking, movimientos, etc.),
        completamos la trazabilidad con picking y movimiento.
        """
        res = super().action_pos_order_done()
        self._g7_link_liquidation_coupons(stage='done')
        return res

    def action_pos_order_paid(self):
        """
        Cuando el ticket se marca como PAGADO, marcamos los cupones
        ligados a este pedido como 'used'.
        """
        res = super().action_pos_order_paid()
        self._g7_mark_coupons_used()
        return res

    # ---------------------------------------------------------------------
    # HELPERS DE CUPONES
    # ---------------------------------------------------------------------

    def _g7_link_liquidation_coupons(self, stage='create'):
        """
        Enlaza cupones de liquidación con el ticket de POS.

        stage='create' -> enlaza pedido + línea
        stage='done'   -> completa picking + stock.move (salida de inventario)
        """
        Coupon = self.env['liquidation.coupon'].sudo()
        name_map = Coupon._g7_traceability_field_names()

        pos_order_field = name_map.get('pos_order')
        pos_line_field = name_map.get('pos_order_line')
        picking_field = name_map.get('picking')
        move_field = name_map.get('move')

        # Detectar el campo Many2many hacia pos.config (PdV permitidos),
        # sin depender del nombre técnico (por si viene de Studio).
        allowed_pos_field = False
        for fname, field in Coupon._fields.items():
            if getattr(field, 'type', '') == 'many2many' and \
               getattr(field, 'comodel_name', '') == 'pos.config':
                allowed_pos_field = fname
                break

        for order in self:
            current_config = order.session_id.config_id  # pos.config actual

            for line in order.lines:
                if not line.product_id:
                    continue

                coupon = False

                # 1) Si ya hay un cupón ligado explícitamente a esta línea, usarlo
                if pos_line_field:
                    coupon = Coupon.search([(pos_line_field, '=', line.id)], limit=1)

                # 2) Si no, buscar por producto + precio, sólo cupones no usados
                if not coupon:
                    domain = [
                        ('product_id', '=', line.product_id.id),
                        ('clearance_price', '=', line.price_unit),
                    ]

                    if 'state' in Coupon._fields:
                        # no tomar cupones ya usados
                        domain.append(('state', '!=', 'used'))

                    if pos_order_field:
                        # sólo cupones que aún no estén ligados a otro ticket
                        domain.append((pos_order_field, '=', False))

                    # Filtro por PdV permitido (si existe el campo y tenemos PdV actual)
                    if allowed_pos_field and current_config:
                        domain.extend([
                            '|',
                            (allowed_pos_field, '=', False),            # sin restricción
                            (allowed_pos_field, 'in', current_config.id),
                        ])

                    coupon = Coupon.search(domain, limit=1, order='write_date desc')

                if not coupon:
                    continue

                # -----------------------------------------------------------------
                # VALIDACIÓN FUERTE DE PdV:
                # Si el cupón tiene PdV limitados y el PdV actual NO está en esa
                # lista, BLOQUEAMOS el uso del cupón.
                # -----------------------------------------------------------------
                if stage == 'create' and allowed_pos_field and current_config:
                    allowed_pdvs = coupon[allowed_pos_field]
                    if allowed_pdvs and current_config not in allowed_pdvs:
                        allowed_names = ", ".join(allowed_pdvs.mapped('display_name'))
                        raise UserError(_(
                            "El cupón %(code)s sólo se puede usar en los PdV: %(pdvs)s.\n"
                            "PdV actual: %(current)s"
                        ) % {
                            'code': coupon.display_name,
                            'pdvs': allowed_names,
                            'current': current_config.display_name,
                        })

                vals = {}

                # En la creación ligamos pedido y línea
                if stage == 'create':
                    if pos_order_field:
                        vals[pos_order_field] = order.id
                    if pos_line_field:
                        vals[pos_line_field] = line.id

                # En 'done' completamos picking y movimiento
                if stage == 'done' and (picking_field or move_field):
                    picking = order.picking_ids[:1]
                    if picking_field and picking:
                        vals[picking_field] = picking.id
                    if move_field and picking:
                        move = picking.move_ids_without_package.filtered(
                            lambda m: m.product_id.id == line.product_id.id
                        )[:1]
                        if move:
                            vals[move_field] = move.id

                if vals:
                    coupon.write(vals)

    def _g7_mark_coupons_used(self):
        """Marca como 'used' los cupones ligados a estos pedidos de POS."""
        Coupon = self.env['liquidation.coupon'].sudo()
        name_map = Coupon._g7_traceability_field_names()
        pos_order_field = name_map.get('pos_order')

        if not pos_order_field:
            return

        # Buscar todos los cupones que tengan ligado alguno de estos pedidos
        domain = [(pos_order_field, 'in', self.ids)]
        if 'state' in Coupon._fields:
            domain.append(('state', '!=', 'used'))

        coupons = Coupon.search(domain)
        for coupon in coupons:
            if 'state' in Coupon._fields:
                coupon.write({'state': 'used'})
