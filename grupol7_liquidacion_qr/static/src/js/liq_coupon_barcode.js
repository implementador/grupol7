/** Odoo 16 POS - interceptar escaneo LIQ/ */
odoo.define('grupol7_liquidacion_qr.LiqCouponBarcode', function (require) {
"use strict";
const Registries = require('point_of_sale.Registries');
const ProductScreen = require('point_of_sale.ProductScreen');


const LiqCouponBarcode = (ProductScreen) => class extends ProductScreen {
async _barcodeProductAction(code) {
if (code.code && code.code.startsWith('LIQ/')) {
const couponCode = code.code.substring(4);
try {
const data = await this.rpc({
model: 'liquidation.coupon',
method: 'pos_validate_coupon',
args: [couponCode, this.env.pos.config.id],
});
const product = this.env.pos.db.get_product_by_id(data.product_id);
if (!product) {
this.showPopup('ErrorPopup', { title: 'Producto no disponible en POS' });
return true;
}
const order = this.env.pos.get_order();
const line = order.add_product(product, {
price: data.price,
extras: { coupon_code: couponCode, coupon_id: data.coupon_id, is_liq: true },
});
if (line) {
line.set_unit_price(data.price); // fija precio
line.price_manually_set = true; // evita recomputes
}
this.showTempScreen('NotificationScreen', { message: 'Cupón LIQ aplicado' });
} catch (err) {
this.showPopup('ErrorPopup', { title: 'Cupón inválido', body: err && err.message ? err.message : '' });
}
return true; // manejado por nosotros
}
return await super._barcodeProductAction(...arguments);
}
};
Registries.Component.extend(ProductScreen, LiqCouponBarcode);
});
