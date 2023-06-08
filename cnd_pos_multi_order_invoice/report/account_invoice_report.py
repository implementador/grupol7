# -*- coding: utf-8 -*-
from odoo import fields, models


class AccountInvoiceReport(models.Model):
    _inherit = "account.invoice.report"

    is_multi_pos_order_invoice = fields.Boolean(readonly=True)

    def _select(self):
        return super(AccountInvoiceReport, self)._select() + ",move.is_multi_pos_order_invoice"

    def _group_by(self):
        return super(AccountInvoiceReport, self)._group_by() + ",move.is_multi_pos_order_invoice"
