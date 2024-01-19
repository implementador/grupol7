odoo.define('bi_pos_show_product_info.ProductScreen', function(require) {
    "use strict";

    const Registries = require('point_of_sale.Registries');
    const ProductScreen = require('point_of_sale.ProductScreen');
    const { useListener } = require("@web/core/utils/hooks");

    const BiProductScreen = (ProductScreen) =>
        class extends ProductScreen {
            setup() {
                super.setup();
                useListener('click-product-info', this._clickProductInfo);
            }

            async _clickProductInfo(product) {
                const info = await this.env.pos.getProductInfo(product.detail, 1);
                await this.showPopup('ProductInfoPopup', { info: info , product: product.detail });
            }
        };
    Registries.Component.extend(ProductScreen, BiProductScreen);
    return ProductScreen;
});