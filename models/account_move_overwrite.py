from odoo import models, fields, api
from datetime import datetime, timedelta
import logging

class StockMove(models.Model):
    _inherit = 'account.move'
    
    @api.onchange('l10n_xma_date_post', 'invoice_date_due', 'invoice_payment_term_id')
    def onchange_credit_or_cash(self):
        for rec in self:
            pass
