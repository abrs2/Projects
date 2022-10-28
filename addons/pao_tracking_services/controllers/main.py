
from crypt import methods
import math
from odoo import http, _, fields
from odoo.http import request
from odoo.tools import html2plaintext, DEFAULT_SERVER_DATETIME_FORMAT as dtf
from odoo.tools.misc import get_lang
from logging import getLogger
from odoo.addons.web.controllers.main import content_disposition
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager, get_records_pager
from functools import reduce
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager, get_records_pager

_logger = getLogger(__name__)


class PaoTrackingServices(http.Controller):

    # Método que toma como parámetros un número de página y un número de cotizaciones por página
    # Regresa una lista con el valor del conteo de páginas y las cotizaciones del numero de página solicitada.
    @http.route('/pao/tracking/my/quotes', type='json', auth="user")
    def track_my_quotes(self, page=1, item_per_page=10, **kw):

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

        sales = []

        for quote in quotations:
            sales.append(
                {
                    "id": quote.id,
                    "name": quote.name,
                    "paymentTermId": quote.payment_term_id.sudo().name,
                    "dateOrder": quote.date_order,
                    "validityDate": quote.validity_date,
                    "isExpired": quote.is_expired,
                    "amountTax": quote.amount_tax,
                    "amountUntaxed": quote.amount_untaxed,
                    "amountTotal": quote.amount_total,
                    "currencyLabel": quote.pricelist_id.sudo().currency_id.currency_unit_label,
                    "currencySymbol": quote.pricelist_id.sudo().currency_id.symbol,
                    "state": quote.state,
                    "accessToken": quote.access_token
                }
            )

        page_count = int(math.ceil(float(quotation_count)/item_per_page))
        response = {"pageCount": page_count, "detail": sales}

        return response
   
    # Método que toma como parámetro el id de una orden de venta convertida en cotización.
    # Regresa una lista con los detalles de la cotización solicitada.
    @http.route('/pao/tracking/my/quotes/detail', type='json', auth="user")
    def track_quotation_detail(self, order_id, **kw):

        partner = request.env.user.partner_id

        SaleOrder = request.env['sale.order']

        domain = [('id', '=', order_id)]

        order = SaleOrder.search(domain)

        services = []

        for line in order.order_line:
            taxes = []
            for tax in line.tax_id:
                taxes.append(tax.name)
            services.append(
                {
                    "id": line.id,
                    "taxes": taxes,
                    "productId": line.product_id.id,
                    "name": line.name,
                    "productQty": line.product_uom_qty,
                    "priceUnit": line.price_unit,
                    "priceSubtotal": line.price_subtotal,
                    "displayType": line.display_type

                }
            )

        return services

    # Método que toma como parámetros el nombre del modelo y el id del documento.
    # Regresa una lista con todo el historial de mensajes relacionados al documento que no son del sistema.
    @http.route('/pao/tracking/my/messages', type='json', auth="user")
    def track_messages(self, document_model, document_id, **kw):

        partner = request.env.user.partner_id

        domain = [('model', '=', document_model), ('res_id', '=', document_id)]
        sort_order = 'date asc'
        messages = request.env["mail.message"].sudo().search(domain, order=sort_order)

        defined_messages = []
        count = 0

        for message in messages:

            if (not message.subtype_id.sudo().internal) and (not message.is_internal) and (message.message_type in ['email', 'comment']):

                defined_messages.append(
                    {
                        "subject": message.subject,
                        "date": message.date,
                        "author": message.author_id.sudo().name,
                        "from": message.email_from,
                        "body": message.body,
                    }
                )
                attachments = []

                for attachment in message.attachment_ids:
                    attachments.append(
                        {
                            "name": attachment.name,
                            "localUrl": attachment.local_url,
                            "type": attachment.type,
                            "mimetype": attachment.mimetype
                        }
                    )

                defined_messages[count]["attachments"]=attachments
                count+=1

        return defined_messages

    def _get_quotation_domain(self, partner):
        return [
            ('message_partner_ids', 'child_of', [
             partner.commercial_partner_id.id]),
            ('state', 'in', ['sent', 'sale', 'done'])
        ]

