from odoo import models, fields, api
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)

class Users(models.Model):
    _inherit = "res.users"

    internal_default_location = fields.Many2one('stock.location','Ubicación interna por defecto')