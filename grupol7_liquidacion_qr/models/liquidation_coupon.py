# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from datetime import date
import secrets


class LiquidationCoupon(models.Model):
    _name = 'liquidation.coupon'
    _description = 'Cupón de liquidación (QR por pieza)'
    _rec_name = 'name'

    # -------------------------------------------------------------------------
    # Datos principales
    # -------------------------------------------------------------------------
    name = fields.Char(
        string="Código",
        required=True,
        copy=False,
        index=True,
        default=lambda s: secrets.token_urlsafe(10),
    )
    product_id = fields.Many2one(
        'product.product', string="Producto", required=True
    )
    lot_id = fields.Many2one(
        'stock.lot', string="N. serie/lote",
        domain="[('product_id','=',product_id)]"
    )

    damage_grade = fields.Selection(
        [
            ('A', "Rayón leve"),
            ('B', "Golpe"),
            ('C', "Detalle serio"),
        ],
        string="Daño",
    )
    damage_note = fields.Char(string="Detalle de daño")

    clearance_price = fields.Monetary(
        string="Precio liquidación", required=True, currency_field='currency_id'
    )
    currency_id = fields.Many2one(
        'res.currency', string="Moneda",
        related='company_id.currency_id', store=True, readonly=True
    )

    expiration_date = fields.Date(string="Vence el")

    # PdV autorizados para usar el cupón
    pos_allowed_ids = fields.Many2many('pos.config', string="PdV permitidos")

    # -------------------------------------------------------------------------
    # Stock/Ubicación
    # -------------------------------------------------------------------------
    location_id = fields.Many2one(
        'stock.location', string="Ubicación POS",
        domain="[('usage','=','internal'), ('company_id','=',company_id)]",
        help="Ubicación física donde está la pieza asociada al cupón."
    )
    qty_at_location = fields.Float(
        string="Existencia en ubicación",
        compute="_compute_qty_at_location", digits='Product Unit of Measure'
    )

    # -------------------------------------------------------------------------
    # Estados / vínculo con ventas
    # -------------------------------------------------------------------------
    state = fields.Selection(
        [
            ('new', 'Nuevo'),
            ('used', 'Usado'),
            ('cancelled', 'Cancelado'),
            ('expired', 'Expirado'),
        ],
        default='new', string="Estado", index=True
    )

    sale_order_id = fields.Many2one('sale.order', string="Sale Order", readonly=True)
    sale_order_line_id = fields.Many2one(
        'sale.order.line', string="Sale Order Line", readonly=True
    )
    pos_order_id = fields.Many2one('pos.order', string="Pos Order", readonly=True)
    pos_order_line_id = fields.Many2one(
        'pos.order.line', string="Pos Order Line", readonly=True
    )

    used_datetime = fields.Datetime(string="Usado el", readonly=True)

    company_id = fields.Many2one(
        'res.company', string="Company", required=True, default=lambda s: s.env.company
    )
    notes = fields.Char(string="Notas")

    _sql_constraints = [
        ('name_uniq', 'unique(name)', "El código de cupón debe ser único."),
    ]

    # -------------------------------------------------------------------------
    # Computes
    # -------------------------------------------------------------------------
    @api.depends('product_id', 'location_id', 'company_id')
    def _compute_qty_at_location(self):
        Quant = self.env['stock.quant']
        for rec in self:
            qty = 0.0
            if rec.product_id and rec.location_id:
                quants = Quant.search([
                    ('product_id', '=', rec.product_id.id),
                    ('location_id', 'child_of', rec.location_id.id),
                    ('company_id', '=', rec.company_id.id),
                ])
                qty = sum(quants.mapped('available_quantity'))
            rec.qty_at_location = qty

    # -------------------------------------------------------------------------
    # Validaciones reutilizables
    # -------------------------------------------------------------------------
    def _check_valid(self, pos_config=None, company=None, product=None):
        """Valida reglas de uso del cupón. Lanza UserError si algo no cuadra."""
        self.ensure_one()

        if self.state != 'new':
            raise UserError(_("Cupón ya utilizado o inválido."))

        if company and self.company_id != company:
            raise UserError(_("Cupón de otra compañía."))

        if self.expiration_date and date.today() > self.expiration_date:
            raise UserError(_("Cupón expirado."))

        if pos_config:
            if self.pos_allowed_ids and pos_config not in self.pos_allowed_ids:
                raise UserError(_("Este PdV no está autorizado para este cupón."))

        if product and self.product_id and product != self.product_id:
            raise UserError(_("Cupón no corresponde al producto."))

        # Si se indicó ubicación en el cupón, exigimos existencia > 0 allí
        if self.location_id and self.qty_at_location <= 0:
            raise UserError(_("Sin existencias en la ubicación del cupón."))

        return True

    # -------------------------------------------------------------------------
    # RPC para POS: Validar antes de agregar línea
    # -------------------------------------------------------------------------
    @api.model
    def pos_validate_coupon(self, code, pos_config_id):
        """Valida un cupón y devuelve datos para prellenar la línea del POS."""
        coupon = self.search([('name', '=', code)], limit=1)
        if not coupon:
            raise UserError(_("Código no encontrado."))

        pos_config = self.env['pos.config'].browse(pos_config_id) if pos_config_id else False
        company = pos_config.company_id if pos_config else self.env.company

        # Valida estado, empresa, vencimiento, PdV y ubicación/stock
        coupon._check_valid(pos_config=pos_config, company=company, product=coupon.product_id)

        return {
            "product_id": coupon.product_id.id,
            "price": coupon.clearance_price,
            "info": "[%s] %s" % (coupon.damage_grade or "", coupon.product_id.display_name),
            "coupon_id": coupon.id,
            # Para autoinserción en POS:
            "lot_name": coupon.lot_id.name or "",
            "requires_lot": coupon.product_id.tracking in ("lot", "serial"),
        }

    # -------------------------------------------------------------------------
    # RPC para POS: Redimir después de crear la línea
    # -------------------------------------------------------------------------
    @api.model
    def pos_redeem_coupon(self, code, pos_order_id, pos_order_line_id):
        """Marca el cupón como usado y lo liga a la orden/línea del POS."""
        coupon = self.search([('name', '=', code)], limit=1)
        if not coupon:
            raise UserError(_("Código no encontrado."))

        if coupon.state != 'new':
            raise UserError(_("Cupón ya utilizado."))

        order = self.env['pos.order'].browse(pos_order_id)
        line = self.env['pos.order.line'].browse(pos_order_line_id)

        # Validación final contra empresa, PdV, producto y ubicación
        coupon._check_valid(
            pos_config=order.config_id,
            company=order.company_id,
            product=line.product_id,
        )

        coupon.write({
            'state': 'used',
            'pos_order_id': order.id,
            'pos_order_line_id': line.id,
            'used_datetime': fields.Datetime.now(),
        })
        return True

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------
    def name_get(self):
        res = []
        for rec in self:
            label = rec.name
            if rec.product_id:
                label = "%s - %s" % (rec.name, rec.product_id.display_name)
            res.append((rec.id, label))
        return res
