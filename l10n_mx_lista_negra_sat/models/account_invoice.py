# -*- coding: utf-8 -*-

from odoo import models, fields, api

class AccountMove(models.Model):
    _inherit = "account.move"

    is_vat = fields.Boolean('Is RFC',compute='check_vat')

    @api.depends('partner_id')
    def check_vat(self):
        for record in self:
            if record.partner_id and record.partner_id.vat:
                vat_invoices = self.env['lista.negra.sat'].search([('vat','=',record.partner_id.vat)])
                if vat_invoices:
                    record.is_vat=True;
                else:
                    record.is_vat=False;
            else:
                record.is_vat=False;

    def action_confirm_custom(self):
        return super(AccountMove,self).action_post()
