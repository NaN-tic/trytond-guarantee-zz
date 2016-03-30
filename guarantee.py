# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from dateutil.relativedelta import relativedelta
from trytond.model import ModelSQL, ModelView, fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval
from trytond.transaction import Transaction
from trytond import backend

__all__ = ['GuaranteeType', 'Product', 'GuaranteeSaleLine',
    'GuaranteeInvoiceLine', 'Guarantee', 'SaleLine', 'InvoiceLine']


class GuaranteeType(ModelSQL, ModelView):
    'Guarantee Type'
    __name__ = 'guarantee.type'
    name = fields.Char('Name', required=True, translate=True)
    duration = fields.Integer('Duration', required=True, help='The number of '
        'months that the product is in guarantee')
    includes_services = fields.Boolean('Include Services', help='If marked '
        'this waranty type will include service products')
    includes_goods = fields.Boolean('Include Goods', help='If marked '
        'this waranty type will include goods products')
    includes_consumables = fields.Boolean('Include Consumables', help='If '
        'marked this waranty type will include consumable products')
    active = fields.Boolean('Active')

    @staticmethod
    def default_duration():
        return 0

    @staticmethod
    def default_active():
        return True

    def applies_for_product(self, product):
        if product.type == 'service':
            return self.includes_services
        elif product.type == 'goods':
            if product.consumable:
                return self.includes_consumables
            return self.includes_goods
        else:
            return False


class Product:
    __metaclass__ = PoolMeta
    __name__ = 'product.product'
    guarantee_type = fields.Many2One('guarantee.type', 'Guarante Type')


class GuaranteeSaleLine(ModelSQL):
    'Guarantee - Sale Line'
    __name__ = 'guarantee.guarantee-sale.line'
    guarantee = fields.Many2One('guarantee.guarantee', 'Guarantee',
        required=True, select=True, ondelete='CASCADE')
    sale_line = fields.Many2One('sale.line', 'Sale Line',
        required=True, select=True, ondelete='CASCADE')


class GuaranteeInvoiceLine(ModelSQL):
    'Guarantee - Invoice Line'
    __name__ = 'guarantee.guarantee-account.invoice.line'
    guarantee = fields.Many2One('guarantee.guarantee', 'Guarantee',
        required=True, select=True, ondelete='CASCADE')
    invoice_line = fields.Many2One('account.invoice.line', 'Invoice Line',
        required=True, select=True, ondelete='CASCADE')


class Guarantee(ModelSQL, ModelView):
    'Guarantee'
    __name__ = 'guarantee.guarantee'
    _rec_name = 'code'

    code = fields.Char('Code', readonly=True, required=True)
    party = fields.Many2One('party.party', 'Party', required=True)
    document = fields.Reference('Document', selection='get_origin',
        required=True, select=True)
    type = fields.Many2One('guarantee.type', 'Type', required=True)
    start_date = fields.Date('Start Date', required=True)
    end_date = fields.Date('End Date', required=True)
    in_guarantee = fields.Function(fields.Boolean('In Guarantee'),
        'get_in_guarantee')
    sale_lines = fields.Many2Many('guarantee.guarantee-sale.line', 'guarantee',
        'sale_line', 'Sale Lines')
    invoice_lines = fields.Many2Many(
        'guarantee.guarantee-account.invoice.line', 'guarantee',
        'invoice_line', 'Invoice Lines')
    guarantee_sale_lines = fields.One2Many('sale.line', 'guarantee',
        'Sale Lines in Guarantee')
    guarantee_invoice_lines = fields.One2Many('account.invoice.line',
        'guarantee', 'Invoice Lines in Guarantee')
    notes = fields.Text('Notes')

    @classmethod
    def __setup__(cls):
        super(Guarantee, cls).__setup__()
        cls._error_messages.update({
                'no_guarantee_sequence': ('No guarantee sequence has been '
                    'defined. Please define one in guarantee configuration')
                })

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        table = TableHandler(cls, module_name)

        super(Guarantee, cls).__register__(module_name)

        # Migration from 3.4: drop required on state
        table.not_null_action('state', action='remove')

    @classmethod
    def _get_origin(cls):
        'Return list of Model names for origin Reference'
        return ['product.product']

    @classmethod
    def get_origin(cls):
        Model = Pool().get('ir.model')
        models = cls._get_origin()
        models = Model.search([
                ('model', 'in', models),
                ])
        return [(m.model, m.name) for m in models]

    def get_in_guarantee(self, name):
        pool = Pool()
        Date = pool.get('ir.date')
        date = Transaction().context.get('gurantee_date', Date.today())
        return self.applies_for_date(date)

    @fields.depends('type', 'start_date')
    def on_change_with_end_date(self):
        if self.type and self.start_date:
            return self.start_date + relativedelta(months=self.type.duration)

    def applies_for_date(self, date):
        'Returns if the guarantee applies for the current date'
        return date >= self.start_date and date <= self.end_date

    def applies_for_product(self, product, date):
        '''Returns if the current waranty applies for the current product
        and date
        '''
        if not self.applies_for_date(date):
            return False
        return self.type.applies_for_product(product)

    @classmethod
    def create(cls, vlist):
        pool = Pool()
        Sequence = pool.get('ir.sequence')
        Config = pool.get('guarantee.configuration')

        sequence = Config(1).guarantee_sequence
        if not sequence:
            cls.raise_user_error('no_guarantee_sequence')
        vlist = [x.copy() for x in vlist]
        for vals in vlist:
            if 'code' not in vals:
                vals['code'] = Sequence.get_id(sequence.id)
        return super(Guarantee, cls).create(vlist)


class SaleLine:
    __metaclass__ = PoolMeta
    __name__ = 'sale.line'
    guarantee = fields.Many2One('guarantee.guarantee', 'Guarantee',
        ondelete='RESTRICT',
        domain=[
            ('party', '=', Eval('_parent_sale', {}).get('party', 0)),
            ],
        states={
            'invisible': Eval('type') != 'line',
            },
        depends=['type'])
    line_in_guarantee = fields.Function(fields.Boolean('In guarantee',
            states={
                'invisible': Eval('type') != 'line',
                },
            depends=['type']),
        'on_change_with_line_in_guarantee')

    @classmethod
    def __setup__(cls):
        super(SaleLine, cls).__setup__()
        cls._error_messages.update({
                'guarantee_nonzero_unit_price': ('Line "%s" must have zero '
                    'unit price as it is on guarantee'),
                })

    @fields.depends('_parent_sale.sale_date', 'guarantee', 'product')
    def on_change_with_line_in_guarantee(self, name=None):
        pool = Pool()
        Date = pool.get('ir.date')
        date = Date.today()
        if self.sale and self.sale.sale_date:
            date = self.sale.sale_date
        if self.guarantee and self.product:
            return self.guarantee.applies_for_product(self.product, date)
        return False

    @fields.depends(methods=['quantity'])
    def on_change_guarantee(self):
        self.on_change_quantity()

    @fields.depends(methods=['quantity'])
    def on_change_product(self):
        super(SaleLine, self).on_change_product()
        self.on_change_quantity()

    @fields.depends('sale', '_parent_sale.sale_date', 'guarantee', 'product')
    def on_change_quantity(self):
        super(SaleLine, self).on_change_quantity()
        if self.on_change_with_line_in_guarantee():
            self.unit_price = 0
            self.gross_unit_price = 0

    @fields.depends(methods=['line_in_guarantee'])
    def on_change_with_amount(self):
        return super(SaleLine, self).on_change_with_amount()

    @classmethod
    def validate(cls, lines):
        super(SaleLine, cls).validate(lines)
        for line in lines:
            line.check_guarantee()

    def check_guarantee(self):
        if self.line_in_guarantee and self.unit_price != 0.0:
            self.raise_user_error('guarantee_nonzero_unit_price',
                self.rec_name)

    def get_invoice_line(self):
        lines = super(SaleLine, self).get_invoice_line()
        for line in lines:
            line.guarantee = self.guarantee
        return lines

    def get_guarantee(self):
        pool = Pool()
        Date = pool.get('ir.date')
        Guarantee = pool.get('guarantee.guarantee')
        if not self.product or not self.product.guarantee_type:
            return
        guarantee = Guarantee()
        guarantee.party = self.sale.party
        guarantee.document = str(self.product)
        guarantee.type = self.product.guarantee_type
        today = Date.today()
        guarantee.start_date = self.sale.sale_date or today
        guarantee.end_date = guarantee.on_change_with_end_date()
        guarantee.sale_lines = [self]
        return guarantee


class InvoiceLine:
    __metaclass__ = PoolMeta
    __name__ = 'account.invoice.line'
    guarantee = fields.Many2One('guarantee.guarantee', 'Guarantee',
        ondelete='RESTRICT',
        domain=[
            ('party', '=', Eval('_parent_invoice', {}).get('party', 0)),
            ],
        states={
            'invisible': Eval('type') != 'line',
            },
        depends=['type'])
    line_in_guarantee = fields.Function(fields.Boolean('In guarantee',
            states={
                'invisible': Eval('type') != 'line',
                },
            depends=['type']),
        'on_change_with_line_in_guarantee')

    @classmethod
    def __setup__(cls):
        super(InvoiceLine, cls).__setup__()
        cls._error_messages.update({
                'guarantee_nonzero_unit_price': ('Line "%s" must have zero '
                    'unit price as it is on guarantee'),
                })

    @fields.depends('_parent_invoice.invoice_date', 'guarantee', 'product',
        'origin')
    def on_change_with_line_in_guarantee(self, name=None):
        pool = Pool()
        Date = pool.get('ir.date')
        date = Date.today()
        if (self.guarantee and self.origin and
                hasattr(self.origin, 'line_in_guarantee')):
            return self.origin.line_in_guarantee
        if self.invoice and self.invoice.invoice_date:
            date = self.invoice.invoice_date
        if self.guarantee and self.product:
            return self.guarantee.applies_for_product(self.product, date)
        return False

    @fields.depends(methods=['product'])
    def on_change_guarantee(self):
        self.on_change_product()

    @fields.depends('invoice', '_parent_invoice.invoice_date', 'guarantee',
        'origin')
    def on_change_product(self):
        super(InvoiceLine, self).on_change_product()
        if self.on_change_with_line_in_guarantee():
            self.unit_price = 0
            self.gross_unit_price = 0
