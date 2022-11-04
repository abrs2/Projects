
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
        url= request.env['ir.config_parameter'].sudo().get_param('web.base.url') # BASE URL
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

                defined_messages[count]["attachments"]=attachments
                count+=1

        return defined_messages

    def _portal_post_has_content(self, res_model, res_id, message, attachment_ids=None, **kw):
        """ Tells if we can effectively post on the model based on content. """
        return bool(message) or bool(attachment_ids)

    def _portal_post_check_attachments(self, attachment_ids, attachment_tokens):
        if len(attachment_tokens) != len(attachment_ids):
            raise UserError(_("An access token must be provided for each attachment."))
        for (attachment_id, access_token) in zip(attachment_ids, attachment_tokens):
            try:
                CustomerPortal._document_check_access(self, 'ir.attachment', attachment_id, access_token)
            except (AccessError, MissingError):
                raise UserError(_("The attachment %s does not exist or you do not have the rights to access it.", attachment_id))

    def _portal_post_filter_params(self):
        return ['token', 'pid']
    

    def _message_post_helper(res_model, res_id, message, token='', _hash=False, pid=False, nosubscribe=True, **kw):
        """ Generic chatter function, allowing to write on *any* object that inherits mail.thread. We
            distinguish 2 cases:
                1/ If a token is specified, all logged in users will be able to write a message regardless
                of access rights; if the user is the public user, the message will be posted under the name
                of the partner_id of the object (or the public user if there is no partner_id on the object).
                2/ If a signed token is specified (`hash`) and also a partner_id (`pid`), all post message will
                be done under the name of the partner_id (as it is signed). This should be used to avoid leaking
                token to all users.
            Required parameters
            :param string res_model: model name of the object
            :param int res_id: id of the object
            :param string message: content of the message
            Optional keywords arguments:
            :param string token: access token if the object's model uses some kind of public access
                                using tokens (usually a uuid4) to bypass access rules
            :param string hash: signed token by a partner if model uses some token field to bypass access right
                                post messages.
            :param string pid: identifier of the res.partner used to sign the hash
            :param bool nosubscribe: set False if you want the partner to be set as follower of the object when posting (default to True)
            The rest of the kwargs are passed on to message_post()
        """
        record = request.env[res_model].browse(res_id)

        # check if user can post with special token/signed token. The "else" will try to post message with the
        # current user access rights (_mail_post_access use case).
        if token or (_hash and pid):
            pid = int(pid) if pid else False
            if _check_special_access(res_model, res_id, token=token, _hash=_hash, pid=pid):
                record = record.sudo()
            else:
                raise Forbidden()
        else:  # early check on access to avoid useless computation
            record.check_access_rights('read')
            record.check_access_rule('read')

        # deduce author of message
        author_id = request.env.user.partner_id.id if request.env.user.partner_id else False

        # Signed Token Case: author_id is forced
        if _hash and pid:
            author_id = pid
        # Token Case: author is document customer (if not logged) or itself even if user has not the access
        elif token:
            if request.env.user._is_public():
                # TODO : After adding the pid and sign_token in access_url when send invoice by email, remove this line
                # TODO : Author must be Public User (to rename to 'Anonymous')
                author_id = record.partner_id.id if hasattr(record, 'partner_id') and record.partner_id.id else author_id
            else:
                if not author_id:
                    raise NotFound()

        email_from = None
        if author_id and 'email_from' not in kw:
            partner = request.env['res.partner'].sudo().browse(author_id)
            email_from = partner.email_formatted if partner.email else None

        message_post_args = dict(
            body=message,
            message_type=kw.pop('message_type', "comment"),
            subtype_xmlid=kw.pop('subtype_xmlid', "mail.mt_comment"),
            author_id=author_id,
            **kw
        )

        # This is necessary as mail.message checks the presence
        # of the key to compute its default email from
        if email_from:
            message_post_args['email_from'] = email_from

        return record.with_context(mail_create_nosubscribe=nosubscribe).message_post(**message_post_args)

    @http.route(['/mail/chatter_post'], type='json', methods=['POST'], auth='user')
    def portal_chatter_post(self, res_model, res_id, message, attachment_ids=None, attachment_tokens=None, **kw):
        """Create a new `mail.message` with the given `message` and/or `attachment_ids` and return new message values.
        The message will be associated to the record `res_id` of the model
        `res_model`. The user must have access rights on this target document or
        must provide valid identifiers through `kw`. See `_message_post_helper`.
        """
        if not self._portal_post_has_content(res_model, res_id, message,
                                             attachment_ids=attachment_ids, attachment_tokens=attachment_tokens,
                                             **kw):
            return

        res_id = int(res_id)

        self._portal_post_check_attachments(attachment_ids or [], attachment_tokens or [])

        result = {'default_message': message}
        # message is received in plaintext and saved in html
        if message:
            message = plaintext2html(message)
        post_values = {
            'res_model': res_model,
            'res_id': res_id,
            'message': message,
            'send_after_commit': False,
            'attachment_ids': False,  # will be added afterward
        }
        post_values.update((fname, kw.get(fname)) for fname in self._portal_post_filter_params())
        post_values['_hash'] = kw.get('hash')
        message = self._message_post_helper(**post_values)
        result.update({'default_message_id': message.id})

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

    def _get_quotation_domain(self, partner):
        return [
            ('message_partner_ids', 'child_of', [
             partner.commercial_partner_id.id]),
            ('state', 'in', ['sent', 'sale', 'done'])
        ]

