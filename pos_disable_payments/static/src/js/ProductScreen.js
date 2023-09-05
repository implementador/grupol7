odoo.define('pos_disable_payments.BiProductScreen', function(require) {
    'use strict';

    const ProductScreen = require('point_of_sale.ProductScreen');
    const Registries = require('point_of_sale.Registries');

    const BiProductScreen = ProductScreen => class extends ProductScreen {

        _setValue(val) {
            let allow_rmv_ol = this.env.pos.get_cashier().is_allow_remove_orderline;
            console.log('allow_rmv_ol', allow_rmv_ol);
            let is_allow_qty = this.env.pos.get_cashier().is_allow_qty;
            if (allow_rmv_ol == false || is_allow_qty == false) {
                if (val == '' || val == 'remove') {
                    alert("Sorry,You are not allowed to perform this operation");
                    return
                }
            }
            if (this.currentOrder.get_selected_orderline()) {
                if (this.env.pos.numpadMode === 'quantity') {
                    const result = this.currentOrder.get_selected_orderline().set_quantity(val);
                    // if (!result) NumberBuffer.reset();
                } else if (this.env.pos.numpadMode === 'discount') {
                    this.currentOrder.get_selected_orderline().set_discount(val);
                } else if (this.env.pos.numpadMode === 'price') {
                    var selected_orderline = this.currentOrder.get_selected_orderline();
                    selected_orderline.price_manually_set = true;
                    selected_orderline.set_unit_price(val);
                }
            }
        }

    };

    Registries.Component.extend(ProductScreen, BiProductScreen);
    return ProductScreen;
});