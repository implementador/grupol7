odoo.define('bi_pos_pay_later.PaymentScreen', function(require) {
	'use strict';

	const PaymentScreen = require('point_of_sale.PaymentScreen');
	const Registries = require('point_of_sale.Registries');
	const session = require('web.session');

	const BiPaymentScreen = PaymentScreen => 
		class extends PaymentScreen {
			setup() {
				super.setup();
			}
			async selectPartner() {
				let self = this;
				if (this.currentOrder.is_paying_partial){
					return self.showPopup('ErrorPopup', {
						title: self.env._t('No permitido'),
						body: self.env._t('No es posible cambiar el cliente de una orden.'),
					});
				} else {
					super.selectPartner();
				}
			}

			remove_current_orderlines(){
				let self = this;
				let order = self.env.pos.get_order();
				let orderlines = order.get_orderlines();
				order.set_partner(null);           
	            while (orderlines.length > 0) {
	                orderlines.forEach(function (line) {
	                    order.remove_orderline(line);
	                });
	            }
	            order.is_paying_partial=false
			}

			async click_back(){
				let self = this;
				if(this.currentOrder.is_paying_partial){
					const { confirmed } = await this.showPopup('ConfirmPopup', {
						title: self.env._t('¿Cancelar pago?'),
						body: self.env._t('¿Seguro que quieres cancelar este pago?'),
					});
					if (confirmed) {
						self.remove_current_orderlines();
						self.showScreen('ProductScreen');
					}
				}
				else{
					self.showScreen('ProductScreen');
				}
			}

			clickPayLater(){
				let self = this;
				let order = self.env.pos.get_order();
				let orderlines = order.get_orderlines();
				let partner_id = order.get_partner();
				if (!partner_id){
					return self.showPopup('ErrorPopup', {
						title: self.env._t('Cliente desconocido'),
						body: self.env._t('Selecciona un cliente primero.'),
					});
				}
				else if(orderlines.length === 0){
					return self.showPopup('ErrorPopup', {
						title: self.env._t('Orden vacía'),
						body: self.env._t('Agrega al menos un producto.'),
					});
				}
				else{
					order.is_partial = true;
					order.amount_due = order.get_due();
					order.set_is_partial(true);
					order.to_invoice = false;
					order.finalized = false;
					self.env.pos.push_single_order(order);
					self.showScreen('ReceiptScreen');						
				}
			}
		}

	Registries.Component.extend(PaymentScreen, BiPaymentScreen);

	return PaymentScreen;

});