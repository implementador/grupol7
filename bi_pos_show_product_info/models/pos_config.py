# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields


class PosConfig(models.Model):
    _inherit = 'pos.config'

    show_product_info = fields.Boolean(string="Show Product Info")
    hide_cost_currency = fields.Boolean(string="Hide Cost on Product Info")
    hide_margin = fields.Boolean(string="Hide Margin on Product Info")
    show_available_pricelist_ids = fields.Many2many('product.pricelist', 'show_available_pricelist_rel', 'available_pro_pricelist', 'pro_pricelist', string="Show Available Pricelist",store="True")
