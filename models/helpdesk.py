from odoo import models, fields
import logging

_logger = logging.getLogger(__name__)
class HelpdeskTicket(models.Model):
    _inherit = 'helpdesk.ticket'

    # Puedes agregar nuevos campos si los necesitas
    area = fields.Selection([('Infraestructura','Infraestructura'),('Redes','Redes'),('Configuración de VPN','Configuración de VPN'),('Asistencia para videoconferencias','Asistencia para videoconferencias')],string="Área")

    def create(self, vals):
        # Aquí puedes manipular los valores antes de crear el ticket
        _logger.info(vals)
        # Llamamos a la creación original
        ticket = super(HelpdeskTicket, self).create(vals)

        # Aquí puedes realizar acciones tras la creación del ticket
        # Por ejemplo, asignar permisos a adjuntos, enviar emails, etc.

        # Ejemplo: Asignar valor adicional basado en lógica
        ticket.message_post(body="Este ticket fue creado desde mi módulo personalizado.")

        return ticket