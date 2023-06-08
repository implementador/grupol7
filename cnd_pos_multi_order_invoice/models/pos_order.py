# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import logging

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from itertools import groupby
from operator import itemgetter

_logger = logging.getLogger(__name__)


class PosPaymentMethod(models.Model):
    _inherit = 'pos.payment.method'

    l10n_mx_edi_payment_method_id = fields.Many2one(
        'l10n_mx_edi.payment.method',
        string='Payment Way',
        help='Indicates the way the invoice was/will be paid, where the '
        'options could be: Cash, Nominal Check, Credit Card, etc. Leave empty '
        'if unkown and the XML will show "Unidentified".',
        required=True,
        default=lambda self: self.env.ref('l10n_mx_edi.payment_method_otros',
                                          raise_if_not_found=False))


class PosOrder(models.Model):
    _inherit = 'pos.order'

    @api.depends('payment_ids')
    def _compute_main_payment_method_id(self):
        for order in self:
            if order.payment_ids:
                payment_id = order.payment_ids.filtered(
                    lambda i: i.amount > 0.00).sorted('amount')
                if payment_id:
                    order.main_payment_method_id = payment_id[-1].payment_method_id.id

    session_state = fields.Selection(
        string='Session Status',
        store=True, readonly=True,
        related="session_id.state")
    main_payment_method_id = fields.Many2one(
        'pos.payment.method',
        compute='_compute_main_payment_method_id',
        store=True,
        readonly=True,
        string='Main Payment Method')
    reverse_move = fields.Many2one('account.move', string='Reverse Move', readonly=True, copy=False)


    def _prepare_invoice_vals(self):
        res = super(PosOrder, self)._prepare_invoice_vals()
        if 'l10n_mx_edi_payment_method_id' in self.env['account.move']._fields:
            if self.main_payment_method_id and self.main_payment_method_id.l10n_mx_edi_payment_method_id:
                res.update({'l10n_mx_edi_payment_method_id': self.main_payment_method_id.l10n_mx_edi_payment_method_id.id})
        if 'l10n_mx_edi_usage' in self.env['res.partner']._fields and 'l10n_mx_edi_usage' in self.env['account.move']._fields:
            if self.partner_id.commercial_partner_id.l10n_mx_edi_usage:
                res.update({'l10n_mx_edi_usage': self.partner_id.commercial_partner_id.l10n_mx_edi_usage})
        
        # El términos de pago es Pago Inmediato, excepto para cuando el Método de Pago es Por Definir
        immediate_payment_term = self.env.ref('account.account_payment_term_immediate', raise_if_not_found=False)
        payment_method_otros = self.env.ref('l10n_mx_edi.payment_method_otros', raise_if_not_found=False)   
        if immediate_payment_term and payment_method_otros:
            if self.main_payment_method_id.l10n_mx_edi_payment_method_id != payment_method_otros:
                res.update({'invoice_payment_term_id': immediate_payment_term.id})
            else:
                payment_term_id = self.partner_id.commercial_partner_id.property_payment_term_id
                if payment_term_id:
                    res.update({'invoice_payment_term_id': payment_term_id.id})

        res.update({'is_multi_pos_order_invoice': False})
        return res

    def _prepare_invoice_line(self, order_line, receipt_number=False):
        res = super(PosOrder, self)._prepare_invoice_line(order_line)
        
        if receipt_number:
            name = receipt_number
        else:
            name = order_line.full_product_name or order_line.product_id.display_name
        res.update({'name': name, 'l10n_mx_edi_identification_number': receipt_number})
        return res

    def closed_or_opened(self, session_state):
        if session_state == 'closed':
            return session_state
        else:
            return 'opened'

    def action_create_multi_order_invoice(self):
        active_ids = self.env.context.get('active_ids')

        # POS Orders validations
        pos_orders = self.browse(active_ids)

        if pos_orders:
            invoice_type = 'out_invoice' if pos_orders[0].amount_total >= 0 else 'out_refund'
            session_state = 'closed' if pos_orders[0].session_state == 'closed' else 'opened'
            currency_id = pos_orders[0].currency_id

        for pos_order in pos_orders:
            # Los pedidos deben ser todos ventas o todos REEMBOLSOS
            if pos_order.amount_total >= 0 and invoice_type == 'out_refund':
                raise ValidationError(
                    _("The type of all POS orders selected must be the same (sale or refund)."))
            elif pos_order.amount_total < 0 and invoice_type == 'out_invoice':
                raise ValidationError(
                    _("The type of all POS orders selected must be the same (sale or refund)."))

            # Los pedidos deben estar en sesión 'closed' or 'any' pero no mezladas
            if self.closed_or_opened(pos_order.session_state) != session_state:
                raise ValidationError(
                    _("The session state of all POS orders selected must be the same, all closed or all opened."))

            # Si la sesión está abierta, veridicar que ningún producto sea NO facturable
            if session_state == 'opened':
                for line in pos_order.lines:
                    if not line.product_id.product_tmpl_id.pos_global_invoice:
                        raise ValidationError(_(
                            "The session state must be closed, because at least one "
                            "product of the pos orders is not billable."))

            # Los pedidos deben estar en estado 'paid' or 'done'
            if pos_order.state not in ('paid', 'done'):
                raise ValidationError(
                    _("The state of all POS orders selected must be paid or done."))

            # Los pedidos deben tener la misma moneda
            if pos_order.currency_id != currency_id:
                raise ValidationError(
                    _("The currency of all POS orders selected must be the same."))

        if not active_ids:
            return ''
        return {
            'name': _('Create Multi Order Invoice'),
            'res_model': 'wizard.mass.invoice',
            'view_mode': 'form',
            'view_id': self.env.ref('cnd_pos_multi_order_invoice.wizard_mass_invoice_pos_order').id,
            'context': self.env.context,
            'target': 'new',
            'type': 'ir.actions.act_window',
        }

    @api.model
    def _get_invoice_line_key_cols(self):
        fields = [
            'name', 'origin', 'discount', 'invoice_line_tax_ids', 'price_unit',
            'product_id', 'account_id', 'account_analytic_id',
            'uom_id'
        ]
        for field in ['sale_line_ids']:
            if field in self.env['account.invoice.line']._fields:
                fields.append(field)
        return fields

    # Odoo Original action_pos_order_invoice
    def create_invoice_from_pos_orders(
            self, customer_id, journal_id, currency_id, l10n_mx_edi_usage,
            l10n_mx_edi_payment_method_id, l10n_mx_edi_is_global_invoice, payment_method_id, invoice_date):
        _logger.info('Create Global Invoice')
        moves = self.env['account.move']

        # POS Orders validations
        pos_orders = self

        if pos_orders:
            invoice_type = 'out_invoice' if pos_orders[0].amount_total >= 0 else 'out_refund'
            session_state = 'closed' if pos_orders[0].session_state == 'closed' else 'opened'
            currency_id = pos_orders[0].currency_id

        # Realizar validaciones antes de realizar la factura
        for pos_order in pos_orders:
            # Los pedidos deben ser todos ventas o todos REEMBOLSOS
            if pos_order.amount_total >= 0 and invoice_type == 'out_refund':
                raise ValidationError(
                    _("The type of all POS orders selected must be the same (sale or refund)."))
            elif pos_order.amount_total < 0 and invoice_type == 'out_invoice':
                raise ValidationError(
                    _("The type of all POS orders selected must be the same (sale or refund)."))

            # Los pedidos deben estar en sesión 'closed' or 'any' pero no mezladas
            if self.closed_or_opened(pos_order.session_state) != session_state:
                raise ValidationError(
                    _("The session state of all POS orders selected must be the same, all closed or all opened."))

            # Si la sesión está abierta, veridicar que ningún producto sea NO facturable
            if session_state == 'opened':
                for line in pos_order.lines:
                    if not line.product_id.product_tmpl_id.pos_global_invoice:
                        raise ValidationError(_(
                            "The session state must be closed, because at least one "
                            "product of the pos orders is not billable."))

            # Los pedidos deben estar en estado 'paid' or 'done'
            if pos_order.state not in ('paid', 'done'):
                raise ValidationError(
                    _("The state of all POS orders selected must be paid or done."))

            # Los pedidos deben tener la misma moneda
            if pos_order.currency_id != currency_id:
                raise ValidationError(
                    _("The currency of all POS orders selected must be the same."))

        pre_invoice_line_ids = []
        name = _("Pos multi order invoice: ")
        note = ''
        for order in self:
            # TODO: No es lógico, comentarlo
            # Si algún pedido de factura global no tiene cliente, asignar el cliente de la factura
            if not l10n_mx_edi_is_global_invoice and not order.partner_id:
                order.partner_id = customer_id

            # Force company for all SUPERUSER_ID action
            if order.account_move:
                moves += order.account_move
                continue
            for line in order.lines:
                if line.product_id.product_tmpl_id.pos_global_invoice:
                    if line.price_subtotal > 0.00 and invoice_type == 'out_invoice' or \
                       line.price_subtotal < 0.00 and invoice_type == 'out_refund':
                        if l10n_mx_edi_is_global_invoice:
                            pre_invoice_line_ids.append(
                                order._prepare_invoice_line(line, order.pos_reference))
                        else:
                            pre_invoice_line_ids.append(
                                order._prepare_invoice_line(line))

            name += order.name + ', '
            if order.note:
                note += order.name + ': ' + order.note + '\n'
        name = name[:-2]
        note = note[:-1]

        # TODO: Merge lines with the same: Product, Unit Price, Discount, Taxes
        # Analizar: Lines will only be merged if:
        #    * Invoice lines are exactly the same except for the quantity and unit
        if l10n_mx_edi_is_global_invoice:
            product_uom_activity = self.env.ref(
                'cnd_pos_multi_order_invoice.product_uom_activity')
            product_product_sell = self.env.ref(
                'cnd_pos_multi_order_invoice.product_product_sell')

            grouper = itemgetter(
                'l10n_mx_edi_identification_number', 'tax_ids', 'discount')
            result = []

            for key, grp in groupby(sorted(pre_invoice_line_ids, key=grouper), grouper):
                temp_dict = dict(
                    zip(['l10n_mx_edi_identification_number', 'tax_ids', 'discount'], key))

                temp_dict['price_unit'] = 0
                for item in grp:
                    temp_dict['price_unit'] += item['price_unit'] * \
                        item['quantity']
                    if 'name' not in temp_dict:
                        temp_dict['name'] = item['name']

                temp_dict['quantity'] = 1
                temp_dict['product_id'] = product_product_sell.id
                temp_dict['product_uom_id'] = product_uom_activity.id
                result.append(temp_dict)

            pre_invoice_line_ids = result

        invoice_line_ids = []
        for invoice_line_id in pre_invoice_line_ids:
            invoice_line_ids.append((0, None, invoice_line_id))

        move_vals = {
            'payment_reference': name,
            'invoice_origin': name,
            'journal_id': journal_id.id,
            'move_type': invoice_type,
            'ref': name,
            'partner_id': customer_id.id,
            'narration': note,
            # considering partner's sale pricelist's currency
            'currency_id': currency_id.id,
            'invoice_user_id': self.env.user.id,
            'fiscal_position_id': customer_id.property_account_position_id.id,
            'invoice_line_ids': invoice_line_ids,
            'invoice_payment_term_id': customer_id.property_payment_term_id.id,
            'l10n_mx_edi_usage': l10n_mx_edi_usage,
            'l10n_mx_edi_payment_method_id': l10n_mx_edi_payment_method_id.id,
            'is_multi_pos_order_invoice': True,
            'invoice_date_due': fields.Date.context_today(self),
            'invoice_date': invoice_date,
        }

        new_move = moves.sudo().create(move_vals)
        message = _(
            "This invoice has been created from the point of sale multi order invoice")
        new_move.message_post(body=message)

        for order in self:
            order.write({'account_move': new_move.id, 'state': 'invoiced'})

        # Publicar la factura por defecto
        use_bridge_accounts = self.company_id.use_bridge_accounts

                
        use_bridge_accounts = self.company_id.use_bridge_accounts
        if use_bridge_accounts:
            self.company_id.bridge_income_account_id.write(
                {'user_type_id': self.env.ref('account.data_account_type_revenue').id, 'reconcile': True})
            self.company_id.bridge_expense_account_id.write(
                {'user_type_id': self.env.ref('account.data_account_type_receivable').id, 'reconcile': True})

        new_move.sudo()._post()

        # Si la sesión de los pedidos está CERRADA:
        #   Crear el movimiento de reversa para que la factura quede corrctamente pagada
        create_out_refund_as_payment = self.env.company.create_out_refund_as_payment

        if session_state == 'closed' and create_out_refund_as_payment:
            _logger.info('Create Reverse move as Invoice Payment')
            reverse_type_map = {
                'entry': 'entry',
                'out_invoice': 'out_refund',
                'out_refund': 'entry',
                'in_invoice': 'in_refund',
                'in_refund': 'entry',
                'out_receipt': 'entry',
                'in_receipt': 'entry',
            }

            default_values = [{
                'move_type': reverse_type_map[new_move.move_type],
                'reversed_entry_id': new_move.id,
                'invoice_date': new_move.invoice_date,
            }]
            reverse_moves = new_move._reverse_moves(
                default_values_list=default_values, cancel=False)

            # Reconciliar para que quede como pagada
            reverse_moves.l10n_mx_edi_sign_required = False
            # Colocar un distintivo a la Nota de crédito para que no sea tomada en cuenta para el cálculo de comisiones
            # módulo: sale_commission
            reverse_moves.is_multi_pos_order_invoice = True
            # TODO: Quitar este comentario para nuevas versiones de cnd_l10n_mx_edi_restrict_sign,
            #       ya que el campo l10n_mx_edi_xml_file_require es de solo lectura, hacerlo store=True
            # reverse_moves.l10n_mx_edi_xml_file_require = False

            reverse_lines = reverse_moves.mapped('line_ids')
            # Reconciliar para que quede como pagada
            if reverse_lines:
                _logger.info('Remove reconcile to Reverse Move')
                reverse_lines.remove_move_reconcile()
                # new_move.mapped('line_ids').remove_move_reconcile()

            # Reconcile moves together to cancel the previous one.
            reverse_moves.with_context(move_reverse_cancel=True)._post()

            if (payment_method_id.type != 'pay_later'):
                for move, reverse_move in zip(new_move, reverse_moves):
                    lines = move.line_ids.filtered(
                        lambda x: (
                            x.account_id.reconcile or x.account_id.account_type in ('asset_cash', 'liability_credit_card'))
                        and not x.reconciled
                    )
                    for line in lines:
                        counterpart_lines = reverse_move.line_ids.filtered(
                            lambda x: x.account_id == line.account_id and x.currency_id == line.currency_id
                            and not x.reconciled
                        )
                        (line + counterpart_lines).with_context(move_reverse_cancel=True).reconcile()
            else:
                # Conciliar el movimiento reverso con la(s) póliza(s) de(los) pedido(s):
                if invoice_type == 'out_invoice':
                    debit_or_credit = 'debit'
                else:
                    debit_or_credit = 'credit'
                move_line_ids = []
                for order_id in self:
                    for line_id in order_id.session_id.move_id.line_ids:
                        if line_id[debit_or_credit] == order_id.amount_total \
                                and line_id.partner_id.commercial_partner_id.id == order_id.partner_id.commercial_partner_id.id \
                                and line_id.parent_state == 'posted' \
                                and (line_id.reconciled is False or line_id.amount_residual != 0 and line_id.amount_residual_currency != 0):
                            if line_id not in move_line_ids:
                                move_line_ids.append(line_id)

                for line in move_line_ids:
                    counterpart_lines = reverse_moves.line_ids.filtered(
                        lambda x: x.account_id == line.account_id and x.currency_id == line.currency_id
                        and not x.reconciled
                    )
                    (line + counterpart_lines).with_context(move_reverse_cancel=True).reconcile()
            for order in self:
                order.write({'reverse_move': reverse_moves.id})

        return new_move

        # Chida página
        # https://github.com/Odoo-10-test/trucos_odoo/blob/master/modelos.md
