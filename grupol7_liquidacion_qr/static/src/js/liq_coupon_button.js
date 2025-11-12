/** @odoo-module **/

import { PosComponent } from 'point_of_sale.PosComponent';
import Registries from 'point_of_sale.Registries';
import { ProductScreen } from 'point_of_sale.ProductScreen';

class L7CouponButton extends PosComponent {
    async onClick() {
        // Pedir código (puedes escanear aquí o teclear)
        const { confirmed, payload } = await this.showPopup('TextInputPopup', {
            title: this.env._t('Escanea o escribe el cupón'),
            startingValue: '',
            confirmText: this.env._t('Validar'),
            placeholder: this.env._t('Código de cupón'),
        });
        if (!confirmed || !payload) return;

        const code = (payload || '').trim();
        try {
            // Llama a tu método Python que ya existe
            const res = await this.env.services.rpc({
                model: 'liquidation.coupon',
                method: 'pos_validate_coupon',
                args: [code, this.env.pos.config.id],
            });

            // Cargar el producto del cupón y agregar con precio del cupón
            const product = this.env.pos.db.get_product_by_id(res.product_id);
            if (!product) {
                return this.showPopup('ErrorPopup', {
                    title: this.env._t('Producto no disponible en el PdV'),
                    body: this.env._t('El producto del cupón no fue cargado en esta sesión.'),
                });
            }

            const order = this.env.pos.get_order();
            order.add_product(product, {
                price: res.price,
                extras: {
                    liq_coupon_id: res.coupon_id,
                    liq_damage_grade: res.damage_grade,
                },
            });
        } catch (err) {
            const msg =
                (err && err.message && err.message.data && err.message.data.message)
                || (err && err.message)
                || this.env._t('No se pudo validar el cupón.');
            this.showPopup('ErrorPopup', {
                title: this.env._t('Cupón inválido'),
                body: msg,
            });
        }
    }
}
L7CouponButton.template = 'L7CouponButton';

// Mostrar el botón en la columna de botones de control del ProductScreen
ProductScreen.addControlButton({
    component: L7CouponButton,
    condition() { return true; },   // puedes filtrar por grupo, compañía, etc.
});

Registries.Component.add(L7CouponButton);
export default L7CouponButton;
