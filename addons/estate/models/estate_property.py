
from datetime import date
from dateutil.relativedelta import relativedelta
from odoo import models,fields,api

def dateInThreeMonths():
    now= date.today()
    dateAfter = now+ relativedelta(months=3)
    year = dateAfter.strftime("%Y")
    month = dateAfter.month
    day = dateAfter.strftime("%d")

    fecha=year+'-'+str(month)+'-'+day

    return fecha
    

class EstateProperty(models.Model):
    _name = 'estate.property'
    _description = "CRM Estate Property"

    name = fields.Char('Property Name',default="Unknown",required=True,translate=True)
    tag_ids = fields.Many2many("estate.property.tag",string="Property Tags")
    property_type_id = fields.Many2one("estate.property.type",string="Property Type")
    description =fields.Text('Description')
    postcode = fields.Char('Postcode',required=True)
    date_availability = fields.Date('Available From',default=dateInThreeMonths(),copy=False)
    expected_price = fields.Float('Expected Price',required=True)
    selling_price = fields.Float('Selling Price',readonly=True, copy=False)
    bedrooms = fields.Integer('Bedrooms', default=2)
    living_area = fields.Integer('Living Area (sqm)')
    facades = fields.Integer('Facades')
    garage = fields.Boolean('Garage')
    garden = fields.Boolean('Garden')
    garden_area = fields.Integer('Garden Area')
    total_area = fields.Integer("Total Area(sqm)",compute="_compute_area",readonly=True)
    garden_orientation = fields.Selection(
        string='Garden Orientation',
        selection=[('please choose one','Please Choose One'),('north','North'), ('south','South'), ('east','East'),('west', 'West')],
        help="Garden Orientation is used to indicate where the garden is", default= 'please choose one',
        )    
    active= fields.Boolean('Active',default=True) 
    state = fields.Selection(
        string='State',
        selection=[('new','New'),('offer received','Offer Received'), ('offer accepted','Offer Accepted'),
        ('sold','Sold'), ('canceled','Canceled')],
        copy=False,required=True,default='new',
    )

    salesMan = fields.Many2one("res.users",string="Salesman",default=lambda self: self.env.user)
    buyer = fields.Many2one("res.partner",string="Buyer",copy=False)

    offer_ids = fields.One2many("estate.property.offer","property_id")

    best_price= fields.Float("Best Price",compute = "_compute_best_price",readonly=True)

    @api.depends("living_area","garden_area")
    def _compute_area(_self):
        for rec in _self:
            rec.total_area = rec.garden_area+rec.living_area

    @api.depends('offer_ids.price')
    def _compute_best_price(self):
        for record in self:
            record.best_price = max(offer.price for offer in record.offer_ids)
            

