# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.pool import Pool
from .configuration import *
from .guarantee import *


def register():
    Pool.register(
        Configuration,
        ConfigurationCompany,
        GuaranteeType,
        Product,
        Guarantee,
        GuaranteeSaleLine,
        GuaranteeInvoiceLine,
        SaleLine,
        InvoiceLine,
        module='guarantee', type_='model')
