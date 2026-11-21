/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { useBarcodeReader } from "@point_of_sale/app/barcode/barcode_reader";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { _t } from "@web/core/l10n/translation";

patch(ProductScreen.prototype, "grupol7_liquidacion_qr.LiqCouponBarcode", {
    setup() {
        super.setup();
        // Interceptar códigos que el POS no reconoce como producto/cliente/etc.
        useBarcodeReader({
            unknown: (code) => this._liquidationCouponScan(code),
            any:     (code) => this._liquidationCouponScan(code),
        });
    },

    async _liquidationCouponScan(code) {
        try {
            const rpc = this.env.services.rpc;
            const resp = await rpc("/grupol7/liq/coupon_scan", { code });
            if (resp && !resp.error) {
                const product = this.env.pos.db.get_product_by_id(resp.product_id);
                if (!product) {
                    await this.showPopup(ErrorPopup, {
                        title: _t("Producto no disponible en TPV"),
                        body: _t("Activa 'Disponible en TPV' en el producto del cupón."),
                    });
                    return true;
                }
                this.currentOrder.add_product(product, {
                    price: resp.clearance_price,
                    merge: false,
                    extras: { liq_coupon_id: resp.id, liq_coupon_code: resp.name },
                });
                return true; // manejado OK
            }
            if (resp && resp.error === "redeemed") {
                await this.showPopup(ErrorPopup, {
                    title: _t("Cupón ya canjeado"),
                    body: _t("Este cupón ya fue canjeado."),
                });
                return true;
            }
            return false; // no es cupón: deja que el POS muestre su popup estándar
        } catch (err) {
            await this.showPopup(ErrorPopup, {
                title: _t("Error validando cupón"),
                body: _t("Revisa la conexión e inténtalo de nuevo."),
            });
            return true;
        }
    },
});
