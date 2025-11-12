/** @odoo-module **/

import { ProductScreen } from 'point_of_sale.ProductScreen';
import Registries from 'point_of_sale.Registries';
import rpc from 'web.rpc';

const LiqCouponPatch = (ProductScreen) => class extends ProductScreen {
    /**
     * Se ejecuta cuando el POS interpreta el escaneo como "producto".
     * Aquí interceptamos primero para intentar tratarlo como CUPÓN.
     */
    async _barcodeProductAction(barcode) {
        const code = (barcode && barcode.code) ? barcode.code : (barcode || '');
        const m = code.trim().match(/^(?:LIQ\/)?([A-Za-z0-9_-]{6,32})$/);
        if (m) {
            const handled = await this._handleLiqCoupon(m[1]);
            if (handled) {
                // Consumido: NO continuar con la lógica por defecto de producto
                return true;
            }
        }
        // Si no parecía cupón o algo falló, continuar con la lógica estándar
        return await super._barcodeProductAction(...arguments);
    }

    async _handleLiqCoupon(cleanCode) {
        try {
            const res = await rpc.query({
                model: 'liquidation.coupon',
                method: 'pos_scan_coupon',
                args: [[], cleanCode, this.env.pos.config.id],
            });
            if (!res || !res.ok) {
                await this.showPopup('ErrorPopup', {
                    title: this.env._t('Cupón no válido'),
                    body: (res && res.message) || this.env._t('No se pudo validar el cupón.'),
                });
                return true; // ya lo manejamos
            }
            const product = this.env.pos.db.get_product_by_id(res.product_id);
            if (!product) {
                await this.showPopup('ErrorPopup', {
                    title: this.env._t('Producto no disponible'),
                    body: this.env._t('El producto del cupón no está cargado en este POS.'),
                });
                return true;
            }
            const order = this.currentOrder;
            order.add_product(product, {
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
};

Registries.Component.extend(ProductScreen, LiqCouponPatch);
