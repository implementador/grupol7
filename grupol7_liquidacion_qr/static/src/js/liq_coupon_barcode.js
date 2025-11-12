/** @odoo-module **/

import { ProductScreen } from 'point_of_sale.ProductScreen';
import Registries from 'point_of_sale.Registries';
import rpc from 'web.rpc';

const LiqCouponProductScreen = (ProductScreen) => class extends ProductScreen {
    mounted() {
        super.mounted();
        // Registra una regla que acepta LIQ/<codigo> o solo <codigo>
        this.env.pos.barcodeReader.addRule({
            name: 'liq-coupon',
            // 6–32 chars alfanum, guion y guion bajo; con o sin prefijo LIQ/
            pattern: /^(?:LIQ\/)?([A-Za-z0-9_-]{6,32})$/,
            callback: (barcode) => this._onLiqCouponScanned(barcode),
        });
    }
    willUnmount() {
        this.env.pos.barcodeReader.removeRule('liq-coupon');
        super.willUnmount();
    }
    async _onLiqCouponScanned(raw) {
        try {
            const res = await rpc.query({
                model: 'liquidation.coupon',
                method: 'pos_scan_coupon',
                args: [[], raw, this.env.pos.config.id],
            });
            if (!res || !res.ok) {
                await this.showPopup('ErrorPopup', {
                    title: this.env._t('Cupón no válido'),
                    body: (res && res.message) || this.env._t('No se pudo validar el cupón.'),
                });
                return true; // Consumir el escaneo para que no dispare “desconocido”.
            }
            const product = this.env.pos.db.get_product_by_id(res.product_id);
            if (!product) {
                await this.showPopup('ErrorPopup', {
                    title: this.env._t('Producto no disponible'),
                    body: this.env._t('El producto del cupón no está cargado en este POS.'),
                });
                return true;
            }
            // Agrega la línea con el precio de liquidación (sin permitir editar)
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
Registries.Component.extend(ProductScreen, LiqCouponProductScreen);
