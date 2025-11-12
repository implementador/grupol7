/** @odoo-module **/
import { ProductScreen } from 'point_of_sale.ProductScreen';
import Registries from 'point_of_sale.Registries';
import rpc from 'web.rpc';

const LiqCouponPatch = (ProductScreen) => class extends ProductScreen {

    /** Intenta manejar un cupón. Devuelve true si lo consumió. */
    async _tryLiqCoupon(raw) {
        const code = (raw && raw.code) ? raw.code : (raw || '');
        const m = code.trim().match(/^(?:LIQ\/)?([A-Za-z0-9_-]{4,64})$/);
        if (!m) return false;  // no parece cupón

        try {
            const res = await rpc.query({
                model: 'liquidation.coupon',
                method: 'pos_scan_coupon',
                args: [[], m[1], this.env.pos.config.id],
            });
            if (!res || !res.ok) {
                await this.showPopup('ErrorPopup', {
                    title: this.env._t('Cupón no válido'),
                    body: (res && res.message) || this.env._t('No se pudo validar el cupón.'),
                });
                return true;
            }
            const product = this.env.pos.db.get_product_by_id(res.product_id);
            if (!product) {
                await this.showPopup('ErrorPopup', {
                    title: this.env._t('Producto no disponible'),
                    body: this.env._t('El producto del cupón no está cargado en este POS.'),
                });
                return true;
            }
            this.currentOrder.add_product(product, {
                price: res.price,
                extras: { liq_coupon_code: res.code },
            });
            return true;
        } catch (e) {
            await this.showPopup('ErrorPopup', {
                title: this.env._t('Error de red'),
                body: this.env._t('No se pudo contactar al servidor.'),
            });
            return true;
        }
    }

    /** Si el escaneo llega como “desconocido”, probamos cupón antes del popup estándar. */
    async _barcodeUnknownAction(code) {
        const handled = await this._tryLiqCoupon(code);
        if (handled) return true;
        return super._barcodeUnknownAction(...arguments);
    }

    /** Si el POS cree que es “producto”, igual probamos cupón primero. */
    async _barcodeProductAction(code) {
        const handled = await this._tryLiqCoupon(code);
        if (handled) return true;
        return super._barcodeProductAction(...arguments);
    }
};
Registries.Component.extend(ProductScreen, LiqCouponPatch);
