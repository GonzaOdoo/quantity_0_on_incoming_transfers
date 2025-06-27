from odoo import models, fields, api
from odoo.tools.float_utils import float_compare
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    hide_validate_button = fields.Boolean(
        string='Ocultar botón Validar',
        compute='_compute_hide_validate_button',
        help='Campo computado para controlar visibilidad del botón Validar'
    )
    available_product_ids = fields.Many2many(
        'product.product',
        string='Productos Disponibles',
        compute='_compute_available_products'
    )

    @api.depends('location_id', 'picking_type_code')
    def _compute_available_products(self):
        for picking in self:
            _logger.info("Busqueda")
            if picking.picking_type_code in ['outgoing'] and picking.location_id:
                # Obtener todas las ubicaciones hijas (incluye la propia si no tiene hijos)
                location_ids = picking.location_id.child_ids.ids or [picking.location_id.id]
    
                quants = self.env['stock.quant'].search([
                    ('location_id', 'in', location_ids),
                    ('quantity', '>', 0),
                    ('product_id.active', '=', True),
                ])
    
                # Obtenemos los productos disponibles
                products = quants.mapped('product_id')
                picking.available_product_ids = [(6, 0, products.ids)]
            elif picking.picking_type_code in ['internal'] and picking.location_id:
                _logger.info("Busqueda 2")
                # Buscamos en stock.quant los productos disponibles en esa ubicación
                products = self.env['product.product'].search([
                    ('categ_id', 'in', [picking.location_dest_id.product_category_id.id,35]),
                ]).mapped('id')
                _logger.info(products)
                picking.available_product_ids = products
            else:
                picking.available_product_ids = self.env['product.product'].search([])
    @api.model
    def default_get(self, fields):
        res = super(StockPicking, self).default_get(fields)
        _logger.info("Default get values: %s", res)
        
        picking_type_id = res.get('picking_type_id') or self._context.get('default_picking_type_id')
        
        if picking_type_id:
            picking_type = self.env['stock.picking.type'].browse(picking_type_id)
            user = self.env.user
            
            # Solo modificamos si el usuario tiene ubicación por defecto configurada
            if user.internal_default_location:
                # Para transferencias INTERNAS (solo ubicación destino)
                if picking_type.code == 'internal':
                    _logger.info("Processing INTERNAL transfer")
                    
                    # 1. Primero obtenemos la ubicación de origen del tipo de operación
                    default_src = picking_type.default_location_src_id
                    if default_src:
                        _logger.info("Using default SRC location from operation type: %s", default_src.display_name)
                        res['location_id'] = default_src.id
                    
                    # 2. Solo aplicamos la ubicación del usuario si no hay destino configurado
                    if user.internal_default_location and not res.get('location_dest_id'):
                        res['location_dest_id'] = user.internal_default_location.id
                        _logger.info("Set user default DEST location: %s", user.internal_default_location.display_name)
    
                
                # Para ENTREGAS/SALIDAS
                elif picking_type.code == 'outgoing':
                    _logger.info("Processing OUTGOING transfer")
                    
                    # Mantener ubicación origen si existe, sino usar la del usuario
                    if not res.get('location_id'):
                        res['location_id'] = user.internal_default_location.id
                        _logger.info("Set user default SRC: %s", user.internal_default_location.display_name)
                    
                    # Mantener ubicación destino del tipo de operación si existe
                    if not res.get('location_dest_id'):
                        default_dest = picking_type.default_location_dest_id
                        if default_dest:
                            res['location_dest_id'] = default_dest.id
                            _logger.info("Set DEST from operation type: %s", default_dest.display_name)
                    
        return res


    
    @api.depends('state', 'picking_type_id.code')
    def _compute_hide_validate_button(self):
        for picking in self:
            # Lógica para determinar si ocultar el botón
            _logger.info(f'Usuario activo:{self.env.user}')
            picking.hide_validate_button = (
                (picking.picking_type_id.code == 'internal' and 
                 self.env.user.has_group('__export__.res_groups_98_f78b878e'))
            )

            
    def remove_lines_on_0(self):
        for record in self:
            for line in record.move_ids_without_package:
                if line.quantity == 0:
                    line.unlink()


    def _pre_action_done_hook(self):
        for picking in self:
            _logger.info('Pre action hook')
            has_quantity = False
            has_pick = False
            for move in picking.move_ids:
                if move.quantity:
                    has_quantity = True
                if move.scrapped:
                    continue
                if move.picked:
                    has_pick = True
                if has_quantity and has_pick:
                    break
            if has_quantity and not has_pick:
                picking.move_ids.picked = True
    
        if not self.env.context.get('skip_backorder'):
            pickings_to_backorder = self._check_backorder()
            if pickings_to_backorder:
                if picking.picking_type_code == 'outgoing':
                    _logger.info('Outgoing!')
                    backorder_lines_vals = []
                    for picking in pickings_to_backorder:
                        backorder_lines_vals.append((0, 0, {
                            'picking_id': picking.id,
                            'to_backorder': True,
                        }))
                    backorder_wizard = self.env['stock.backorder.confirmation'].new({
                        'pick_ids': [(6, 0, pickings_to_backorder.ids)],
                        'backorder_confirmation_line_ids': backorder_lines_vals,
                        'show_transfers': pickings_to_backorder._should_show_transfers(),
                    })
                    backorder_wizard.process()
                # 2. Validamos internas sin backorder
                elif picking.picking_type_code == 'internal':
                    _logger.info(pickings_to_backorder)
                    pickings_to_validate_ids = pickings_to_backorder.ids
                    if pickings_to_validate_ids:
                        pickings_to_validate = self.env['stock.picking'].browse(pickings_to_validate_ids)
                        pickings_to_validate._check_less_quantities_than_expected(pickings_to_validate)
    
                        # Llamamos al button_validate con contexto especial
                        pickings_to_validate.with_context(
                            skip_backorder=True,
                            picking_ids_not_to_backorder=pickings_to_validate.ids
                        ).button_validate()
                else:
                    return pickings_to_backorder._action_generate_backorder_wizard(show_transfers=self._should_show_transfers())
        return True

    def _check_less_quantities_than_expected(self, pickings):
        for pick_id in pickings:
            moves_to_log = {}
            for move in pick_id.move_ids:
                picked_qty = move._get_picked_quantity()
                if float_compare(move.product_uom_qty,
                                 picked_qty,
                                 precision_rounding=move.product_uom.rounding) > 0:
                    moves_to_log[move] = (picked_qty, move.product_uom_qty)
            if moves_to_log:
                pick_id._log_less_quantities_than_expected(moves_to_log)

class ProductProduct(models.Model):
    _inherit = 'product.product'

    qty_available_in_location = fields.Float(
        string='Stock Disponible',
        compute='_compute_qty_available_in_location'
    )

    @api.depends_context('location_id')
    def _compute_qty_available_in_location(self):
        for product in self:
            location_id = self.env.context.get('location_id')
            if location_id:
                # Obtener todas las ubicaciones hijas (incluyendo la misma si no tiene hijos)
                location_ids = self.env['stock.location'].browse(location_id).child_ids.ids
                if not location_ids:  # Si no tiene hijos, usar solo la ubicación actual
                    location_ids = [location_id]

                # Buscamos todos los quant con stock > 0 en esa ubicación o sub-ubicaciones
                quants = self.env['stock.quant'].search([
                    ('product_id', '=', product.id),
                    ('location_id', 'in', location_ids),
                    ('quantity', '>', 0)
                ])
                # Sumamos todas las cantidades
                product.qty_available_in_location = sum(quants.mapped('quantity'))
            else:
                product.qty_available_in_location = 0.0