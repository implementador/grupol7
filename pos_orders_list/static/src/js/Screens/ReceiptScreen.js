odoo.define('pos_orders_list.ReceiptScreen', function(require) {
	"use strict";

	const OrderReceipt = require('point_of_sale.OrderReceipt');
	const ReceiptScreen = require('point_of_sale.ReceiptScreen');
	const Registries = require('point_of_sale.Registries');
	const { onMounted, useRef, status } = owl;

	const ReceiptScreenOrder = OrderReceipt => 
		class extends OrderReceipt {
			setup() {
            	super.setup();
            	onMounted(() => {
                    var order = this.env.pos.get_order();
					
					$("#barcode_print").barcode(
						order.barcode, // Value barcode (dependent on the type of barcode)
						"code128" // type (string)
					);
                });
            	
			}

			
			
			get receiptBarcode(){
				var order = this.env.pos.get_order();
				return true;
			}

			
		
	};
	Registries.Component.extend(OrderReceipt, ReceiptScreenOrder);
	return OrderReceipt
});