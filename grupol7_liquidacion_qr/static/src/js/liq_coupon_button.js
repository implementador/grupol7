/** @odoo-module */
import { PosComponent } from 'point_of_sale.PosComponent';
import { ProductScreen } from 'point_of_sale.ProductScreen';
import Registries from 'point_of_sale.Registries';
import { useListener } from '@web/core/utils/hooks';
import {Gui} from 'point_of_sale.Gui';

console.log('CouponButton loaded');

class CouponButton extends PosComponent {
    setup() {
        super.setup();
        useListener('click', this.onClick);
    }
    async onClick() {
        const { confirmed, payload } = await Gui.showPopup('TextInputPopup', {
            title: this.env._t('Canjear cupón de liquidación'),
            startingValue: '',
            confirmText: this.env._t('Validar'),
            cancelText: this.env._t('Cancelar'),
            placeholder: this.env._t('Escribe o escanea el código'),
        });
        if (!confirmed || !payload) return;

        try {
            // Validar cupón (método de tu modelo Python)
            const data = await this.rpc({
                model: 'liquidation.coupon',
                method: 'pos_validate_coupon',
                args: [payload, this.env.pos.config.id],
            });

            // Añadir el producto con el precio de liquidación
            const product = this.env.pos.db.get_product_by_id(data.product_id);
            if (!product) {
                throw new Error(this.env._t('Producto no cargado en POS.'));
            }
            this.currentOrder.add_product(product, {
                price: data.price,
                extras: { coupon_id: data.coupon_id, damage_grade: data.grade },
            });

            // Marcar el cupón como redimido ligándolo a la línea creada
            const line = this.currentOrder.get_selected_orderline();
            await this.rpc({
                model: 'liquidation.coupon',
                method: 'pos_redeem_coupon',
                args: [payload, this.env.pos.get_order().uid, (line && line.uid) || false],
            });

            Gui.showPopup('ConfirmPopup', {
                title: this.env._t('Cupón aplicado'),
                body: this.env._t('Se aplicó el precio de liquidación.'),
            });
        } catch (err) {
            Gui.showPopup('ErrorPopup', {
                title: this.env._t('No se pudo canjear'),
                body: (err && err.message) || this.env._t('Error desconocido.'),
            });
        }
    }
}
CouponButton.template = 'Grupol7CouponButton';

// Registrar botón en la ActionPad del ProductScreen
ProductScreen.addControlButton({
    component: CouponButton,
    condition() { return true; },
});
Registries.Component.add(CouponButton);
export default CouponButton;
