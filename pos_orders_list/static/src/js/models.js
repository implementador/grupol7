// pos_orders_list js
odoo.define('pos_orders_list.models', function(require) {
	"use strict";

	var core = require('web.core');
	var utils = require('web.utils');
	var round_pr = utils.round_precision;
	var field_utils = require('web.field_utils');
	const Registries = require('point_of_sale.Registries');
	var { Order, Orderline, PosGlobalState} = require('point_of_sale.models');
	var PosDB = require("point_of_sale.DB");


	const BiCustomOrder = (Order) => class BiCustomOrder extends Order{
		constructor(obj, options) {
        	super(...arguments);
			this.barcode = this.barcode || "";
			this.set_barcode();
		}

		set_barcode(){
			var self = this;	
			var temp = Math.floor(100000000000+ Math.random() * 9000000000000)
			self.barcode =  temp.toString();
		}

		export_as_JSON() {
			const json = super.export_as_JSON(...arguments);
			json.barcode = this.barcode;
			return json;
		}

		init_from_JSON(json){
			super.init_from_JSON(...arguments);
			this.barcode = json.barcode;
		}

	}
	Registries.Model.extend(Order, BiCustomOrder);

	PosDB.include({
		init: function(options){
			this.get_orders_by_id = {};
			this.get_orders_by_barcode = {};
			this.get_orderline_by_id = {};
			this._super(options);
		},
	});
});