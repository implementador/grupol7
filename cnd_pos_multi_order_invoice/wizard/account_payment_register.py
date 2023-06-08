# -*- coding: utf-8 -*-
from odoo import models, api


class AccountPaymentRegister(models.TransientModel):
    _inherit = 'account.payment.register'

    @api.model 
    def default_get(self, fields_list):
        if self._context.get('active_model') == 'account.move':
            lines = self.env['account.move'].browse(self._context.get('active_ids', [])).line_ids
        elif self._context.get('active_model') == 'account.move.line':
            lines = self.env['account.move.line'].browse(self._context.get('active_ids', []))

        # Publicar la factura por defecto
        use_bridge_accounts = lines[0].company_id.use_bridge_accounts
        if use_bridge_accounts:
            lines[0].company_id.bridge_income_account_id.write({
                'user_type_id': lines[0].env.ref('account.data_account_type_revenue').id,
                'reconcile': True,
            })
            lines[0].company_id.bridge_expense_account_id.write({
                'user_type_id': lines[0].env.ref('account.data_account_type_receivable').id,
                'reconcile': True,
            })
        return super().default_get(fields_list)

    def _create_payments(self):
        res = super()._create_payments()
        for payment in res:
            lines = payment.move_id.line_ids
            company_id = lines[0].company_id
            if company_id.use_bridge_accounts and company_id.bridge_expense_payment_account_id:
                line_expense_id = lines.filtered(lambda line: line.account_id.id == company_id.bridge_expense_account_id.id)
                if line_expense_id:
                    for line in line_expense_id:
                        self.env.cr.execute('''UPDATE account_move_line SET account_id=%s WHERE id=%s;''' % (company_id.bridge_expense_payment_account_id.id, line.id))
        return res
