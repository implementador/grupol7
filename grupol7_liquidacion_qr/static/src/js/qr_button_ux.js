	/** @odoo-module **/

import { PosComponent } from 'point_of_sale.PosComponent';
import { ProductScreen } from 'point_of_sale.ProductScreen';
import Registries from 'point_of_sale.Registries';
import { useService } from "@web/core/utils/hooks";

class QrCouponButton extends PosComponent {
    setup() {
        super.setup();
        this.orm = useService("orm");
    }

    async onClick() {
        const { confirmed, payload: code } = await this.showPopup('TextInputPopup', {
            title: this.env._t('Cupón QR'),
            startingValue: '',
            confirmText: this.env._t('Validar'),
        });
        if (!confirmed || !code) return;

        let data;
        try {
            data = await this.orm.call(
                'liquidation.coupon',
                'pos_validate_coupon',
                [code, this.env.pos.config.id],
                {}
            );
        } catch (e) {
            const msg = (e?.message) || (e?.data?.message) || this.env._t('Error al validar el cupón.');
            await this.showPopup('ErrorPopup', { title: this.env._t('Cupón QR'), body: msg });
            return;
        }

        const product = this.env.pos.db.get_product_by_id(data.product_id);
        if (!product) {
            await this.showPopup('ErrorPopup', {
                title: this.env._t('Producto no cargado'),
                body: this.env._t('Actualiza el POS e inténtalo de nuevo.'),
            });
            return;
        }

        const order = this.env.pos.get_order();
        order.add_product(product, {
            price: data.price,
            extras: { liq_coupon_id: data.coupon_id, liq_coupon_info: data.info },
        });

        await this.showPopup('ConfirmPopup', {
            title: this.env._t('Cupón OK'),
            body: `${this.env._t('Precio')}: ${data.price}\n${data.info || ''}`.trim(),
        });
    }
}
QrCouponButton.template = 'QrCouponButton';
Registries.Component.add(QrCouponButton);
ProductScreen.addControlButton({ component: QrCouponButton, condition() { return true; }});

export default QrCouponButton;

