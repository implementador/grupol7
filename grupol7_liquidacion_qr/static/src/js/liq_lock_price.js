/** Odoo 16 POS - bloquear edición de precio si línea es LIQ */
odoo.define('grupol7_liquidacion_qr.LiqLockPrice', function (require) {
"use strict";
const Registries = require('point_of_sale.Registries');
const Orderline = require('point_of_sale.Orderline');


const LiqOrderline = (Orderline) => class extends Orderline {
canBePriceModified() {
// si viene de cupón LIQ, no permitir edición de precio
const extras = (this.orderline && this.orderline.extras) || {};
if (extras.is_liq || this.orderline?.get_extra('is_liq')) {
return false;
}
return super.canBePriceModified();
}
};


Registries.Component.extend(Orderline, LiqOrderline);
});
