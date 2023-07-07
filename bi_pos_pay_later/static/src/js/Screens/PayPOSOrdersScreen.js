odoo.define('bi_pos_pay_later.PayPOSOrdersScreen', function (require) {
	'use strict';

	const POSOrdersScreen = require('pos_orders_list.POSOrdersScreen');
	const Registries = require('point_of_sale.Registries');
	const { useListener } = require("@web/core/utils/hooks");
	const { onMounted, onWillUnmount, useRef } = owl;

	const PayPOSOrdersScreen = (POSOrdersScreen) =>
		class extends POSOrdersScreen {
			setup() {
				super.setup()
				this.filter_state = '';
				this.state = {
					filter_state: this.filter_state,
				};
				this.searchWordInput = useRef('search-word-input-product');
				useListener('click-pay', this.clickPay);
			}
			_clearSearch() {
	            this.searchWordInput.el.value = '';
	            this.trigger('clear-search');
	        }
			draftFilter(){
				this.state.filter_state  = 'Unpaid/Draft';
				this.state.query = 'draft';
				const pos_orders = this.pos_orders;
				this.render();
			}
			paidFilter(){
				this.state.filter_state  = 'Paid';
				this.state.query = 'paid';
				const pos_orders = this.pos_orders;
				this.render();
			}
			doneFilter(){
				this.state.filter_state  = 'Posted';
				this.state.query = 'done';
				const pos_orders = this.pos_orders;
				this.render();
			}
			invoicedFilter(){
				this.state.filter_state  = 'Invoiced';
				this.state.query = 'invoiced';
				const pos_orders = this.pos_orders;
				this.render();
			}
			refresh_orders(){
				$('.input-search-orders').val('');
				this.state.query = '';
				this.props.selected_partner_id = false;
				this.state.filter_state  = '';
				this.render();
			}

			remove_current_orderlines(){
				let self = this;
				let order = self.env.pos.get_order();
				let orderlines = order.get_orderlines();
				if(orderlines.length > 0){
					for (let line in orderlines)
					{
						order.remove_orderline(order.get_orderlines());
					}
				} 
			}

			async clickPay(event){
				let self = this;
				let old_order = self.env.pos.get_order();
				let order = event.detail;
				let o_id = parseInt(event.detail.id);
				let orderlines = [];
				let amount_due = order.amount_total - order.amount_paid
				$.each(order.lines, function(index, value) {
					let ol = self.env.pos.db.get_orderline_by_id[value];
					orderlines.push(ol);
				});
				self.remove_current_orderlines();
				if(orderlines.length > 0){
					old_order.name = order.pos_reference;
					old_order.is_partial = order.is_partial;
					old_order.amount_due = order.amount_total - order.amount_paid;
					old_order.barcode = order.barcode;
					old_order.barcode_img = order.barcode_img;
					old_order.is_paying_partial = true;
					old_order.amount_paid  = order.amount_paid;
				}

				if (order.partner_id) {
					let partner = self.env.pos.db.get_partner_by_id(order.partner_id[0]);
					old_order.set_partner(partner);
				}

				orderlines.forEach(function(ol) {
					let product = self.env.pos.db.get_product_by_id(ol.product_id[0]);
					old_order.add_product(product, {
						quantity: parseFloat(ol.qty),
						price: ol.price_unit,
						discount: ol.discount,
					});
				});

				if(amount_due > 0 && order.amount_paid != 0)
				{
					let product_for_due = self.env.pos.config.partial_product_id;
					if(product_for_due)
					{
						let prd = self.env.pos.db.get_product_by_id(product_for_due[0]);
						if(prd == undefined){
							self.showPopup('ErrorPopup', {
								title: self.env._t('Configurar Producto'),
								body: self.env._t('Parece haber algún error en la carga del producto, verifica que su categoría no esté restringida.'),
							});
						}else{
							old_order.add_product(prd,{
								quantity: 1.0,
								price: -order.amount_paid,
								discount: 0
							});							
						}
					}
					else{
						return self.showPopup('ErrorPopup', {
							title: self.env._t('Configurar producto'),
							body: self.env._t('Por favor selecciona un producto para los apartados.'),
						});
					}
				}
				if(old_order.orderlines.length > 0){
					self.trigger('close-temp-screen');
					self.showScreen('PaymentScreen');			
				}
			}

		}
		
	Registries.Component.extend(POSOrdersScreen, PayPOSOrdersScreen);

	return POSOrdersScreen;
});


