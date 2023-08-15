odoo.define('bi_pos_pay_later.BiProductScreen', function(require) {
    'use strict';

    const ProductScreen = require('point_of_sale.ProductScreen');
    const Registries = require('point_of_sale.Registries');

    const BiProductScreen = ProductScreen => class extends ProductScreen {

        async _clickProduct(event) {
            if (!this.currentOrder) {
                this.env.pos.add_new_order();
            }
            const product = event.detail;
            if(product.qty_available > -10){

	            const options = await this._getAddProductOptions(product);
	            // Do not add product if options is undefined.
	            if (!options) return;
	            // Add the product after having the extra information.
	            await this._addProduct(product, options);
	            // NumberBuffer.reset();
            }else{
            	alert("This product is out of stock")
            }
        }

    };

    Registries.Component.extend(ProductScreen, BiProductScreen);
    return ProductScreen;
});
