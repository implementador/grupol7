/** @odoo-module **/

import { Component } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { TextInputPopup } from "@point_of_sale/app/utils/input_popups/text_input_popup";
import { ErrorPopup } from "@point_of_sale/app/utils/popups/error_popup";

export class LiqCouponButton extends Component {
    setup() {
        this.popup = useService("popup");
        this.orm = useService("orm");
    }

    async onClick() {
        // Pedimos el código de cupón
        const { confirmed, payload } = await this.popup.add(TextInputPopup, {
            title: this.env._t("Cupón de liquidación"),
            body: this.env._t("Escanea o escribe el código del cupón"),
            startingValue: "",
            confirmText: this.env._t("Aplicar"),
            cancelText: this.env._t("Cancelar"),
            placeholder: "Ej. sY3WlyUJP19KLA",
        });
        if (!confirmed) return;
        const code = (payload || "").trim();
        if (!code) return;

        try {
            // Llamamos a nuestro método del backend
            const res = await this.orm.call(
                "liquidation.coupon",
                "pos_apply_coupon",
                [[], code, this.env.pos.config.id],
                {}
            );

            if (!res || !res.ok) {
                throw new Error((res && res.message) || this.env._t("Cupón inválido o no aplicable."));
            }

            // Obtenemos el producto en cache del POS y lo añadimos con el precio de liquidación
            const product = this.env.pos.db.get_product_by_id(res.product_id);
            if (!product) {
                throw new Error(this.env._t("El producto del cupón no está disponible en el POS."));
            }
            this.env.pos.get_order().add_product(product, {
                price: res.price,
                quantity: 1,
                merge: false,
                extras: { liq_coupon_code: code },
            });
        } catch (err) {
            await this.popup.add(ErrorPopup, {
                title: this.env._t("No se pudo aplicar el cupón"),
                body: (err && err.message) || this.env._t("Error inesperado."),
            });
        }
    }
}
LiqCouponButton.template = "grupol7_liquidacion_qr.LiqCouponButton";

// Registramos el botón en la barra de acciones del ProductScreen
ProductScreen.addControlButton({
    component: LiqCouponButton,
    condition: () => true,
    position: ["before", "SetCustomerButton"],
});
