# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Invoice Multi Branch Unit',
    'version': '16.0.0.0',
    'category': 'Accounting',
    'summary': 'Multi Branch Invoice Multiple Branch Invoice multi branch accounting multi branch invoicing multiple branch Invoice multiple branch bills multi unit vendor bills multi unit invoicing process multi branch invoice multi branch invoice multi branches invoice',
    "description": """
       
        Invoicing Multi Branch in odoo,
        multiple Branch for Customer Invoice in odoo,
        multiple Branch for Vendor Bill in odoo,
        multiple Branch for Payment in odoo,
        multiple Branch for Credit Note in odoo,
        multiple Branch for Journal Entry in odoo,
        multiple Branch for Refund in odoo,
        multiple Branch for Receipt in odoo,
        multiple Branch for Bank Statement in odoo,

    """,
    'author': 'BrowseInfo',
    "price": 30,
    "currency": 'EUR',
    'website': 'https://www.browseinfo.in',
    'depends': ['account', 'sale_management', 'bi_branch_base'],
    'data': [
        'views/inherited_account_invoice.xml',
        'wizard/inherited_account_payment.xml',
    ],
    'license': 'OPL-1',
    'installable': True,
    'auto_install': False,
    'live_test_url': 'https://youtu.be/4TzD3tIXF-c',
    "images": ['static/description/Banner.gif'],
    'post_init_hook': 'post_init_hook',
}

