from odoo import models, fields, api
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
                    continue
                else:
                    # Permitir cálculo normal y resetear flag
                    super(StockMove, move)._compute_quantity()
                    move.initial_purchase_quantity_zero = False
                    continue
            else:
                # Comportamiento normal
                super(StockMove, move)._compute_quantity()


class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    """
    @api.model_create_multi
    def create(self, vals_list):
        # Primero modificamos los vals_list según nuestra necesidad
        for vals in vals_list:
            if vals.get('move_id'):
                move = self.env['stock.move'].browse(vals['move_id'])
                if move.quantity == 0:
                    _logger.info("Setting quantity to 0 for move line")
                    vals['quantity'] = 0  # o 'qty_done' según lo que necesites
        
        # Llamamos al super() para que se ejecute la lógica original
        mls = super().create(vals_list)
        
        return mls
    """
    
    def write(self, vals):
        # Verificar si se está modificando quantity y si move_id tiene quantity=0
        if 'quantity' in vals:
            for ml in self:
                if ml.move_id and ml.move_id.quantity == 0:
                    _logger.info(f"Overriding quantity with product_uom_qty for move line {ml.id}")
                    vals['quantity'] = ml.move_id.product_uom_qty
        
        # Llamar al método original
        return super().write(vals)
