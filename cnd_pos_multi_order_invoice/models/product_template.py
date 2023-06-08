# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    pos_global_invoice = fields.Boolean("Include in POS Global Invoice", default=True)
