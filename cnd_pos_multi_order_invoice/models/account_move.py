# -*- coding: utf-8 -*-
from odoo import models, fields, api


class AccountMove(models.Model):
    _inherit = 'account.move'

    @api.depends('partner_id')
    def _compute_sign_required(self):
        """Assign the "Sign CFDI?" value how in the partner"""
        out_invoice = self.filtered(lambda i: i.move_type == 'out_invoice')
        for record in out_invoice:
            record.l10n_mx_edi_sign_required = record.partner_id.commercial_partner_id.l10n_mx_edi_sign_required
            record.l10n_mx_edi_payment_sign_required = record.partner_id.commercial_partner_id.l10n_mx_edi_sign_required

        for record in self - out_invoice:
            record.l10n_mx_edi_sign_required = True
            record.l10n_mx_edi_payment_sign_required = True

    def _inverse_sign_required(self):
        return False

    is_multi_pos_order_invoice = fields.Boolean(default=False, readonly=True)
    l10n_mx_edi_sign_required = fields.Boolean(
        string='Sign CFDI?',
        compute='_compute_sign_required',
        default=True,
        store=True,
        inverse='_inverse_sign_required',
        states={'draft': [('readonly', False)]},
        help='If this field is active, the CFDI will be generated for this invoice.')
    l10n_mx_edi_payment_sign_required = fields.Boolean(
        string='Sign CFDI Payment?',
        compute='_compute_sign_required',
        default=True,
        store=True,
        inverse='_inverse_sign_required',
        states={'draft': [('readonly', False)]},
        help='If this field is active, the CFDI payment will be generated for this invoice payments.')
    l10n_mx_edi_usage = fields.Selection(
        selection_add=[('S01', 'No tax effects')])
    l10n_mx_edi_periodicity = fields.Selection(
        string='Periodicity',
        related='company_id.l10n_mx_edi_periodicity',
        required=True,
        readonly=False,
        help="Used on every global invoice on Global Information Node.")


    def button_cancel(self):
        res = super(AccountMove, self).button_cancel()

        for invoice in self:
            for pos_order in invoice.pos_order_ids:
                pos_order.state = 'done'
                pos_order.account_move = False
        return res

    def l10n_mx_edi_is_required(self):
        self.ensure_one()

        return (self.l10n_mx_edi_sign_required and super(AccountMove, self).l10n_mx_edi_is_required())

    # TODO: Revisar si es la solución para no crear los asientos contables de costo y de salida de mercancía
    # def is_sale_document(self, include_receipts=False):
    #     if self.is_multi_pos_order_invoice == True:
    #         return False
    #     else:
    #         return self.move_type in self.get_sale_types(include_receipts)

    # Override this method
    def _stock_account_prepare_anglo_saxon_out_lines_vals(self):
        ''' Prepare values used to create the journal items (account.move.line) corresponding to the Cost of Good Sold
        lines (COGS) for customer invoices.

        Example:

        Buy a product having a cost of 9 being a storable product and having a perpetual valuation in FIFO.
        Sell this product at a price of 10. The customer invoice's journal entries looks like:

        Account                                     | Debit | Credit
        ---------------------------------------------------------------
        200000 Product Sales                        |       | 10.0
        ---------------------------------------------------------------
        101200 Account Receivable                   | 10.0  |
        ---------------------------------------------------------------

        This method computes values used to make two additional journal items:

        ---------------------------------------------------------------
        220000 Expenses                             | 9.0   |
        ---------------------------------------------------------------
        101130 Stock Interim Account (Delivered)    |       | 9.0
        ---------------------------------------------------------------

        Note: COGS are only generated for customer invoices except refund made to cancel an invoice.

        :return: A list of Python dictionary to be passed to env['account.move.line'].create.
        '''
        lines_vals_list = []
        for move in self:
            # Make the loop multi-company safe when accessing models like product.product
            move = move.with_company(move.company_id)

            if not move.is_sale_document(include_receipts=True) or \
               not move.company_id.anglo_saxon_accounting or self.is_multi_pos_order_invoice:
                continue

            for line in move.invoice_line_ids:

                # Filter out lines being not eligible for COGS.
                if not line._eligible_for_cogs():
                    continue

                # Retrieve accounts needed to generate the COGS.
                accounts = line.product_id.product_tmpl_id.get_product_accounts(fiscal_pos=move.fiscal_position_id)
                debit_interim_account = accounts['stock_output']
                credit_expense_account = accounts['expense'] or move.journal_id.default_account_id
                if not debit_interim_account or not credit_expense_account:
                    continue

                # Compute accounting fields.
                sign = -1 if move.move_type == 'out_refund' else 1
                price_unit = line._stock_account_get_anglo_saxon_price_unit()
                balance = sign * line.quantity * price_unit

                # Add interim account line.
                lines_vals_list.append({
                    'name': line.name[:64],
                    'move_id': move.id,
                    'partner_id': move.commercial_partner_id.id,
                    'product_id': line.product_id.id,
                    'product_uom_id': line.product_uom_id.id,
                    'quantity': line.quantity,
                    'price_unit': price_unit,
                    'debit': balance < 0.0 and -balance or 0.0,
                    'credit': balance > 0.0 and balance or 0.0,
                    'account_id': debit_interim_account.id,
                    # TODO: Buscar el campo que reemplaza a exclude_from_invoice_tab en V16, aparce 3 veces en el código
                    # By simplicity, and also because it makes more sense, some boolean fields
                    # have been merged into `display_type`:
                    # * `is_rounding_line`
                    # * `exclude_from_invoice_tab`
                    # * `is_anglo_saxon_line`
                    # 'exclude_from_invoice_tab': True,
                    # 'is_anglo_saxon_line': True,
                    'display_type': 'cogs',
                })

                # Add expense account line.
                lines_vals_list.append({
                    'name': line.name[:64],
                    'move_id': move.id,
                    'partner_id': move.commercial_partner_id.id,
                    'product_id': line.product_id.id,
                    'product_uom_id': line.product_uom_id.id,
                    'quantity': line.quantity,
                    'price_unit': -price_unit,
                    'debit': balance > 0.0 and balance or 0.0,
                    'credit': balance < 0.0 and -balance or 0.0,
                    'account_id': credit_expense_account.id,
                    # TODO: No existe clos sig. campos en v16, reemplaarlos
                    # 'analytic_account_id': line.analytic_account_id.id,
                    # 'analytic_tag_ids': [(6, 0, line.analytic_tag_ids.ids)],
                    # 'exclude_from_invoice_tab': True,
                    # 'is_anglo_saxon_line': True,
                    'display_type': 'cogs',
                })
        return lines_vals_list

    def _recompute_payment_terms_lines(self):
        ''' Compute the dynamic payment term lines of the journal entry.'''
        self.ensure_one()
        self = self.with_company(self.company_id)
        in_draft_mode = self != self._origin
        today = fields.Date.context_today(self)
        self = self.with_company(self.journal_id.company_id)

        def _get_payment_terms_computation_date(self):
            ''' Get the date from invoice that will be used to compute the payment terms.
            :param self:    The current account.move record.
            :return:        A datetime.date object.
            '''
            if self.invoice_payment_term_id:
                return self.invoice_date or today
            else:
                return self.invoice_date_due or self.invoice_date or today

        def _get_payment_terms_account(self, payment_terms_lines):
            ''' Get the account from invoice that will be set as receivable / payable account.
            :param self:                    The current account.move record.
            :param payment_terms_lines:     The current payment terms lines.
            :return:                        An account.account record.
            '''
            if payment_terms_lines:
                # Retrieve account from previous payment terms lines in order to allow the user to set a custom one.
                return payment_terms_lines[0].account_id
            elif self.partner_id:
                # Retrieve account from partner.
                if self.is_sale_document(include_receipts=True):
                    use_bridge_accounts = self.company_id.use_bridge_accounts
                    if use_bridge_accounts and self.is_multi_pos_order_invoice:
                        return self.company_id.bridge_expense_account_id
                    else:
                        return self.partner_id.property_account_receivable_id
                else:
                    return self.partner_id.property_account_payable_id
            else:
                # Search new account.
                domain = [
                    ('company_id', '=', self.company_id.id),
                    # v15 ('internal_type', '=', 'receivable' if self.move_type in ('out_invoice', 'out_refund', 'out_receipt') else 'payable'),
                ]
                # v15 'internal_type', '=', 'receivable'  v16 account_type in ('asset_receivable','liability_payable')
                # v15 'internal_type', '=', 'payable'     v16 account_type in ('asset_cash', 'liability_credit_card')
                if self.move_type in ('out_invoice', 'out_refund', 'out_receipt'):
                    domain.append(('account_type', 'in', ('asset_receivable','liability_payable')))
                else:
                    domain.append(('account_type', 'in', ('asset_cash', 'liability_credit_card')))

                return self.env['account.account'].search(domain, limit=1)

        def _compute_payment_terms(self, date, total_balance, total_amount_currency):
            ''' Compute the payment terms.
            :param self:                    The current account.move record.
            :param date:                    The date computed by '_get_payment_terms_computation_date'.
            :param total_balance:           The invoice's total in company's currency.
            :param total_amount_currency:   Thedate_maturity invoice's total in invoice's currency.
            :return:                        A list <to_pay_company_currency, to_pay_invoice_currency, due_date>.
            '''
            if self.invoice_payment_term_id:
                to_compute = self.invoice_payment_term_id.compute(total_balance, date_ref=date, currency=self.company_id.currency_id)
                if self.currency_id == self.company_id.currency_id:
                    # Single-currency.
                    return [(b[0], b[1], b[1]) for b in to_compute]
                else:
                    # Multi-currencies.
                    to_compute_currency = self.invoice_payment_term_id.compute(total_amount_currency, date_ref=date, currency=self.currency_id)
                    return [(b[0], b[1], ac[1]) for b, ac in zip(to_compute, to_compute_currency)]
            else:
                return [(fields.Date.to_string(date), total_balance, total_amount_currency)]

        def _compute_diff_payment_terms_lines(self, existing_terms_lines, account, to_compute):
            ''' Process the result of the '_compute_payment_terms' method and creates/updates corresponding invoice lines.
            :param self:                    The current account.move record.
            :param existing_terms_lines:    The current payment terms lines.
            :param account:                 The account.account record returned by '_get_payment_terms_account'.
            :param to_compute:              The list returned by '_compute_payment_terms'.
            '''
            # As we try to update existing lines, sort them by due date.
            existing_terms_lines = existing_terms_lines.sorted(lambda line: line.date_maturity or today)
            existing_terms_lines_index = 0

            # Recompute amls: update existing line or create new one for each payment term.
            new_terms_lines = self.env['account.move.line']
            for date_maturity, balance, amount_currency in to_compute:
                currency = self.journal_id.company_id.currency_id
                if currency and currency.is_zero(balance) and len(to_compute) > 1:
                    continue

                if existing_terms_lines_index < len(existing_terms_lines):
                    # Update existing line.
                    candidate = existing_terms_lines[existing_terms_lines_index]
                    existing_terms_lines_index += 1
                    candidate.update({
                        'date_maturity': date_maturity,
                        'amount_currency': -amount_currency,
                        'debit': balance < 0.0 and -balance or 0.0,
                        'credit': balance > 0.0 and balance or 0.0,
                    })
                else:
                    # Create new line.
                    create_method = in_draft_mode and self.env['account.move.line'].new or self.env['account.move.line'].create
                    values = {
                        'name': self.payment_reference or '',
                        'debit': balance < 0.0 and -balance or 0.0,
                        'credit': balance > 0.0 and balance or 0.0,
                        'quantity': 1.0,
                        'amount_currency': -amount_currency,
                        'date_maturity': date_maturity,
                        'move_id': self.id,
                        'currency_id': self.currency_id.id,
                        'account_id': account.id,
                        'partner_id': self.commercial_partner_id.id,
                        # 'exclude_from_invoice_tab': True,
                        'display_type': 'cogs',
                    }
                    # JCT: if
                    if values['debit'] != 0.00 or values['credit'] != 0.00:
                        candidate = create_method(values)
                    else:
                        candidate = False
                if candidate:
                    new_terms_lines += candidate
                    if in_draft_mode:
                        candidate.update(candidate._get_fields_onchange_balance(force_computation=True))
            return new_terms_lines

        existing_terms_lines = self.line_ids.filtered(lambda line: line.account_id.user_type_id.type in ('receivable', 'payable'))
        others_lines = self.line_ids.filtered(lambda line: line.account_id.user_type_id.type not in ('receivable', 'payable'))
        company_currency_id = (self.company_id or self.env.company).currency_id
        total_balance = sum(others_lines.mapped(lambda l: company_currency_id.round(l.balance)))
        total_amount_currency = sum(others_lines.mapped('amount_currency'))

        if not others_lines:
            self.line_ids -= existing_terms_lines
            return

        computation_date = _get_payment_terms_computation_date(self)
        account = _get_payment_terms_account(self, existing_terms_lines)
        to_compute = _compute_payment_terms(self, computation_date, total_balance, total_amount_currency)
        new_terms_lines = _compute_diff_payment_terms_lines(self, existing_terms_lines, account, to_compute)

        # Remove old terms lines that are no longer needed.
        self.line_ids -= existing_terms_lines - new_terms_lines

        if new_terms_lines:
            self.payment_reference = new_terms_lines[-1].name or ''
            self.invoice_date_due = new_terms_lines[-1].date_maturity

    # TODO: Reemplazo de override, pero no fuuncionó, marca error:
    # You can only set an account having the receivable type on payment terms lines for customer invoice.
    # def _recompute_payment_terms_lines(self):
    #     super(AccountMove, self)._recompute_payment_terms_lines()

    #     if self.is_sale_document(include_receipts=True):
    #         use_bridge_accounts = self.company_id.use_bridge_accounts
    #         for line_id in self.line_ids:
    #             if use_bridge_accounts and line_id.account_id == self.partner_id.property_account_receivable_id:
    #                 #if line_id.debit == 0.00 and line_id.credit == 0.00:
    #                 line_id.account_id = self.company_id.bridge_expense_account_id


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    l10n_mx_edi_identification_number = fields.Char(
        string='Identification #',
        help="In this field, the folio or transaction number of the transaction vouchers with "
        "the general public must be recorded.")

        
    def _get_computed_account(self):
        self.ensure_one()
        result = super(AccountMoveLine, self)._get_computed_account()

        use_bridge_accounts = self.company_id.use_bridge_accounts
        if use_bridge_accounts and self.move_id.is_multi_pos_order_invoice:
            return self.company_id.bridge_income_account_id
        else:
            return result


    @api.model
    def _get_default_tax_account(self, repartition_line):
        result = super(AccountMoveLine, self)._get_default_tax_account(repartition_line)

        use_bridge_accounts = self.company_id.use_bridge_accounts
        if use_bridge_accounts and self.move_id.is_multi_pos_order_invoice:
            # account = False
            account = self.company_id.bridge_income_account_id
        else:
            account = result
        return account


    # 1. You cannot use taxes on lines with an Off-Balance account
    # 2. Seleccionar cuentas "Fuera de balance"
    # 3. Traducción
    @api.constrains('account_id', 'tax_ids', 'tax_line_id', 'reconciled')
    def _check_off_balance(self):
        for line in self:
            if line.account_id.internal_group == 'off_balance':
                if not self.company_id.use_bridge_accounts or not line.move_id.is_multi_pos_order_invoice:
                    if any(a.internal_group != line.account_id.internal_group for a in line.move_id.line_ids.account_id):
                        raise UserError(_('If you want to use "Off-Balance Sheet" accounts, all the accounts of the journal entry must be of this type'))
                    if line.tax_ids or line.tax_line_id:
                        raise UserError(_('You cannot use taxes on lines with an Off-Balance account'))
                    if line.reconciled:
                        raise UserError(_('Lines from "Off-Balance Sheet" accounts cannot be reconciled'))

