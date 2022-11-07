
from crypt import methods
import math
from odoo import http, tools, _, SUPERUSER_ID
from odoo.http import request
import json
from odoo.tools import consteq, plaintext2html
from odoo.tools.misc import get_lang
from odoo.exceptions import AccessDenied, AccessError, MissingError, UserError
from logging import getLogger
from odoo.addons.web.controllers.main import content_disposition
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager, get_records_pager
from functools import reduce
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager, get_records_pager
import base64

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
    
    def _get_quotation_domain(self, partner):
        return [
            ('message_partner_ids', 'child_of', [
             partner.commercial_partner_id.id]),
            ('state', 'in', ['sent', 'sale', 'done'])
        ]

    # Método que toma como parámetros el nombre del modelo y el id del documento.
    # Regresa una lista con todo el historial de mensajes relacionados al documento que no son del sistema.
    @http.route('/pao/tracking/my/messages', type='json', auth="user")
    def track_messages(self, document_model, document_id, **kw):

        partner = request.env.user.partner_id

        domain = [('model', '=', document_model), ('res_id', '=', document_id)]
        sort_order = 'date asc'
        messages = request.env["mail.message"].sudo().search(
            domain, order=sort_order)

        defined_messages = []
        count = 0
        url = request.env['ir.config_parameter'].sudo(
        ).get_param('web.base.url')  # BASE URL
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
                            "localUrl": url+attachment.local_url,
                            "type": attachment.type,
                            "mimetype": attachment.mimetype
                        }
                    )

                defined_messages[count]["attachments"] = attachments
                count += 1

        return defined_messages
    def _pao_tracking_post_has_content(self, message, attachment_ids=None):
        return bool(message) or bool(attachment_ids)

    def _document_check_access(self, model_name, document_id, access_token=None):
        """Check if current user is allowed to access the specified record.
        :param str model_name: model of the requested record
        :param int document_id: id of the requested record
        :param str access_token: record token to check if user isn't allowed to read requested record
        :return: expected record, SUDOED, with SUPERUSER context
        :raise MissingError: record not found in database, might have been deleted
        :raise AccessError: current user isn't allowed to read requested document (and no valid token was given)
        """
        document = request.env[model_name].browse([document_id])
        document_sudo = document.with_user(SUPERUSER_ID).exists()
        if not document_sudo:
            raise MissingError(_("This document does not exist."))
        try:
            document.check_access_rights('read')
            document.check_access_rule('read')
        except AccessError:
            if not access_token or not document_sudo.access_token or not consteq(document_sudo.access_token, access_token):
                raise
        return document_sudo

    def _pao_post_check_attachments(self, attachment_ids, attachment_tokens):
        if len(attachment_tokens) != len(attachment_ids):
            raise UserError(_("An access token must be provided for each attachment."))
        for (attachment_id, access_token) in zip(attachment_ids, attachment_tokens):
            try:
                CustomerPortal._document_check_access(self, 'ir.attachment', attachment_id, access_token)
            except (AccessError, MissingError):
                raise UserError(_("The attachment %s does not exist or you do not have the rights to access it.", attachment_id))
                
    @http.route('/pao/tracking/attachment/add', type='http', auth='user')
    def attachment_add(self, name, file, res_model, res_id, access_token=None, **kwargs):
        
        try:
            self._document_check_access(res_model, int(res_id), access_token=access_token)
        except (AccessError, MissingError) as e:
            raise UserError(_("The document does not exist or you do not have the rights to access it."))
        
        IrAttachment = request.env['ir.attachment']
        access_token = False
         

        if not request.env.user.share:
            IrAttachment = IrAttachment.sudo().with_context(binary_field_real_user=IrAttachment.env.user)
            access_token = IrAttachment._generate_access_token()
    
        attachment = IrAttachment.create({
            'name': name,
            'datas': base64.b64encode(file.read()),
            'res_model': 'mail.compose.message',
            'res_id': 0,
            'access_token': access_token,
        })
        
        
        data= attachment.read(['id', 'name', 'mimetype', 'file_size', 'access_token']),
        
        #data = [name, file, res_model, res_id, access_token]

        return json.dumps(data)
    
    @http.route(['/pao/tracking/post/message'], type='json', methods=['POST'], auth='user')
    def pao_track_message(self, res_model, res_id, message, attachment_ids=None, attachment_tokens=None, **kw):
        partner = request.env.user.partner_id
        if not self._pao_tracking_post_has_content( message,attachment_ids=attachment_ids):
            return

        
        self._pao_post_check_attachments(attachment_ids or [], attachment_tokens or [])
        
        
        if message:
            message = plaintext2html(message)
        post_values = {
            'res_model': res_model,
            'res_id': res_id,
            'message': message,
            'send_after_commit': False,
            'attachment_ids': False,  # will be added afterward
        }

        defaulId = self._message_post(res_model,res_id,message,partner)
      
        
        result = {'default_message_id': defaulId.id}
        #result.update({'default_message_id': message.id})
        
        if attachment_ids:
            # sudo write the attachment to bypass the read access
            # verification in mail message
            record = request.env[res_model].browse(res_id)
            message_values = {'res_id': res_id, 'model': res_model}
            attachments = record._message_post_process_attachments([], attachment_ids, message_values)

            if attachments.get('attachment_ids'):
                message.sudo().write(attachments)

            result.update({'default_attachment_ids': message.attachment_ids.sudo().read(['id', 'name', 'mimetype', 'file_size', 'access_token'])})
        
        return result

    def _message_post(self,res_model, res_id, message,partner, **kw):
        record = request.env[res_model].browse(int(res_id))
        _logger.error("entro")
        _logger.error(record)

        record.check_access_rights('read')
        record.check_access_rule('read')
        #_logger.error(record.check_access_rights('read'))
        #_logger.error(record.check_access_rule('read'))
        email_from = partner.email_formatted if partner.email else None
        
        message_post_args = dict(
            body=message,
            message_type=kw.pop('message_type', "comment"),
            subtype_xmlid=kw.pop('subtype_xmlid', "mail.mt_comment"),
            author_id=partner.id,
            **kw
        )
        
        if email_from:
            message_post_args['email_from'] = email_from
        
        _logger.error(message_post_args)
       
        return record.with_context(mail_create_nosubscribe=True).message_post(**message_post_args)
        
