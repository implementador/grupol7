from odoo import models, fields

class ProductTemplate(models.Model):
    _inherit = "product.template"

    x_motor_watts = fields.Char("Motor (W)")
    x_model_year  = fields.Char("Año")
    x_color_name  = fields.Char("Color")
