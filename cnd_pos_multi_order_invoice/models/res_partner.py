# -*- coding: utf-8 -*-
from odoo import models, fields


class ResPartner(models.Model):
    _inherit = 'res.partner'

    l10n_mx_edi_sign_required = fields.Boolean(
        string='Sign CFDI?',
        default=True,
        help='If this field is active, the invoices for this customer by '
        'default will be signed.')
