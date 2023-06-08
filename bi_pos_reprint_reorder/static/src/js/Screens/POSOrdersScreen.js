odoo.define('bi_pos_reprint_reorder.POSOrdersScreen', function (require) {
	'use strict';

	const POSOrdersScreen = require('pos_orders_list.POSOrdersScreen');
	const Registries = require('point_of_sale.Registries');
	const { useListener } = require("@web/core/utils/hooks");
    const { useExternalListener,useState } = owl;

	const BiPOSOrdersScreen = (POSOrdersScreen) =>
		class extends POSOrdersScreen {
			setup() {
            	super.setup();
				useListener('click-reorder', this.clickReOrder);
				useListener('click-reprint', this.clickReprint);
			}
			
			clickReOrder(order){
				let self = this;
				// let order = event.detail;
				let o_id = parseInt(order.id);
				let orderlines =  self.orderlines;				
				let pos_lines = [];

				for(let n=0; n < orderlines.length; n++){
					if (orderlines[n]['order_id'][0] ==o_id){
						pos_lines.push(orderlines[n])
					}
				}
				self.showPopup('ReOrderPopup', {
					'order': event.detail, 
					'orderlines':pos_lines,
				});
			}

			async clickReprint(order){
				let self = this;
				// let order = event.detail;

				await self.rpc({
					model: 'pos.order',
					method: 'print_pos_receipt',
					args: [order.id],
				}).then(function(output) {
					let data = output;
					data['order'] = order;
					self.showTempScreen('OrderReprintScreen',data);
				});

			}
		}
		
	Registries.Component.extend(POSOrdersScreen, BiPOSOrdersScreen);

	return POSOrdersScreen;
});


