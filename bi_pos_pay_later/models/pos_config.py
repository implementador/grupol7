# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, api, _ , tools
from odoo.exceptions import Warning
from odoo.exceptions import RedirectWarning, UserError, ValidationError

class ResCompany(models.Model):
	_inherit = 'res.company'
	

	point_of_sale_update_stock_quantities = fields.Selection([
				('closing', 'At the session closing (faster)'),
				('real', 'In real time (accurate but slower test)'),
				], default="real", string="Update quantities in stock",
				help="At the session closing:\n In real time: Each order sent to the server create its own picking")


class POSConfigInherit(models.Model):
	_inherit = 'pos.config'
	
	allow_partical_payment = fields.Boolean('Allow Partial Payment')
	partial_product_id = fields.Many2one("product.product",string="Partial Payment Product", domain = [('type', '=', 'service'),('available_in_pos', '=', True)])

	res_partner_id = fields.Many2one('res.partner', string="default Customer")

class ResConfigSettings(models.TransientModel):
	_inherit = 'res.config.settings'

	@api.model
	def default_get(self, fields):
		result = super(ResConfigSettings, self).default_get(fields)
		test_config = self.env['res.config.settings'].search([('company_id', '=', self.env.company.id)], order='write_date desc', limit=1)
		test_config.update({'update_stock_quantities':'real'})
		return result

	allow_partical_payment = fields.Boolean(related='pos_config_id.allow_partical_payment',readonly=False)
	partial_product_id = fields.Many2one(related='pos_config_id.partial_product_id',readonly=False)

	pos_res_partner_id = fields.Many2one(related='pos_config_id.res_partner_id', readonly=False)

	@api.onchange('update_stock_quantities')
	def _onchange_update_stock_quantities(self):
		if self.update_stock_quantities:
			if self.update_stock_quantities == 'closing':
				raise ValidationError(_('Not allowed to session closing.'))

	@api.model_create_multi
	def create(self, vals_list):
		res = super(ResConfigSettings, self).create(vals_list)

		for vals in vals_list:
			product=self.env['product.product'].browse(vals.get('partial_product_id',False))

			if vals.get('allow_partical_payment',False) and product:
				if product.available_in_pos != True:
					raise ValidationError(_('Please enable available in POS for the Partial Payment Product'))

				if product.taxes_id:
					raise ValidationError(_('You are not allowed to add Customer Taxes in the Partial Payment Product'))

		return res


	def write(self, vals):
		res=super(ResConfigSettings, self).write(vals)

		if self.allow_partical_payment:
			if self.partial_product_id.available_in_pos != True:
				raise ValidationError(_('Please enable available in POS for the Partial Payment Product'))

			if self.partial_product_id.taxes_id:
				raise ValidationError(_('You are not allowed to add Customer Taxes in the Partial Payment Product'))

		return res

	