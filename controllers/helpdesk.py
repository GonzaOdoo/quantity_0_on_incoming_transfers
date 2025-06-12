from odoo import http
import re
from odoo.http import request
from odoo.addons.website_helpdesk.controllers.main import WebsiteForm
from odoo import _
from markupsafe import Markup
from odoo.addons.base.models.ir_qweb_fields import nl2br, nl2br_enclose
from odoo.tools import html2plaintext
import logging

_logger = logging.getLogger(__name__)
class WebsiteForm(WebsiteForm):

    def insert_record(self, request, model, values, custom, meta=None):
        # Llamamos al original para crear el ticket
        _logger.info("VALORES DEL FORMULARIO: %s", values)
        _logger.info("CUSTOM CONTENT: %s", custom)
        _logger.info("META DATA: %s", meta)
        res = super().insert_record(request, model, values, custom, meta=meta)

        # Verificamos que sea un ticket de helpdesk
        if model.sudo().model != 'helpdesk.ticket':
            return res

        ticket = request.env['helpdesk.ticket'].sudo().browse(res)
        _logger.info("Hola mundo")
        
        # Procesar campos personalizados del formulario
        default_field = model.website_form_default_field_id
        _logger.info(default_field.name)
        if default_field:
            custom_label = Markup("<h4>%s</h4>" % _("Other Information"))
            default_field_data = values.get(default_field.name, '')
            default_content = Markup("<h4>%s</h4><p>%s</p>") % (
                default_field.name.capitalize(),
                html2plaintext(default_field_data)
            ) if default_field_data else ''

            custom_content = default_content + custom_label + Markup(custom or '')

            if default_field.ttype == 'html':
                custom_content = nl2br(custom_content)

            ticket[default_field.name] = custom_content

            # Agregar mensaje visible públicamente
            ticket._message_log(
                body=custom_content,
                message_type='comment',
            )

        # Tu lógica adicional personalizada
        ticket.message_post(
            body="Este ticket fue procesado por mi controlador personalizado.",
            message_type='comment',
            subtype_xmlid='mail.mt_comment'
        )
        self._aplicar_condiciones(ticket, custom)
        return res


    def _aplicar_condiciones(self, ticket, custom):
        """
        Aplica lógica condicional basada en el contenido del formulario.
        """

        # Buscar "Acerca de" en `custom`
        if custom:
            _logger.info("CUSTOM RAW DATA: %s", custom)

            # Usamos regex para buscar "Acerca de : Valor"
            acerca_de_match = re.search(r'Acerca de\s*:\s*(.*?)(?:<br\s*/?>|\n|$)', custom, re.IGNORECASE | re.DOTALL)

            if acerca_de_match:
                acerca_de_valor = acerca_de_match.group(1).strip()
                _logger.info("VALOR EXTRAÍDO DE 'ACERCA DE': %s", acerca_de_valor)

                # Asignar al campo `area` del ticket
                ticket.write({
                    'area': acerca_de_valor  # Suponiendo que `area` es un campo `Char` en `helpdesk.ticket`
                })

                ticket.message_post(
                    body=f"Campo <b>Área</b> actualizado automáticamente a: <b>{acerca_de_valor}</b>",
                    message_type='comment',
                    subtype_xmlid='mail.mt_comment'
                )