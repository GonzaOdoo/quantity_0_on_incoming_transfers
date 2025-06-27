from odoo import models, fields, api
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)

class PurchaseRequirements(models.Model):
    _name = 'purchase.requirements'
    _description = 'Purchase requirements'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char('Nombre', default='Borrador')
    state = fields.Selection(selection=[('draft','Borrador'),('pending','Por aprobar'),('done','Hecho')],default="draft",string="Estado")
    date = fields.Date('Fecha')
    partner_id = fields.Many2one('res.partner', string='Proveedor')
    category_id = fields.Many2one('product.category', string='Sector', required=True)
    line_ids = fields.One2many('purchase.requirements.line', 'requirement_id', string='Líneas de requerimiento')
    # Relación many2many
    purchase_ids = fields.Many2many(
        'purchase.order',
        'purchase_requirement_purchase_order_rel',
        'requirement_id',
        'order_id',
        string='Órdenes de compra asociadas',
    )
    order_count = fields.Integer(
    'Número de órdenes',
    compute='_compute_order_count',
    readonly=True
)
    @api.depends('purchase_ids')
    def _compute_order_count(self):
        for requirement in self:
            requirement.order_count = len(requirement.purchase_ids)

    @api.model
    def create(self, vals):
        # Si no tiene nombre o es 'Borrador', asignar secuencia
        if not vals.get('name') or vals['name'] == 'Borrador':
            sequence = self.env['ir.sequence'].next_by_code('pedidos_compra')
            vals['name'] = sequence
        return super(PurchaseRequirements, self).create(vals)

    def action_confirm(self):
        for record in self:
            record.state = 'pending'
        
    def action_create_purchase_order(self):
        PurchaseOrder = self.env['purchase.order']
        PurchaseOrderLine = self.env['purchase.order.line']
    
        for requirement in self:
            if not requirement.line_ids.filtered(lambda l: l.qty_to_order > 0):
                continue
    
            # Agrupar por proveedor
            partner_lines = {}
            for line in requirement.line_ids:
                if line.qty_to_order <= 0:
                    continue
                if line.partner_id.id not in partner_lines:
                    partner_lines[line.partner_id.id] = []
                partner_lines[line.partner_id.id].append(line)
    
            # Crear o reutilizar órdenes por proveedor
            for partner_id, lines in partner_lines.items():
                if not partner_id:
                    continue
    
                # Buscar cotización en borrador que YA TENGA ALGÚN REQUERIMIENTO asociado
                existing_po = PurchaseOrder.search([
                    ('partner_id', '=', partner_id),
                    ('state', '=', 'draft'),
                    ('purchase_requirement_ids', '!=', False),
                ], limit=1)
    
                if existing_po:
                    po = existing_po
                    # Asegurarse de que el requerimiento actual esté relacionado
                    if requirement.id not in po.purchase_requirement_ids.ids:
                        po.write({'purchase_requirement_ids': [(4, requirement.id)]})
                else:
                    # Crear nueva orden y vincular requerimiento
                    vals = {
                        'partner_id': partner_id,
                        'origin': requirement.name,
                        'date_order': fields.Datetime.now(),
                        'company_id': self.env.company.id,
                        'purchase_requirement_ids': [(6, 0, [requirement.id])],
                    }
                    po = PurchaseOrder.create(vals)
    
                # Preparar líneas nuevas o actualizar las existentes
                product_qty_map = {}
    
                # Cargar líneas existentes en la orden (si la estamos reutilizando)
                for line in po.order_line:
                    product_qty_map[line.product_id.id] = line.product_qty
    
                # Procesar las líneas del requerimiento
                for line in lines:
                    product_id = line.product_id.id
                    qty_to_add = line.qty_to_order
    
                    if product_id in product_qty_map:
                        # Si ya existe, sumar cantidad
                        product_qty_map[product_id] += qty_to_add
                    else:
                        # Si no existe, crear nueva entrada
                        product_qty_map[product_id] = qty_to_add
    
                # Ahora construimos las líneas finales
                order_lines = []
                for product_id, qty in product_qty_map.items():
                    product = self.env['product.product'].browse(product_id)
                    order_lines.append((0, 0, {
                        'product_id': product_id,
                        'name': product.name or '/',
                        'product_qty': qty,
                    }))
    
                # Reemplazar todas las líneas de la orden
                po.write({'order_line': [(5, 0, 0)] + order_lines})
    
            # Marcar como hecho
            requirement.write({'state': 'done'})

    def open_add_product_list(self):
        for record in self:
            return {
                'name': 'Product Variants',
                'type': 'ir.actions.act_window',
                'res_model': 'product.product',
                'view_mode': 'list',
                'view_id': self.env.ref('quantity_0_on_incoming_transfers.view_purchase_requirements_tree_requirements').id,
                'target': 'new',  # Esto lo abre como wizard/popup
                'domain': [('categ_id', '=', record.category_id.id)],
                'context': {
                    'default_requirement_id': self.id,
                    'create': False,  # Opcional: deshabilitar creación
                    'delete': False,  # Opcional: deshabilitar eliminación
                },
            }

    def action_view_orders(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("purchase.purchase_rfq")
        orders = self.purchase_ids
        if len(orders) > 1:
            action['domain'] = [('id', 'in', orders.ids)]
        elif len(orders) == 1:
            form_view = [(self.env.ref('purchase.purchase_order_form').id, 'form')]
            if 'views' in action:
                action['views'] = form_view + [(state, view) for state, view in action['views'] if view != 'form']
            else:
                action['views'] = form_view
            action['res_id'] = orders.id
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action

   
class PurchaseRequirementsLine(models.Model):
    _name = 'purchase.requirements.line'
    _description = 'Linea de requirimiento'

    partner_id = fields.Many2one('res.partner',string='Proveedor',required=True)
    requirement_id = fields.Many2one('purchase.requirements',string='Requirimiento', ondelete='cascade')
    product_id = fields.Many2one('product.product',string='Producto')
    qty_on_hand = fields.Float('A mano', readonly=True, compute='_compute_qty')
    qty_forecast = fields.Float('Pronosticado', readonly=True, compute='_compute_qty')
    qty_to_order = fields.Float('A ordenar')
    min = fields.Float('Min',related='product_id.reordering_min_qty')
    max = fields.Float('Max',related='product_id.reordering_max_qty')
    
    @api.depends('product_id')
    def _compute_qty(self):
        for record in self:
            if not record.product_id:
                record.qty_on_hand = False
                record.qty_forecast = False
            else:
                record.qty_on_hand = record.product_id.qty_available
                record.qty_forecast = record.product_id.qty_available + record.product_id.incoming_qty - record.product_id.outgoing_qty


class ProductProduct(models.Model):
    _inherit = 'product.product'

    def action_add_to_requirement(self):
        requirement_id = self.env.context.get('default_requirement_id')
        if not requirement_id:
            raise UserError("No se encontró el requerimiento.")

        requirement = self.env['purchase.requirements'].browse(requirement_id)
        lines = []
        for product in self:
            amount_to_order = 0
            if product.virtual_available <= product.reordering_max_qty:
                amount_to_order = max(0, product.reordering_max_qty - product.virtual_available)
            lines.append((0, 0, {
                'product_id': product.id,
                'partner_id': product.seller_ids[0].partner_id.id if product.seller_ids[0] else False,
                'qty_to_order': amount_to_order,  # Puedes ajustarlo según lógica (min/max, etc.)
            }))

        requirement.write({'line_ids': lines})
        return {'type': 'ir.actions.act_window_close'}


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    purchase_requirement_ids = fields.Many2many(
        'purchase.requirements',
        'purchase_requirement_purchase_order_rel',
        'order_id',
        'requirement_id',
        string='Requerimientos asociados',
        
    )
    requirement_count = fields.Integer(
        string='Número de requerimientos',
        compute='_compute_requirement_count'
    )

    @api.depends('purchase_requirement_ids')
    def _compute_requirement_count(self):
        for record in self:
            record.requirement_count = len(record.purchase_requirement_ids)


    def action_view_requirements(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("quantity_0_on_incoming_transfers.action_purchase_requirements")
    
        requirements = self.purchase_requirement_ids
        if len(requirements) > 1:
            action['domain'] = [('id', 'in', requirements.ids)]
        elif len(requirements) == 1:
            form_view = [(self.env.ref('quantity_0_on_incoming_transfers.view_purchase_requirements_form').id, 'form')]
            if 'views' in action:
                # Mantener otras vistas (como kanban, etc.) si existen
                action['views'] = form_view + [(state, view) for state, view in action['views'] if view != 'form']
            else:
                action['views'] = form_view
            action['res_id'] = requirements.id
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action
    
    