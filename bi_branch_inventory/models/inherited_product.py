# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _


class ProductTemplateIn(models.Model):
    _inherit = 'product.template'

    @api.model
    def default_get(self, default_fields):
        res = super(ProductTemplateIn, self).default_get(default_fields)
        context = self._context
        current_uid = context.get('uid')
        user = self.env['res.users'].browse(current_uid)
        if user.branch_id:
            res.update({
                'branch_id': user.branch_id.id or False
            })
        return res

    branch_id = fields.Many2one('res.branch', string="Branch")
