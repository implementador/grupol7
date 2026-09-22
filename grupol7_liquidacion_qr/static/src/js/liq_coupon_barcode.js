/** @odoo-module **/

import Registries from 'point_of_sale.Registries';
import { ProductScreen } from 'point_of_sale.ProductScreen';

const LiqUnknownBarcodePatch = (ProductScreen) => class extends ProductScreen {
    async _barcodeErrorAction(code) {
        // Intentar tratarlo como Cupón LIQ antes del popup de error
        try {
            // Filtro simple para no spamear RPC con códigos raros
            const clean = (code || '').trim();
            if (clean.length >= 6 && clean.length <= 64) {
                const result = await this.rpc({
                    model: 'liquidation.coupon',
                    method: 'pos_apply_coupon',
                    args: [clean, this.env.pos.config.id],
                });
                if (result && result.product_id && !result.error) {
                    const product = this.env.pos.db.get_product_by_id(result.product_id);
                    if (product) {
                        const order = this.env.pos.get_order();
                        const line = order.add_product(product, { price: result.price, extras: { liq_coupon_code: clean } });
                        line.set_unit_price(result.price);
                        line.price_manually_set = true;
                        return; // Consumimos el “desconocido”
                    }
                }
            }
        } catch (e) {
            console.warn('[LIQ] pos_apply_coupon error', e);
        }
        // Si no era cupón válido, seguimos con el comportamiento estándar
        return super._barcodeErrorAction(code);
    }
};
Registries.Component.extend(ProductScreen, LiqUnknownBarcodePatch);
