odoo.define('bi_pos_reprint_reorder.OrderReprintReceipt', function(require) {
	'use strict';

	const PosComponent = require('point_of_sale.PosComponent');
	const Registries = require('point_of_sale.Registries');
	const { onMounted, useRef, status } = owl;

	class OrderReprintReceipt extends PosComponent {
		constructor() {
			super(...arguments);
			onMounted(() => {
                var order = this.env.pos.get_order();
				
				$("#barcode_print1").barcode(
					order.barcode, // Value barcode (dependent on the type of barcode)
					"code128" // type (string)
				);
            });
		}
		
		get receiptBarcode(){
			let barcode = this.props.barcode;
			$("#barcode_print1").barcode(
				barcode, // Value barcode (dependent on the type of barcode)
				"code128" // type (string)
			);
		return true
		}
	}
	OrderReprintReceipt.template = 'OrderReprintReceipt';

	Registries.Component.add(OrderReprintReceipt);

	return OrderReprintReceipt;
});
