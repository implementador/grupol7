# -*- coding: utf-8 -*-
from datetime import date

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class LiquidationCoupon(models.Model):
    _name = "liquidation.coupon"
    _description = "Cupón de liquidación (QR por pieza)"
    _rec_name = "name"

    # -------------------------
    # Datos principales
    # -------------------------
    name = fields.Char(
        string="Código", required=True, copy=False, index=True,
        default=lambda self: secrets.token_urlsafe(10)
    )
    product_id = fields.Many2one(
        "product.product", string="Producto", required=True
    )
    lot_id = fields.Many2one(
        "stock.lot", string="N. serie/lote"
    )
    damage_grade = fields.Selection(
        [
            ("A", "Rayón leve"),
            ("B", "Golpe"),
            ("C", "Detalle serio"),
        ],
        string="Daño",
    )
    damage_note = fields.Char(string="Detalle de daño")

    clearance_price = fields.Monetary(
        string="Precio liquidación", digits=(16, 4), required=True
    )
    currency_id = fields.Many2one(
        "res.currency", string="Moneda",
        related="company_id.currency_id", store=True, readonly=True
    )

    expiration_date = fields.Date(string="Vence el")
    pos_allowed_ids = fields.Many2many(
        "pos.config", string="PdV permitidos"
    )

    # NUEVO: ubicación a la que pertenece el cupón
    location_id = fields.Many2one(
        "stock.location",
        string="Ubicación",
        domain=[("usage", "in", ("internal", "transit"))],
        help="Ubicación/almacén donde físicamente está la pieza asociada al cupón."
    )

    state = fields.Selection(
        [
            ("new", "Nuevo"),
            ("used", "Usado"),
            ("cancelled", "Cancelado"),
            ("expired", "Expirado"),
        ],
        default="new",
        string="Estado", index=True
    )

    # Trazabilidad / vínculos
    sale_order_id = fields.Many2one(
        "sale.order", string="Sale Order", readonly=True
    )
    sale_order_line_id = fields.Many2one(
        "sale.order.line", string="Sale Order Line", readonly=True
    )
    pos_order_id = fields.Many2one(
        "pos.order", string="Pos Order", readonly=True
    )
    pos_order_line_id = fields.Many2one(
        "pos.order.line", string="Pos Order Line", readonly=True
    )
    used_datetime = fields.Datetime(
        string="Usado el", readonly=True
    )

    company_id = fields.Many2one(
        "res.company", string="Company", required=True,
        default=lambda s: s.env.company
    )
    notes = fields.Char(string="Notas")

    _sql_constraints = [
        ("name_uniq", "unique(name)", "El código de cupón debe ser único."),
    ]

    # ---------------------------------------------------------
    # Helpers internos
    # ---------------------------------------------------------
    def _pos_location_from_config(self, pos_config):
        """Devuelve la ubicación de stock que usa el PdV para abastecerse."""
        if not pos_config:
            return False
        picking_type = pos_config.picking_type_id
        return (
            picking_type.default_location_src_id
            or (picking_type.warehouse_id and picking_type.warehouse_id.lot_stock_id)
            or False
        )

    def _check_location_allowed(self, location):
        """Si el cupón tiene location_id, exige que coincida con la del PdV (o su hijo)."""
        if not self.location_id or not location:
            return  # Sin restricción de ubicación
        # Permite misma ubicación o una hija (ej. estante dentro de almacén del PdV)
        child_ids = self.env["stock.location"].search([("id", "child_of", location.id)]).ids
        if self.location_id.id not in child_ids:
            raise UserError(_("Este cupón pertenece a otra ubicación/almacén."))

    # ---------------------------------------------------------
    # Validaciones reutilizables
    # ---------------------------------------------------------
    def _check_valid(self, pos_config=None, company=None, product=None, location=None):
        """Valida reglas de uso del cupón. Lanza UserError si algo no cuadra."""
        self.ensure_one()

        if self.state != "new":
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

        # Validación de ubicación
        if location:
            self._check_location_allowed(location)

        return True

    # ---------------------------------------------------------
    # RPC para POS: Validar antes de agregar línea
    # (Se usa al escanear o desde el botón en el POS)
    # ---------------------------------------------------------
    @api.model
    def pos_validate_coupon(self, code, pos_config_id):
        """Valida un cupón y devuelve datos para prellenar la línea del POS."""
        coupon = self.search([("name", "=", code)], limit=1)
        if not coupon:
            raise UserError(_("Código no encontrado."))

        pos_config = self.env["pos.config"].browse(pos_config_id) if pos_config_id else False
        company = pos_config.company_id if pos_config else self.env.company
        pos_location = coupon._pos_location_from_config(pos_config)

        # Validación asegura estado, empresa, vencimiento, PdV permitido y ubicación.
        coupon._check_valid(
            pos_config=pos_config,
            company=company,
            product=coupon.product_id,
            location=pos_location,
        )

        info = "[%s] %s" % (coupon.damage_grade or "", coupon.product_id.display_name)
        return {
            "product_id": coupon.product_id.id,
            "price": coupon.clearance_price,
            "info": info.strip(),
            "coupon_id": coupon.id,
        }

    # ---------------------------------------------------------
    # RPC para POS: Redimir después de crear la línea
    # (Se llama cuando el usuario confirma aplicar el cupón)
    # ---------------------------------------------------------
    @api.model
    def pos_redeem_coupon(self, code, pos_order_id, pos_order_line_id):
        """Marca el cupón como usado y lo liga a la orden/línea del POS."""
        coupon = self.search([("name", "=", code)], limit=1)
        if not coupon:
            raise UserError(_("Código no encontrado."))

        if coupon.state != "new":
            raise UserError(_("Cupón ya utilizado."))

        order = self.env["pos.order"].browse(pos_order_id)
        line = self.env["pos.order.line"].browse(pos_order_line_id)

        pos_config = order.config_id
        pos_location = coupon._pos_location_from_config(pos_config)

        # Validación final contra empresa, PdV, producto y ubicación de la línea
        coupon._check_valid(
            pos_config=pos_config,
            company=order.company_id,
            product=line.product_id,
            location=pos_location,
        )

        coupon.write(
            {
                "state": "used",
                "pos_order_id": order.id,
                "pos_order_line_id": line.id,
                "used_datetime": fields.Datetime.now(),
            }
        )
        return True

    # ---------------------------------------------------------
    # name_get bonito
    # ---------------------------------------------------------
    def name_get(self):
        res = []
        for rec in self:
            label = rec.name
            if rec.product_id:
                label = "%s - %s" % (rec.name, rec.product_id.display_name)
            res.append((rec.id, label))
        return res
