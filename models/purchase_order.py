from odoo import models, fields, api, Command, _
from odoo.exceptions import UserError
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)
class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    is_sent = fields.Boolean(
        string="Order Sent",
        copy=False,
        help="Indicates if the purchase order has been sent to the vendor via email."
    )

    @api.returns('mail.message', lambda value: value.id)
    def message_post(self, **kwargs):
        # Llamamos al método original primero
        result = super(PurchaseOrder, self).message_post(**kwargs)
    
        # Si se está marcando como enviada, actualizamos el campo is_sent
        if self.env.context.get('mark_rfq_as_sent'):
            self.filtered(lambda o: o.state in ('purchase', 'done')).write({'is_sent': True})
    
        return result