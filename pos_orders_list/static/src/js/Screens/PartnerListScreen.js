odoo.define('pos_orders_list.PartnerListScreen', function (require) {
	'use strict';

	const PartnerListScreen = require('point_of_sale.PartnerListScreen');
	const { useListener } = require("@web/core/utils/hooks");
    const { useExternalListener,useState } = owl;
	const models = require('point_of_sale.models');
	const Registries = require('point_of_sale.Registries');

	const BiPartnerListScreen = (PartnerListScreen) =>
		class extends PartnerListScreen {
			setup() {
            super.setup();
				// useListener('click-show-orders', this.showOrders);
			}

			async showOrders(partner){
				let partner_id = partner.id;
				await this.showTempScreen('POSOrdersScreen', {
					'selected_partner_id': partner_id 
				});
			}
		}
	Registries.Component.extend(PartnerListScreen, BiPartnerListScreen);

	return PartnerListScreen;
});
