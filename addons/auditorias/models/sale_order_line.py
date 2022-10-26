from odoo import fields,models

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'


    auditoria_ids = fields.Many2one('pao.auditorias', string='Auditorias',store=True)