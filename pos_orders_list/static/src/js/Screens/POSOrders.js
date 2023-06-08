odoo.define('point_of_sale.POSOrders', function(require) {
	'use strict';

	const PosComponent = require('point_of_sale.PosComponent');
	const Registries = require('point_of_sale.Registries');

	class POSOrders extends PosComponent {
		setup() {
            super.setup();
		}

		get highlight() {
			return this.props.order !== this.props.selectedPosOrder ? '' : 'highlight';
		}

		GetFormattedDate(date) {
		    var month = ("0" + (date.getMonth() + 1)).slice(-2);
		    var day  = ("0" + (date.getDate())).slice(-2);
		    var year = date.getFullYear();
		    var hour =  ("0" + (date.getHours())).slice(-2);
		    var min =  ("0" + (date.getMinutes())).slice(-2);
		    var seg = ("0" + (date.getSeconds())).slice(-2);
		    return year + "-" + month + "-" + day + " " + hour + ":" +  min + ":" + seg;
		}

		get_order_date(dt){
			/*dt +=' UTC' */
			let a=dt.split(" ");			
			let a1=a[0]+'T';
			let a2=a[1]+'Z';
			let final_date=a1+a2;
			let date = new Date(final_date);
			let new_date = this.GetFormattedDate(date);
			return new_date
		}
	}
	POSOrders.template = 'POSOrders';

	Registries.Component.add(POSOrders);

	return POSOrders;
});
