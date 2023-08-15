# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, api, _ , tools
from odoo.exceptions import Warning
from odoo.exceptions import RedirectWarning, UserError, ValidationError
import random
import psycopg2
import base64
from odoo.http import request
from functools import partial
from odoo.tools import float_is_zero

from datetime import date, datetime
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT, DEFAULT_SERVER_DATE_FORMAT
import logging
from odoo.osv.expression import AND

_logger = logging.getLogger(__name__)


class ReceptionReport(models.AbstractModel):
    _inherit = 'report.point_of_sale.report_saledetails'



    @api.model
    def get_sale_details(self, date_start=False, date_stop=False, config_ids=False, session_ids=False):
        """ Serialise the orders of the requested time period, configs and sessions.

        :param date_start: The dateTime to start, default today 00:00:00.
        :type date_start: str.
        :param date_stop: The dateTime to stop, default date_start + 23:59:59.
        :type date_stop: str.
        :param config_ids: Pos Config id's to include.
        :type config_ids: list of numbers.
        :param session_ids: Pos Config id's to include.
        :type session_ids: list of numbers.

        :returns: dict -- Serialised sales.
        """
        domain = [('state', 'in', ['paid','invoiced','done'])]

        if (session_ids):
            domain = AND([domain, [('session_id', 'in', session_ids)]])
        else:
            if date_start:
                date_start = fields.Datetime.from_string(date_start)
            else:
                # start by default today 00:00:00
                user_tz = pytz.timezone(self.env.context.get('tz') or self.env.user.tz or 'UTC')
                today = user_tz.localize(fields.Datetime.from_string(fields.Date.context_today(self)))
                date_start = today.astimezone(pytz.timezone('UTC'))

            if date_stop:
                date_stop = fields.Datetime.from_string(date_stop)
                # avoid a date_stop smaller than date_start
                if (date_stop < date_start):
                    date_stop = date_start + timedelta(days=1, seconds=-1)
            else:
                # stop by default today 23:59:59
                date_stop = date_start + timedelta(days=1, seconds=-1)

            domain = AND([domain,
                [('date_order', '>=', fields.Datetime.to_string(date_start)),
                ('date_order', '<=', fields.Datetime.to_string(date_stop))]
            ])

            if config_ids:
                domain = AND([domain, [('config_id', 'in', config_ids)]])

        orders = self.env['pos.order'].search(domain)

        user_currency = self.env.company.currency_id

        total = 0.0
        products_sold = {}
        taxes = {}
        for order in orders:
            if user_currency != order.pricelist_id.currency_id:
                total += order.pricelist_id.currency_id._convert(
                    order.amount_total, user_currency, order.company_id, order.date_order or fields.Date.today())
            else:
                total += order.amount_total
            currency = order.session_id.currency_id

            for line in order.lines:
                key = (line.product_id, line.price_unit, line.discount)
                products_sold.setdefault(key, 0.0)
                products_sold[key] += line.qty

                if line.tax_ids_after_fiscal_position:
                    line_taxes = line.tax_ids_after_fiscal_position.sudo().compute_all(line.price_unit * (1-(line.discount or 0.0)/100.0), currency, line.qty, product=line.product_id, partner=line.order_id.partner_id or False)
                    for tax in line_taxes['taxes']:
                        taxes.setdefault(tax['id'], {'name': tax['name'], 'tax_amount':0.0, 'base_amount':0.0})
                        taxes[tax['id']]['tax_amount'] += tax['amount']
                        taxes[tax['id']]['base_amount'] += tax['base']
                else:
                    taxes.setdefault(0, {'name': _('No Taxes'), 'tax_amount':0.0, 'base_amount':0.0})
                    taxes[0]['base_amount'] += line.price_subtotal_incl

        payment_ids = self.env["pos.payment"].search([('pos_order_id', 'in', orders.ids)]).ids
        if payment_ids:
            self.env.cr.execute("""
                SELECT COALESCE(method.name->>%s, method.name->>'en_US') as name, sum(amount) total
                FROM pos_payment AS payment,
                     pos_payment_method AS method
                WHERE payment.payment_method_id = method.id
                    AND payment.id IN %s
                GROUP BY method.name
            """, (self.env.lang, tuple(payment_ids),))
            payments = self.env.cr.dictfetchall()
        else:
            payments = []

        return {
            'date_start': date_start,
            'date_stop': date_stop,
            'currency_precision': user_currency.decimal_places,
            'total_paid': user_currency.round(total),
            'payments': payments,
            'company_name': self.env.company.name,
            'taxes': list(taxes.values()),
            'orders': orders,
        }





class PosPaymentInherit(models.Model):
	_inherit = 'pos.payment'

	session_id = fields.Many2one('pos.session', related='', string='Session', store=True, index=True)



class PosOrderInherit(models.Model):
	_inherit = 'pos.order'


	return_order_ref = fields.Many2one('pos.order',string="Return Order Ref")


	@api.model
	def _payment_fields(self, order, ui_paymentline):
		res = super(PosOrderInherit, self)._payment_fields(order,ui_paymentline)
		res['session_id'] = order.session_id.id

		return res

	def _default_session(self):
		return self.env['pos.session'].search([('state', '=', 'opened'), ('user_id', '=', self.env.uid)], limit=1)


	is_picking_created = fields.Boolean('Picking Created')
	is_partial = fields.Boolean('Is Partial Payment')
	amount_due = fields.Float("Amount Due",compute="get_amount_due")

	@api.depends('amount_total','amount_paid')
	def get_amount_due(self):
		for order in self :
			if order.amount_paid - order.amount_total >= 0:
				order.amount_due = 0
				order.is_partial = False
			else:
				order.amount_due = order.amount_total - order.amount_paid
				
	def write(self, vals):
		for order in self:
			if order.name == '/' and order.is_partial :
				vals['name'] = order.config_id.sequence_id._next()
		return super(PosOrderInherit, self).write(vals)

	def _is_pos_order_paid(self):
		return float_is_zero(self._get_rounded_amount(self.amount_total) - self.amount_paid, precision_rounding=self.currency_id.rounding)

	def action_pos_order_paid(self):
		self.ensure_one()
		if not self.is_partial:
			return super(PosOrderInherit, self).action_pos_order_paid()
		if self.is_partial:
			if self._is_pos_order_paid():
				self.write({'state': 'paid'})
				if self.picking_ids:
					return True
				else :
					return self._create_order_picking()
			else:
				if not self.picking_ids :
					return self._create_order_picking()
				else:
					return False

	@api.model
	def _order_fields(self, ui_order):
		res = super(PosOrderInherit, self)._order_fields(ui_order)
		process_line = partial(self.env['pos.order.line']._order_line_fields, session_id=ui_order['pos_session_id'])
		if 'is_partial' in ui_order:
			res['is_partial'] = ui_order.get('is_partial',False) 
			res['amount_due'] = ui_order.get('amount_due',0.0)

		if 'return_order_ref' in ui_order:
			if ui_order.get('return_order_ref') != False:
				res['return_order_ref'] = int(ui_order['return_order_ref'])
				po_line_obj = self.env['pos.order.line']
				for l in ui_order['lines']:
					line = po_line_obj.browse(int(l[2]['original_line_id']))
					if line:
						line.write({
							'return_qty' : line.return_qty - (l[2]['qty']),
						})
		return res

	@api.model
	def _process_order(self, order, draft, existing_order):
		"""Create or update an pos.order from a given dictionary.

		:param dict order: dictionary representing the order.
		:param bool draft: Indicate that the pos_order is not validated yet.
		:param existing_order: order to be updated or False.
		:type existing_order: pos.order.
		:returns: id of created/updated pos.order
		:rtype: int
		"""
		order = order['data']
		is_partial = order.get('is_partial')
		is_draft_order = order.get('is_draft_order')
		is_paying_partial = order.get('is_paying_partial')

		pos_session = self.env['pos.session'].browse(order['pos_session_id'])
		if pos_session.state == 'closing_control' or pos_session.state == 'closed':
			order['pos_session_id'] = self._get_valid_session(order).id

		pos_order = False
		if is_paying_partial:
			pos_order = self.search([('pos_reference', '=', order.get('name'))])
		else:
			if not existing_order:
				pos_order = self.create(self._order_fields(order))
			else:
				pos_order = existing_order
				pos_order.lines.unlink()
				order['user_id'] = pos_order.user_id.id
				pos_order.write(self._order_fields(order))

		pos_order = pos_order.with_company(pos_order.company_id)
		self = self.with_company(pos_order.company_id)
		self._process_payment_lines(order, pos_order, pos_session, draft)

		try:
			pos_order.action_pos_order_paid()
		except psycopg2.DatabaseError:
			# do not hide transactional errors, the order(s) won't be saved!
			raise
		except Exception as e:
			_logger.error('Could not fully process the POS Order: %s', tools.ustr(e))

		if pos_order.is_partial == False and is_paying_partial == False:

			if pos_order.company_id.point_of_sale_update_stock_quantities == "real":
				pos_order._create_order_picking()


		create_invoice = False
		if order.get('to_invoice' , False) and pos_order.state == 'paid':
			create_invoice = True


		if create_invoice:
			pos_order.action_pos_order_invoice()

		return pos_order.id


	def _process_payment_lines(self, pos_order, order, pos_session, draft):
		"""Create account.bank.statement.lines from the dictionary given to the parent function.

		If the payment_line is an updated version of an existing one, the existing payment_line will first be
		removed before making a new one.
		:param pos_order: dictionary representing the order.
		:type pos_order: dict.
		:param order: Order object the payment lines should belong to.
		:type order: pos.order
		:param pos_session: PoS session the order was created in.
		:type pos_session: pos.session
		:param draft: Indicate that the pos_order is not validated yet.
		:type draft: bool.
		"""
		prec_acc = order.pricelist_id.currency_id.decimal_places

		order_bank_statement_lines= self.env['pos.payment'].search([('pos_order_id', '=', order.id)])
		is_paying_partial = pos_order.get('is_paying_partial')
		if not is_paying_partial:
			order_bank_statement_lines.unlink()
		for payments in pos_order['statement_ids']:
			if not float_is_zero(payments[2]['amount'], precision_digits=prec_acc):
				order.add_payment(self._payment_fields(order, payments[2]))

		order.amount_paid = sum(order.payment_ids.mapped('amount'))

		if order.amount_paid >= order.amount_total :
			order.write({
				'is_partial' : False,
			})

		if not draft and not float_is_zero(pos_order['amount_return'], prec_acc):
			cash_payment_method = pos_session.payment_method_ids.filtered('is_cash_count')[:1]
			if not cash_payment_method:
				raise UserError(_("No cash statement found for this session. Unable to record returned cash."))
			return_payment_vals = {
				'name': _('return'),
				'pos_order_id': order.id,
                'session_id': order.session_id.id,
				'amount': -pos_order['amount_return'],
				'payment_date': fields.Datetime.now(),
				'payment_method_id': cash_payment_method.id,
				'is_change': True,
			}
			order.add_payment(return_payment_vals)


class PosMakePayment(models.TransientModel):
	_inherit = 'pos.make.payment'

	def check(self):
		"""Check the order:
		if the order is not paid: continue payment,
		if the order is paid print ticket.
		"""
		self.ensure_one()

		order = self.env['pos.order'].browse(self.env.context.get('active_id', False))
		currency = order.currency_id

		init_data = self.read()[0]
		if not float_is_zero(init_data['amount'], precision_rounding=currency.rounding):
			order.add_payment({
				'pos_order_id': order.id,
				'session_id' : order.session_id.id,
				'amount': order._get_rounded_amount(init_data['amount']),
				'name': init_data['payment_name'],
				'payment_method_id': init_data['payment_method_id'][0],
			})

		if order._is_pos_order_paid():
			order.action_pos_order_paid()
			order._create_order_picking()
			order._compute_total_cost_in_real_time()
			return {'type': 'ir.actions.act_window_close'}

		return self.launch_payment()


class PosOrderLineInherit(models.Model):
	_inherit = 'pos.order.line'

	original_line_id = fields.Many2one('pos.order.line', string="original Line")
	return_qty = fields.Float('Return Qty')