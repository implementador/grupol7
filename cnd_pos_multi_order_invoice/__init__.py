# -*- coding: utf-8 -*-
from . import models
from . import wizard
from . import report
from odoo import api, SUPERUSER_ID, _


def pre_init_check(cr):
    from odoo.service import common
    from odoo.exceptions import UserError
    version_info = common.exp_version()
    server_serie = version_info.get('server_serie')
    if '16.' not in server_serie:
        raise UserError(_('This module support Odoo series 16.x, found %s.') %
                        server_serie)
    return True

def post_init_hook(cr, registry):
    env = api.Environment(cr, SUPERUSER_ID, {})
    
    zip = env.ref('base.main_company').zip
    if zip:
        partner_general_public = env.ref('cnd_pos_multi_order_invoice.res_partner_general_public')
        partner_general_public.write({'zip': zip})
    return True
