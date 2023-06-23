odoo.define('bi_pos_pay_later.PosOrdersDetailRestric', function(require) {
	'use strict';

	
	const PosComponent = require('point_of_sale.PosComponent');
	const AbstractAwaitablePopup = require('point_of_sale.AbstractAwaitablePopup');
	const Registries = require('point_of_sale.Registries');
    const { useListener } = require("@web/core/utils/hooks");
    const { useExternalListener,useState } = owl;

	class PosOrdersDetailRestric extends AbstractAwaitablePopup {
		setup() {
			super.setup();
		}

		async discard_order(){

			var order = this.env.pos.get_order()

			if(order.get_orderlines().length > 0 ){
				this.env.pos.removeOrder(order);
                this.env.pos.add_new_order()

                this.env.posbus.trigger('close-popup', {
            		popupId: this.props.id });
				await this.showTempScreen('POSOrdersScreen', {
					'selected_partner_id': false 
				});
			}else{
				this.env.posbus.trigger('close-popup', {
	            popupId: this.props.id });
			}
		}		
	}
	
	PosOrdersDetailRestric.template = 'PosOrdersDetailRestric';
	Registries.Component.add(PosOrdersDetailRestric);
	return PosOrdersDetailRestric;
});