odoo.define('bi_pos_pay_later.CreateDraftPOS', function(require) {
	'use strict';

	const PosComponent = require('point_of_sale.PosComponent');
	const ProductScreen = require('point_of_sale.ProductScreen');
	const { useListener } = require("@web/core/utils/hooks");
	const Registries = require('point_of_sale.Registries');

	class CreateDraftPOS extends PosComponent {
		setup() {
			super.setup();
			useListener('click', this.onClick);
		}	
		async onClick() {
			let self = this;
			let order = this.env.pos.get_order();
			let orderlines = order.get_orderlines();
			let partner_id = order.get_partner();
			let flag_call = true;
			if (!partner_id){
				return self.showPopup('ErrorPopup', {
					title: self.env._t('Unknown customer'),
					body: self.env._t('You cannot Create Order.Select customer first.'),
				});
			}
			else if(orderlines.length === 0){
				return self.showPopup('ErrorPopup', {
					title: self.env._t('Empty Order'),
					body: self.env._t('There must be at least one product in your order.'),
				});
			}
			else if(order.to_invoice){
				return self.showPopup('ErrorPopup', {
					'title': self.env._t('Order Validation'),
					'body': self.env._t('You Can not create invoice for draft order,please uncheck "Invoice" from payment screen.'),
				});
				return;
			}
			else{
				$.each(orderlines, function( i, line ){
					let prd = line.product;
					var final_qty = prd.bi_on_hand - prd.reserve_qty
					if(prd.bi_on_hand < line.quantity){
						self.showPopup('ErrorPopup', {
							title: self.env._t('Deny Order 1'),
							body: self.env._t("(" + prd.display_name + ")" + " existencias insuficientes."),
						});
						flag_call = false;
					}else if(final_qty < line.quantity){
						self.showPopup('ErrorPopup', {
							title: self.env._t('Deny Order 2'),
							body: self.env._t("(" + prd.display_name + ")" + " existencias insuficientes."),
						});
						flag_call = false;
					}						
					
				})
				if(flag_call){
					if(order.get_total_with_tax() !== order.get_total_paid()){
						order.amount_due = order.get_due();
						order.is_draft_order = true;
						order.is_partial = true;
						order.to_invoice = false;
						self.env.pos.push_single_order(order);
						self.showScreen('ReceiptScreen');			
					}					
				}
			}

		}
	}
	CreateDraftPOS.template = 'CreateDraftPOS';

	ProductScreen.addControlButton({
		component: CreateDraftPOS,
		condition: function() {
			return this.env.pos.config.allow_partical_payment;
		},
	});

	Registries.Component.add(CreateDraftPOS);

	return CreateDraftPOS;
});
