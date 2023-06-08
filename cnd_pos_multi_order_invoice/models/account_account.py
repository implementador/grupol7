# -*- coding: utf-8 -*-
from odoo import models, api

# v15 'internal_type', '=', 'receivable'  v16 account_type in ('asset_receivable','liability_payable')
# v15 'internal_type', '=', 'payable'     v16 account_type in ('asset_cash', 'liability_credit_card')

class AccountAccount(models.Model):
    _inherit = 'account.account'

    @api.constrains('reconcile', 'internal_group', 'tax_ids')
    def _constrains_reconcile(self):
        return True

    @api.onchange('user_type_id')
    def _onchange_user_type_id(self):
        self.reconcile = self.account_type in ('liability_payable', 'asset_receivable','liability_payable')
        # if self.account_type in 'liquidity':
        if self.account_type in ('asset_cash', 'liability_credit_card'):
            self.reconcile = False
        elif self.internal_group == 'off_balance' and not self.tax_ids:
            self.tax_ids = self.company_id.account_purchase_tax_id
        elif self.internal_group == 'income' and not self.tax_ids:
            self.tax_ids = self.company_id.account_sale_tax_id
        elif self.internal_group == 'expense' and not self.tax_ids:
            self.tax_ids = self.company_id.account_purchase_tax_id