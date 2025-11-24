from odoo import api, models
from odoo.exceptions import ValidationError


class PosOrderLiquidationCoupon(models.Model):
    _inherit = 'pos.order'

    # -------------------------------------------------------------------------
    # CREACIÓN Y PROCESADO DE LA ORDEN
    # -------------------------------------------------------------------------

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
        ligados a este pedido como 'used' y validamos PdV permitido.
        """
        res = super().action_pos_order_paid()
        self._g7_mark_coupons_used()
        return res

    # -------------------------------------------------------------------------
    # HELPERS DE CUPONES
    # -------------------------------------------------------------------------

    def _g7_link_liquidation_coupons(self, stage='create'):
        """
        Enlaza cupones de liquidación con el ticket de POS.

        stage='create' -> enlaza pos.order + pos.order_line
        stage='done'   -> completa picking + stock.move (salida de inventario)
        """
        Coupon = self.env['liquidation.coupon'].sudo()

        # Usamos los nombres de campo reales del modelo
        name_map = Coupon._fields
        pos_order_field = name_map.get('pos_order')
        pos_line_field = name_map.get('pos_order_line')
        picking_field = name_map.get('picking')
        move_field = name_map.get('move')

        for order in self:
            for line in order.lines:
                if not line.product_id:
                    continue

                coupon = False

                # 1) Si ya hay un cupón ligado explícitamente a esta línea, usarlo
                if pos_line_field:
                    coupon = Coupon.search(
                        [(pos_line_field.name, '=', line.id)],
                        limit=1,
                    )

                # 2) Si no, buscar por producto + precio, sólo cupones no usados
                if not coupon:
                    domain = [
                        ('product_id', '=', line.product_id.id),
                        ('clearance_price', '=', line.line_price_unit),
                    ]
                    if 'state' in Coupon._fields:
                        domain.append(('state', '!=', 'used'))
                    if pos_order_field:
                        # Que aún no estén ligados a un pedido de POS
                        domain.append((pos_order_field.name, '=', False))

                    coupon = Coupon.search(domain, limit=1, order='write_date desc')

                if not coupon:
                    continue

                vals = {}

                # En la creación ligamos pedido y línea
                if stage == 'create':
                    if pos_order_field:
                        vals[pos_order_field.name] = order.id
                    if pos_line_field:
                        vals[pos_line_field.name] = line.id

                # En 'done' completamos picking y movimiento
                if stage == 'done' and (picking_field or move_field):
                    picking = order.picking_ids[:1]
                    if picking_field and picking:
                        vals[picking_field.name] = picking.id

                    if picking and move_field:
                        move = picking.move_ids_without_package.filtered(
                            lambda m: m.product_id.id == line.product_id.id
                        )[:1]
                        if move:
                            vals[move_field.name] = move.id

                if vals:
                    coupon.write(vals)

    def _g7_mark_coupons_used(self):
        """
        Marca como 'used' los cupones ligados a estos pedidos de POS.

        Además valida que el cupón sólo pueda usarse en los PdV permitidos
        (campo Many2many hacia pos.config, por ejemplo 'allowed_pos_ids').
        """
        Coupon = self.env['liquidation.coupon'].sudo()

        name_map = Coupon._fields
        pos_order_field = name_map.get('pos_order')
        if not pos_order_field:
            # Si no existe el campo de enlace con pos.order, salimos
            return

        # Detectar el campo de PdV permitidos (Many2many a pos.config)
        allowed_field_name = None
        for fname in (
            'allowed_pos_ids',
            'allowed_pos_config_ids',
            'pos_config_ids',
            'pos_ids',
            'pdv_ids',
        ):
            if fname in Coupon._fields:
                allowed_field_name = fname
                break

        # Buscar todos los cupones ligados a estos pedidos y no usados
        domain = [(pos_order_field.name, 'in', self.ids)]
        if 'state' in Coupon._fields:
            domain.append(('state', '!=', 'used'))

        coupons = Coupon.search(domain)

        for coupon in coupons:
            # Validar PdV permitido, si el campo existe
            if allowed_field_name:
                allowed_pos = coupon[allowed_field_name]          # many2many a pos.config
                order = coupon[pos_order_field.name]              # pedido de POS ligado

                if order and allowed_pos:
                    config = order.session_id.config_id
                    if config and config not in allowed_pos:
                        # Si el PdV del ticket no está entre los permitidos, NO se deja pagar
                        raise ValidationError(
                            "El cupón %s no está permitido en el PdV '%s'."
                            % (coupon.name, config.display_name)
                        )

            # Si pasa la validación (o no hay restricción), marcamos el cupón como usado
            if 'state' in Coupon._fields:
                coupon.write({'state': 'used'})
            else:
                coupon.write({'state': 'used'})
