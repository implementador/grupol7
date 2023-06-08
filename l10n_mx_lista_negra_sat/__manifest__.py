# -*- coding: utf-8 -*-

{
    'name':'Lista Negra Sat', 
    'category':"",
    'author': 'Lava Studio',
    'version': '16.01',
    'description' :'''Add One Field in res.partner.
        Create Automated Function That Runs Every Day.
        Add 2 New Menu Options On Invoicing – Vendors and Customers''',
    'depends':['account','l10n_mx_edi','sale'],
    'data':[
           'security/ir.model.access.csv',
           'data/crone_data.xml',
           'data/data.xml',
           'views/lista_negra_sat_view.xml',
           'views/sale_order.xml',
           'views/account_invoice.xml',
           'views/add_menu.xml',

        ],
}
