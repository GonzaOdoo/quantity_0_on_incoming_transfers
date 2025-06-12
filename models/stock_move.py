from odoo import models, fields, api
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)

class StockMove(models.Model):
    _inherit = 'stock.move'
    
    initial_purchase_quantity_zero = fields.Boolean(
        string="Initial Purchase Qty Zero",
        help="Technical field to mark if quantity was set to 0 at creation from PO",
        default=False,
        copy=False
    )

    @api.model_create_multi
    def create(self, vals_list):
        moves = super().create(vals_list)
        for move in moves:
            if (move.picking_id and 
                move.picking_id.picking_type_id.code == 'incoming' and 
                move.purchase_line_id and
                not move.initial_purchase_quantity_zero):
                move.write({
                    'quantity': 0,
                    'initial_purchase_quantity_zero': True,
                })
                _logger.info("Initial quantity set to 0 for move %s from PO %s", 
                           move.id, move.purchase_line_id.order_id.name)
        return moves

    @api.depends('move_line_ids.quantity', 'move_line_ids.product_uom_id')
    def _compute_quantity(self):
        _logger.info("Computing quantity")
        for move in self:
            has_tracking_lines = any(line.lot_id or line.lot_name for line in move.move_line_ids)
            if move.initial_purchase_quantity_zero :
                if move.quantity == 0 and not has_tracking_lines:
                    # Primera ejecución - mantener 0
                    now = fields.Datetime.now()
                    time_threshold = now - timedelta(seconds=5)
                    
                    if move.move_line_ids:
                        all_recent = True
                        for line in move.move_line_ids:
                            if not line.create_date:
                                all_recent = False
                                break
                            create_date = fields.Datetime.from_string(line.create_date)
                            if create_date <= time_threshold:
                                all_recent = False
                                break
                        
                        if all_recent:
                            _logger.info("Deleting automatically created lines for move %s", move.id)
                            move.move_line_ids.unlink()
                    continue
                else:
                    # Permitir cálculo normal y resetear flag
                    super(StockMove, move)._compute_quantity()
                    move.initial_purchase_quantity_zero = False
                    continue
            else:
                # Comportamiento normal
                super(StockMove, move)._compute_quantity()


