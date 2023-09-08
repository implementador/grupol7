# -*- coding:utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, api, _
from datetime import date, datetime
import random


class pos_order(models.Model):
	_inherit = 'pos.order'

	barcode = fields.Char(string="Order Barcode")
	barcode_img = fields.Binary('Order Barcode Image')


	@api.model
	def _order_fields(self, ui_order):
		res = super(pos_order, self)._order_fields(ui_order)
		code =(random.randrange(1111111111111,9999999999999))
		res['barcode'] = ui_order.get('barcode',code)
		return res
		

class pos_config(models.Model):
	_inherit = 'pos.config'
	
	show_order = fields.Boolean('Show Orders')
	pos_session_limit = fields.Selection([('all',  "Load all Session's Orders"), ('last3', "Load last 3 Session's Orders"), ('last5', " Load last 5 Session's Orders"),('current_day', "Only Current Day Orders"), ('current_session', "Only Current Session's Orders")], string='Session limit',default="current_day")
	show_barcode = fields.Boolean('Show Barcode in Receipt')
	show_draft = fields.Boolean('Show Draft Orders')
	show_posted = fields.Boolean('Show Posted Orders')



class ResConfigSettings(models.TransientModel):
	_inherit = 'res.config.settings'


	show_order = fields.Boolean('Show Orders',related="pos_config_id.show_order",readonly=False,)
	pos_session_limit = fields.Selection(related="pos_config_id.pos_session_limit", readonly=False, string='Session limit',)
	show_barcode = fields.Boolean('Show Barcode in Receipt',related="pos_config_id.show_barcode",readonly=False)
	show_draft = fields.Boolean('Show Draft Orders',related="pos_config_id.show_draft",readonly=False)
	show_posted = fields.Boolean('Show Posted Orders',related="pos_config_id.show_posted",readonly=False)
