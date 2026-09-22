from odoo import models, fields

class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    # Guarda en la línea lo que está en el producto (reportable)
    x_motor_watts = fields.Char(related="product_id.product_tmpl_id.x_motor_watts", store=True)
    x_model_year  = fields.Char(related="product_id.product_tmpl_id.x_model_year",  store=True)
    x_color_name  = fields.Char(related="product_id.product_tmpl_id.x_color_name",  store=True)
