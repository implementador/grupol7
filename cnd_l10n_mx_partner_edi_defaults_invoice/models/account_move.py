# -*- coding: utf-8 -*-
from odoo import api, models, fields, _
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = "account.move"

    l10n_mx_edi_usage = fields.Selection(
        selection_add=[('S01', 'No tax effects')])

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        '''Set the payment l10n_mx_edi_usage on the sale order as the first of the selected partner.
        '''
        # OVERRIDE
        res = super(AccountMove, self)._onchange_partner_id()
        if self.partner_id:
            # EDI Usage from Partner
            if self.partner_id.commercial_partner_id.is_company and \
                    self.partner_id.commercial_partner_id.l10n_mx_edi_usage:
                self.l10n_mx_edi_usage = self.partner_id.commercial_partner_id.l10n_mx_edi_usage

            # Method from Partner
            payment_term_immediate = self.env.ref('account.account_payment_term_immediate', raise_if_not_found=False)
            if self.invoice_payment_term_id != payment_term_immediate:
                self.l10n_mx_edi_payment_method_id = self.env.ref(
                    'l10n_mx_edi.payment_method_otros', raise_if_not_found=False)
            elif self.partner_id.commercial_partner_id.is_company and \
                    self.partner_id.commercial_partner_id.l10n_mx_edi_payment_method_id:
                self.l10n_mx_edi_payment_method_id = self.partner_id.commercial_partner_id.l10n_mx_edi_payment_method_id
        return res

    @api.onchange('invoice_payment_term_id')
    def _onchange_invoice_payment_term_id(self):
        l10n_mx_edi_payment_method_id = self.l10n_mx_edi_payment_method_id

        payment_term_immediate = self.env.ref('account.account_payment_term_immediate', raise_if_not_found=False)
        if self.invoice_payment_term_id != payment_term_immediate:
            l10n_mx_edi_payment_method_id = self.env.ref('l10n_mx_edi.payment_method_otros', raise_if_not_found=False)
        elif self.partner_id.commercial_partner_id.l10n_mx_edi_payment_method_id:
            l10n_mx_edi_payment_method_id = self.partner_id.commercial_partner_id.l10n_mx_edi_payment_method_id

        self.l10n_mx_edi_payment_method_id = l10n_mx_edi_payment_method_id

    def _post(self, soft=True):
        # OVERRIDE

        # Validar que cuando el "Método de pago" NO SEA inmediato, la "Forma de Pago" SEA "Por definir"
        payment_term_immediate = self.env.ref('account.account_payment_term_immediate', raise_if_not_found=False)
        payment_method_to_define = self.env.ref('l10n_mx_edi.payment_method_otros', raise_if_not_found=False)
        for move in self:
            if move.move_type == 'out_invoice':
                if (move.invoice_payment_term_id != payment_term_immediate and
                   move.l10n_mx_edi_payment_method_id != payment_method_to_define):
                    raise UserError(
                        _('Cuando el "Plazo de Pago" sea diferente a "Pago Inmediato", la "Forma de Pago" deberá ser "Por definir".'))
                    # _('When the Payment Term is different from "Immediate Payment", the Payment Way must be "To be defined".'))
                # Validar que cuando el "Método de pago" SEA inmediato, la "Forma de Pago" NO SEA "Por definir"
                elif (move.invoice_payment_term_id == payment_term_immediate and
                      move.l10n_mx_edi_payment_method_id == payment_method_to_define):
                    raise UserError(
                        _('Cuando el "Plazo de Pago" es "Pago Inmediato", la "Forma de Pago" debe ser diferente a "Por definir".'))
                    # _('When the Payment Term is "Immediate Payment", the Payment Way must different from "To be defined".'))

        to_post = super()._post(soft=soft)
        return to_post
