from odoo import models,fields

class EstatePropertyOffer(models.Model):
    _name = 'estate.property.offer'

    price = fields.Float("Price")
    validity = fields.Integer("Validity",default=7)
    date_deadline = fields.Date("Date Deadline")
    status = fields.Selection(string="Status",selection=[('accepted','Accepted'),('refused','Refused')],copy=False,)
    partner_id = fields.Many2one("res.partner",string="Partner")
    property_id = fields.Many2one("estate.property",string="Property")