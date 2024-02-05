# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, api, _


class ResConfigSettings(models.TransientModel):
	_inherit = 'res.config.settings'

	pos_show_product_info = fields.Boolean(related='pos_config_id.show_product_info', readonly=False)
	pos_hide_cost_currency = fields.Boolean(related='pos_config_id.hide_cost_currency', readonly=False)
	pos_hide_margin = fields.Boolean(related='pos_config_id.hide_margin', readonly=False)
	pos_show_available_pricelist_ids = fields.Many2many(related='pos_config_id.show_available_pricelist_ids', readonly=False)
