# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, api, _


class ResUsers(models.Model):
    _inherit = 'res.users'

    is_allow_numpad=fields.Boolean("Allow Numpad")
    is_allow_payments = fields.Boolean('Allow Payments')
    is_allow_discount = fields.Boolean('Allow Discount')
    is_allow_qty = fields.Boolean('Allow Qty')
    is_edit_price = fields.Boolean('Allow Edit Price')
    is_allow_remove_orderline = fields.Boolean('Allow Remove Order Line')
    is_allow_customer_selection=fields.Boolean("Allow Customer Selection")
    is_allow_plus_minus_button=fields.Boolean("Allow +/- Button")

    @api.onchange('is_allow_numpad', 'is_allow_payments', 'is_allow_discount', 'is_allow_qty','is_edit_price','is_allow_remove_orderline', 'is_allow_customer_selection', 'is_allow_plus_minus_button')
    def _update_hr_settings(self):
        for user in self.with_context(active_test=False):
            user.employee_id.update({
                'is_allow_numpad': user.is_allow_numpad,
                'is_allow_payments': user.is_allow_payments,
                'is_allow_discount': user.is_allow_discount,
                'is_allow_qty': user.is_allow_qty,
                'is_allow_remove_orderline': user.is_allow_remove_orderline,
                'is_allow_customer_selection': user.is_allow_customer_selection,
                'is_allow_plus_minus_button': user.is_allow_plus_minus_button,
            })


class HrEmployeeBase(models.AbstractModel):
    _inherit = "hr.employee.base"

    is_allow_numpad=fields.Boolean("Allow Numpad")
    is_allow_payments = fields.Boolean('Allow Payments')
    is_allow_discount = fields.Boolean('Allow Discount')
    is_allow_qty = fields.Boolean('Allow Qty')
    is_edit_price = fields.Boolean('Allow Edit Price')
    is_allow_remove_orderline = fields.Boolean('Allow Remove Order Line')
    is_allow_customer_selection=fields.Boolean("Allow Customer Selection")
    is_allow_plus_minus_button=fields.Boolean("Allow +/- Button")


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    def open_employee_user(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_window',
                'res_model': 'res.users',
                'view_mode': 'form',
                'res_id': self.user_id.id,
                'target': 'current',
                }

class POSSession(models.Model):
    _inherit = 'pos.session'    

    def _loader_params_res_users(self):
        result = super()._loader_params_res_users()
        result['search_params']['fields'].extend(['company_id','lang','is_allow_numpad','is_allow_payments',
                'is_allow_discount','is_allow_qty','is_edit_price','is_allow_remove_orderline','is_allow_customer_selection',
                'is_allow_plus_minus_button'])
        return result


    def _loader_params_hr_employee(self):
        result = super()._loader_params_hr_employee()
        result['search_params']['fields'].extend(['is_allow_numpad','is_allow_payments','is_allow_discount','is_allow_qty',
            'is_edit_price','is_allow_remove_orderline','is_allow_customer_selection','is_allow_plus_minus_button'])
        return result