# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.
from . import models
from odoo import _


def pre_init_check(cr):
    from odoo.service import common
    from odoo.exceptions import UserError
    version_info = common.exp_version()
    server_serie = version_info.get('server_serie')
    if '16.' not in server_serie:
        raise UserError(_('This module support Odoo series 16.x, found %s.') %
                      server_serie)
    return True
