odoo.define('bi_pos_pay_later.BiSeePOSOrdersButton', function (require) {
	'use strict';

	const SeePOSOrdersButton = require('pos_orders_list.SeePOSOrdersButton');
	const Registries = require('point_of_sale.Registries');
	// const { useListener } = require("@web/core/utils/hooks");
	const { onMounted, onWillUnmount, useRef } = owl;

	const BiSeePOSOrdersButton = (SeePOSOrdersButton) =>
		class extends SeePOSOrdersButton {
			
			setup() {
	            super.setup();
	            // useListener('click', this.onClick);
	        }
        
			async onClick() {
				var order = this.env.pos.get_order()
				if(order.get_orderlines().length > 0){
					// alert("pls first Complete current order or remove the order")
					this.showPopup('PosOrdersDetailRestric',{
					})
				}else{
					await this.showTempScreen('POSOrdersScreen', {
						'selected_partner_id': false 
					});
				}
			}
		}
		
	Registries.Component.extend(SeePOSOrdersButton, BiSeePOSOrdersButton);

	return SeePOSOrdersButton;
});


