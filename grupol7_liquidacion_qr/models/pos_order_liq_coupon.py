# -*- coding: utf-8 -*-

from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)


class PosOrder(models.Model):
    _inherit = 'pos.order'

    @api.model
    def create_from_ui(self, orders, draft=False):
        """
        Después de crear las órdenes desde el POS,
        marcamos los cupones de liquidación como usados
        y generamos la trazabilidad basándonos en los lotes (QR/serie).
        """
        res = super().create_from_ui(orders, draft=draft)
        try:
            self._liq_mark_coupons_from_orders(orders_response=res)
        except Exception:
            _logger.exception("Error marcando cupones de liquidación desde POS")
        return res

    def _liq_mark_coupons_from_orders(self, orders_response):
        if not orders_response:
            return

        # orders_response = [{'id': 42, 'name': 'Order 00042', ...}, ...]
        order_ids = []
        for entry in orders_response:
            if isinstance(entry, dict):
                oid = entry.get('id')
                if isinstance(oid, int):
                    order_ids.append(oid)

        if not order_ids:
            return

        pos_orders = self.browse(order_ids)
        if not pos_orders:
            return

        Coupon = self.env['liquidation.coupon']

        # Detectar dinámicamente el modelo de trazas (por si se llama liq.trace o liquidation.trace)
        TraceModel = None
        for model_name in ('liq.trace', 'liquidation.trace'):
            if model_name in self.env:
                TraceModel = self.env[model_name]
                break

        # Buscar el campo many2one hacia liquidation.coupon
        coupon_m2o_field = None
        if TraceModel:
            for fname, field in TraceModel._fields.items():
                if getattr(field, 'type', None) == 'many2one' and getattr(field, 'comodel_name', None) == 'liquidation.coupon':
                    coupon_m2o_field = fname
                    break

        # Campo de estado del cupón (para ponerlo en usado/usado)
        coupon_state_field = Coupon._fields.get('liq_state')

        for order in pos_orders:
            # Sólo cuando la orden está realmente confirmada / cobrada
            if order.state not in ('paid', 'done', 'invoiced'):
                continue

            # Obtener los códigos (nombres de lote/QR) de las líneas del POS
            coupon_codes = set()
            for line in order.lines:
                pack_lots = getattr(line, 'pack_lot_ids', False)
                for lot in (pack_lots or []):
                    name = getattr(lot, 'lot_name', False)
                    if name:
                        coupon_codes.add(name.strip())

            if not coupon_codes:
                continue

            coupons = Coupon.search([('name', 'in', list(coupon_codes))])
            if not coupons:
                _logger.info(
                    "[POS Coupon] No se encontraron cupones para códigos %s en pedido %s",
                    coupon_codes, order.name or order.pos_reference
                )
                continue

            _logger.info(
                "[POS Coupon] Pedido %s (%s) → códigos %s → cupones %s",
                order.id, order.name or order.pos_reference, coupon_codes, coupons.ids
            )

            for coupon in coupons:
                vals = {}

                # Poner estado en 'used' / 'usado' si existe en la selección
                if coupon_state_field and getattr(coupon_state_field, 'type', None) == 'selection':
                    selection_items = coupon_state_field.selection or []
                    selection_keys = {key for key, _ in selection_items}
                    state_key = None
                    if 'used' in selection_keys:
                        state_key = 'used'
                    elif 'usado' in selection_keys:
                        state_key = 'usado'
                    if state_key:
                        vals[coupon_state_field.name] = state_key

                # Campos “típicos” si existen en el modelo
                if 'pos_order_id' in coupon._fields:
                    vals['pos_order_id'] = order.id
                if 'last_order_name' in coupon._fields:
                    vals['last_order_name'] = order.name or order.pos_reference
                if 'last_sale_date' in coupon._fields:
                    vals['last_sale_date'] = fields.Datetime.now()
                if 'last_user_id' in coupon._fields:
                    vals['last_user_id'] = order.user_id.id or self.env.user.id

                if vals:
                    coupon.write(vals)

                # Crear traza de forma genérica para que dispare la trazabilidad
                if TraceModel and coupon_m2o_field:
                    trace_vals = {coupon_m2o_field: coupon.id}

                    # Rellenar campos requeridos de forma genérica
                    for fname, field in TraceModel._fields.items():
                        if fname in trace_vals or not getattr(field, 'required', False):
                            continue
                        ftype = getattr(field, 'type', None)
                        if ftype == 'char':
                            trace_vals[fname] = "Venta POS %s" % (order.name or order.pos_reference)
                        elif ftype == 'float':
                            trace_vals[fname] = 0.0
                        elif ftype == 'integer':
                            trace_vals[fname] = 1
                        elif ftype == 'datetime':
                            trace_vals[fname] = fields.Datetime.now()
                        elif ftype == 'many2one':
                            comodel = getattr(field, 'comodel_name', '')
                            if comodel == 'pos.order':
                                trace_vals[fname] = order.id
                            elif comodel == 'res.users':
                                trace_vals[fname] = order.user_id.id or self.env.user.id
                            elif comodel == 'res.partner':
                                trace_vals[fname] = order.partner_id.id or False
                            elif comodel == 'stock.picking' and order.picking_ids:
                                trace_vals[fname] = order.picking_ids[0].id

                    TraceModel.create(trace_vals)

        return
