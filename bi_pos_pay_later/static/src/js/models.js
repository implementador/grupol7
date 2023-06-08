odoo.define('bi_pos_pay_later.models', function(require) {
	"use strict";

	var core = require('web.core');
	var utils = require('web.utils');
	var PosDB = require('point_of_sale.DB');
	var round_pr = utils.round_precision;
	var field_utils = require('web.field_utils');
	const Registries = require('point_of_sale.Registries');
	var { Order, Orderline, PosGlobalState} = require('point_of_sale.models');


	const POSPayLater = (PosGlobalState) => class POSPayLater extends PosGlobalState {

		async _processData(loadedData) {
	        await super._processData(...arguments);
	        this.pos_order = loadedData['pos_order'] || [];
        }
    }
    Registries.Model.extend(PosGlobalState, POSPayLater);

    PosDB.include({
		get_unpaid_orders: function(){
			var saved = this.load('unpaid_orders',[]);
			var orders = [];
			for (var i = 0; i < saved.length; i++) {
				let odr = saved[i].data;
				if(!odr.is_paying_partial && !odr.is_partial && !odr.is_draft_order){
					orders.push(saved[i].data);
				}
				if(odr.is_paying_partial || odr.is_partial || odr.is_draft_order){
					saved = _.filter(saved, function(o){
						return o.id !== odr.uid;
					});
				}
			}
			this.save('unpaid_orders',saved);
			return orders;
		},
	});

    const CustomOrder = (Order) => class CustomOrder extends Order{

    	constructor(obj, options) {
    		super(...arguments);
    		var self = this;
			this.is_partial    = false;
			this.is_paying_partial    = false;
			this.amount_due    = 0;
			this.amount_paid    = 0;
			this.is_draft_order = false;
			this.set_is_partial();

    	}
    	set_is_partial(set_partial){
    		this.is_partial = set_partial || false;
    	}
    	export_as_JSON(){
    		const json = super.export_as_JSON(...arguments);
    		json.is_partial = this.is_partial || false;
			json.amount_due = this.get_partial_due();
			json.is_paying_partial = this.is_paying_partial;
			json.is_draft_order = this.is_draft_order || false;
			return json;
    	}
    	init_from_JSON(json){
    		super.init_from_JSON(...arguments);
    		this.is_partial = json.is_partial;
			this.amount_due = json.amount_due;
			this.is_paying_partial = json.is_paying_partial;
			this.is_draft_order = json.is_draft_order;
    	}
    	get_partial_due(){
    		let due = 0;
			if(this.get_due() > 0){
				due = this.get_due();
			}
			return due
    	}
    }
    Registries.Model.extend(Order, CustomOrder);
});