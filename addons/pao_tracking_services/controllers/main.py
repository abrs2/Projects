
from crypt import methods
from locale import currency
from odoo import http, _, fields
from odoo.http import request
from openerp.api import Environment as Env
from odoo.tools import html2plaintext, DEFAULT_SERVER_DATETIME_FORMAT as dtf
from odoo.tools.misc import get_lang
from logging import getLogger
from odoo.addons.web.controllers.main import content_disposition
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager, get_records_pager
from functools import reduce
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager, get_records_pager
import symbol

_logger = getLogger(__name__)


class PaoTrackingServices(http.Controller):

    @http.route('/pao/tracking/my/quotes', type='json', auth="user")
    def track_my_quotes(self, page = 1 , item_per_page = 10, **kw):

        partner = request.env.user.partner_id

        SaleOrder = request.env['sale.order']
        domain = self._get_quotation_domain(partner)

        # default sortby order

        sort_order = 'date_order desc'

        # count for pager
        quotation_count = SaleOrder.search_count(domain)

        # make pager
        pager = portal_pager(

            url="/pao/tracking/my/quotes",
            total=quotation_count,
            page=page,
            step=item_per_page

        )

        # search the count to display, according to the pager data
        quotations = SaleOrder.search(
            domain, order=sort_order, limit=item_per_page, offset=pager['offset'])
        
        result = quotations.read(['name','payment_term_id', 'date_order','validity_date','is_expired','amount_tax','amount_untaxed','amount_total'])

        result[0]['currency_unit_label']=quotations.pricelist_id.sudo().currency_id.currency_unit_label
        result[0]['symbol']=quotations.pricelist_id.sudo().currency_id.symbol

        return result

    @http.route('/pao/tracking/my/quotes/detail', type='json', auth="user")
    def track_quotation_detail(self, order_id, **kw):

        partner = request.env.user.partner_id

        SaleOrder = request.env['sale.order']

        domain = [('id','=',order_id)]

        order = SaleOrder.search(domain)

        services=[]
        

        for line in order.order_line:
            taxes= []
            for tax in line.tax_id:
                taxes.append(tax.name)
            services.append(
                {
                    "taxes": taxes, 
                    "productId": line.product_id.id,
                    "name":line.name,
                    "productQty": line.product_uom_qty,
                    "priceUnit": line.price_unit,
                    "priceSubtotal": line.price_subtotal,
                    "displayType": line.display_type

                }
            )
        
        return services

    def _get_quotation_domain(self,partner):
        return [
            ('message_partner_ids', 'child_of', [
             partner.commercial_partner_id.id]),
            ('state', '=', 'sent')
        ]

    