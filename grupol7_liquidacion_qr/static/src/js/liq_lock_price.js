/** @odoo-module **/
import { Orderline } from 'point_of_sale.models';
import { patch } from 'web.utils';

patch(Orderline.prototype, 'liq-lock-price', {
    can_be_edited() {
        // Si trae el flag del cupón, no permitir edición de precio
        if (this.get_extras()?.liq_coupon_code) return false;
        return this._super(...arguments);
    },
});
