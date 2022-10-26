from odoo import fields,models,api

class PaoAuditorias(models.Model):
    
    _name = "pao.auditorias"
    _description = "Pao Auditorias"
    _rec_name = 'numero'

    numero = fields.Char("Numero de Auditoria",required=True,copy=False)
    cliente = fields.Many2one("res.partner",string="Cliente",required=True)
    pais = fields.Many2one("res.country",string="País de Auditoría")
    estado = fields.Many2one('res.country.state',string="Estado de Auditoría", store=True)
    ciudad = fields.Char('Ciudad de Auditoría')


        