# -*- coding: utf-8 -*-
from odoo import models


class AccountEdiFormat(models.Model):
    _inherit = 'account.edi.format'

    def _is_required_for_invoice(self, invoice):
        # OVERRIDE
        self.ensure_one()
        if self.code != 'cfdi_3_3' and invoice.l10n_mx_edi_sign_required is True:
            return super()._is_required_for_invoice(invoice)

        # Determine on which invoices the Mexican CFDI must be generated.
        return invoice.move_type in ('out_invoice', 'out_refund') and invoice.country_code == 'MX' \
            and invoice.l10n_mx_edi_sign_required

    def _is_required_for_payment(self, move):
        # OVERRIDE
        self.ensure_one()

        sign_not_required = (
            move.payment_id.reconciled_invoice_ids.filtered(lambda i: i.l10n_mx_edi_payment_sign_required is False))

        if self.code != 'cfdi_3_3' and sign_not_required is False:
            return super()._is_required_for_payment(move)

        # Determine on which invoices the Mexican CFDI must be generated.
        if move.country_code != 'MX' or sign_not_required:
            return False

        if (move.payment_id or move.statement_line_id).l10n_mx_edi_force_generate_cfdi:
            return True

        reconciled_invoices = move._get_reconciled_invoices()
        return 'PPD' in reconciled_invoices.mapped('l10n_mx_edi_payment_policy')


    def _post_invoice_edi(self, invoices):
        # EXTENDS l10n_mx_edi - rename attachment
        edi_result = super()._post_invoice_edi(invoices)
        if self.code != 'cfdi_3_3':
            return edi_result
        for invoice in invoices:
            if edi_result[invoice].get('attachment', False):
                cfdi_filename = ('%s-%s-MX-Invoice-4.0.xml' % (invoice.journal_id.code, invoice.payment_reference)).replace('/', '')
                edi_result[invoice]['attachment'].name = cfdi_filename
        return edi_result

