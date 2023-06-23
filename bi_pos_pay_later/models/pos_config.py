# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, api, _ , tools
from odoo.exceptions import Warning
from odoo.exceptions import RedirectWarning, UserError, ValidationError


class POSConfigInherit(models.Model):
	_inherit = 'pos.config'
	
	allow_partical_payment = fields.Boolean('Permitir pagos parciales')
	partial_product_id = fields.Many2one("product.product",string="Producto para pago parcial", domain = [('type', '=', 'service'),('available_in_pos', '=', True)])


class ResConfigSettings(models.TransientModel):
	_inherit = 'res.config.settings'


	allow_partical_payment = fields.Boolean(related='pos_config_id.allow_partical_payment',readonly=False)
	partial_product_id = fields.Many2one(related='pos_config_id.partial_product_id',readonly=False)


	@api.model
	def create(self, vals):
		res=super(ResConfigSettings, self).create(vals)
		product=self.env['product.product'].browse(vals.get('partial_product_id',False))

		if vals.get('allow_partical_payment',False) and product:
			if product.available_in_pos != True:
				raise ValidationError(_('Habilita disponible en punto de venta para el producto de pago parcial'))

			if product.taxes_id:
				raise ValidationError(_('No estás autorizado a agregar impuestos de cliente en el producto de pago parcial'))

		return res


	def write(self, vals):
		res=super(ResConfigSettings, self).write(vals)

		if self.allow_partical_payment:
			if self.partial_product_id.available_in_pos != True:
				raise ValidationError(_('Habilita disponible en punto de venta para el producto de pago parcial'))

			if self.partial_product_id.taxes_id:
				raise ValidationError(_('No estás autorizado a agregar impuestos de cliente en el producto de pago parcial'))

		return res

	
