# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from decimal import Decimal
import datetime
from dateutil.relativedelta import relativedelta
import unittest
import trytond.tests.test_tryton
from trytond.tests.test_tryton import POOL, DB_NAME, USER, CONTEXT, test_view,\
    test_depends
from trytond.transaction import Transaction

from trytond.tests.test_tryton import ModuleTestCase
from trytond.tests.test_tryton import (doctest_setup, doctest_teardown,
    doctest_checker)


class TestCase(ModuleTestCase):
    'Test module'
    module = 'guarantee'

    def setUp(self):
        trytond.tests.test_tryton.install_module('guarantee')
        self.company = POOL.get('company.company')
        self.guarantee = POOL.get('guarantee.guarantee')
        self.guarantee_config = POOL.get('guarantee.configuration')
        self.guarantee_type = POOL.get('guarantee.type')
        self.product = POOL.get('product.product')
        self.sequence = POOL.get('ir.sequence')
        self.template = POOL.get('product.template')
        self.uom = POOL.get('product.uom')
        self.user = POOL.get('res.user')

    def test0010_in_guarante(self):
        with Transaction().start(DB_NAME, USER, context=CONTEXT) as tx:
            company, = self.company.search([
                    ('rec_name', '=', 'Dunder Mifflin'),
                    ])
            self.user.write([self.user(USER)], {
                'main_company': company.id,
                'company': company.id,
                })
            sequence, = self.sequence.search([
                    ('code', '=', 'guarantee.guarantee')
                    ])
            with tx.set_context(company=company.id):
                self.guarantee_config.create([{
                            'guarantee_sequence': sequence.id,
                            }])

            today = datetime.date.today()
            tomorrow = today + relativedelta(days=1)
            next_month = today + relativedelta(months=1)
            next_two_month = today + relativedelta(months=2)
            u, = self.uom.search([('name', '=', 'Unit')])
            good, service, consumable = self.template.create([{
                        'name': 'Test Guarantee Good',
                        'type': 'goods',
                        'list_price': Decimal(1),
                        'cost_price': Decimal(0),
                        'cost_price_method': 'fixed',
                        'default_uom': u.id,
                        }, {
                        'name': 'Test Guarantee Service',
                        'type': 'service',
                        'list_price': Decimal(1),
                        'cost_price': Decimal(0),
                        'cost_price_method': 'fixed',
                        'default_uom': u.id,
                        }, {
                        'name': 'Test Guarantee Consumable',
                        'type': 'goods',
                        'consumable': True,
                        'list_price': Decimal(1),
                        'cost_price': Decimal(0),
                        'cost_price_method': 'fixed',
                        'default_uom': u.id,
                        }])
            products = self.product.create([{
                        'template': good.id,
                        }, {
                        'template': service.id,
                        }, {
                        'template': consumable.id,
                        }])
            good_product, service_product, consumable_product = products

            types = self.guarantee_type.create([{
                        'name': 'Goods',
                        'includes_goods': True,
                        }, {
                        'name': 'Services',
                        'includes_services': True,
                        }, {
                        'name': 'Consumables',
                        'includes_consumables': True,
                        }])
            goods_guarantee, service_guarantee, consumable_guarantee = types
            tests = [{
                    'product': good_product,
                    'guarantee_type': goods_guarantee,
                    'start_date': today,
                    'end_date': next_month,
                    'test_date': today,
                    'result': True,
                    }, {
                    'product': good_product,
                    'guarantee_type': goods_guarantee,
                    'start_date': today,
                    'end_date': next_month,
                    'test_date': tomorrow,
                    'result': True,
                    }, {
                    'product': good_product,
                    'guarantee_type': goods_guarantee,
                    'start_date': today,
                    'end_date': next_month,
                    'test_date': next_month,
                    'result': True,
                    }, {
                    'product': good_product,
                    'guarantee_type': goods_guarantee,
                    'start_date': today,
                    'end_date': next_month,
                    'test_date': next_two_month,
                    'result': False,
                    }, {
                    'product': good_product,
                    'guarantee_type': service_guarantee,
                    'start_date': today,
                    'end_date': next_month,
                    'test_date': tomorrow,
                    'result': False,
                    }, {
                    'product': service_product,
                    'guarantee_type': service_guarantee,
                    'start_date': today,
                    'end_date': next_month,
                    'test_date': tomorrow,
                    'result': True,
                    }, {
                    'product': good_product,
                    'guarantee_type': consumable_guarantee,
                    'start_date': today,
                    'end_date': next_month,
                    'test_date': tomorrow,
                    'result': False,
                    }, {
                    'product': consumable_product,
                    'guarantee_type': consumable_guarantee,
                    'start_date': today,
                    'end_date': next_month,
                    'test_date': tomorrow,
                    'result': True,
                    }]
            for data in tests:
                with tx.set_context(company=company.id):
                    guarantee, = self.guarantee.create([{
                                'party': company.party.id,
                                'document': str(data['product']),
                                'type': data['guarantee_type'],
                                'start_date': data['start_date'],
                                'end_date': data['end_date'],
                                }])
                self.assertEqual(guarantee.applies_for_product(data['product'],
                        data['test_date']), data['result'])


def suite():
    suite = trytond.tests.test_tryton.suite()
    from trytond.modules.company.tests import test_company
    for test in test_company.suite():
        suite.addTest(test)
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestCase))
    return suite
