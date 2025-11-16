/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { PosComponent } from "point_of_sale.PosComponent";
import Registries from "point_of_sale.Registries";
import ProductScreen from "point_of_sale.ProductScreen";

class QrCouponButton extends PosComponent {
    setup() {
        super.setup();
        this.orm = useService("orm");
    }

    async onClick() {
        // 1) Pedir código (teclado/escáner)
        const { confirmed, payload: code } = await this.showPopup("TextInputPopup", {
            title: _t("Cupón QR"),
            body: _t("Escribe o escanea el código del cupón."),
            startingValue: "",
            confirmText: _t("Validar"),
        });
        if (!confirmed || !code) return;

        // 2) Validar cupón en servidor
        let data;
        try {
            data = await this.orm.call(
                "liquidation.coupon",
                "pos_validate_coupon",
                [[], code, this.env.pos.config.id]
            );
        } catch (err) {
            console.error(err);
            await this.showPopup("ErrorPopup", {
                title: _t("Cupón no válido"),
                body: err.message || _t("No fue posible validar el cupón."),
            });
            return;
        }

        // 3) Buscar producto en caché del POS
        const productId = (data.product_id && data.product_id.id) || data.product_id;
        let product =
            (this.env.pos.db && this.env.pos.db.get_product_by_id(productId)) ||
            (this.env.pos.get_product_by_id && this.env.pos.get_product_by_id(productId));

        if (!product) {
            await this.showPopup("ErrorPopup", {
                title: _t("Cupón OK pero…"),
                body: _t("El producto no está cargado en este PdV. Actualiza artículos."),
            });
            return;
        }

        // 4) Crear línea con precio del cupón y lote (si aplica)
        const options = {
            quantity: 1,
            merge: false,
            price: data.price,
        };
        if (data.requires_lot) {
            options.draftPackLotLines = [{ lot_name: data.lot_name || "" }];
        }

        try {
            this.currentOrder.add_product(product, options);

            const line = this.currentOrder.get_last_orderline();
            if (line) {
                line.set_unit_price(data.price);
                if (line.set_note) {
                    line.set_note(`Cupón QR: ${data.info}`);
                }
                line.coupon_qr_code = code;
                line.coupon_id = data.coupon_id;
            }

            await this.showPopup("ConfirmPopup", {
                title: _t("Cupón aplicado"),
                body: `${product.display_name} - $${data.price}`,
            });
        } catch (err) {
            console.error(err);
            await this.showPopup("ErrorPopup", {
                title: _t("No se pudo añadir la línea"),
                body: _t("El cupón es válido, pero el producto no pudo agregarse automáticamente."),
            });
        }
    }
}
QrCouponButton.template = "QrCouponButton"; // Tu template ya lo define el archivo UX

ProductScreen.addControlButton({
    component: QrCouponButton,
    condition: () => true,
});

Registries.Component.add(QrCouponButton);

export default QrCouponButton;
