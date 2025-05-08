from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)
class StockMove(models.Model):
    _inherit = 'stock.move'

    @api.depends('product_uom_qty', 'product_uom', 'picking_id.picking_type_id', 'picking_id.state')
    def _compute_quantity(self):
        super(StockMove, self)._compute_quantity()
        for move in self:
            if (
                move.picking_id 
                and move.picking_id.picking_type_id.code == 'incoming'
                and move.purchase_line_id  # Viene de compra
                and move.picking_id.state != 'done'  # Solo si no está validado
            ):
                _logger.info("Setting quantity to 0 for move %s (state: %s)", 
                           move.id, move.picking_id.state)
                move.quantity = 0