from odoo import fields,models

class SaleOrderLine(models.Model):
    _inherit = 'purchase.order.line'


    new_field = fields.Char(string='New Field',store=True)