odoo.define('grupol7_liquidacion_qr.CouponButton', function (require) {
    'use strict';

    const { PosComponent } = require('point_of_sale.PosComponent');
    const ProductScreen = require('point_of_sale.ProductScreen');
    const Registries = require('point_of_sale.Registries');
    const { useListener } = require('web.custom_hooks');

    class CouponButton extends PosComponent {
        setup() {
            super.setup();
            useListener('click', this.onClick);
        }

        async onClick() {
            const { confirmed, payload } = await this.showPopup('TextInputPopup', {
                title: this.env._t('Canjear cupón'),
                startingValue: '',
                confirmText: this.env._t('Validar'),
                placeholder: this.env._t('Escanea o escribe el código'),
            });
            if (!confirmed) return;

            const code = (payload || '').trim();
            if (!code) return;

            try {
                const res = await this.rpc({
                    model: 'liquidation.coupon',
                    method: 'pos_validate_coupon',
                    args: [code, this.env.pos.config.id],
                });

                const product = this.env.pos.db.get_product_by_id(res.product_id);
                if (!product) {
                    await this.showPopup('ErrorPopup', {
                        title: this.env._t('Producto no cargado en PdV'),
                        body: this.env._t('Actualiza la sesión del PdV e inténtalo de nuevo.'),
                    });
                    return;
                }

                this.currentOrder.add_product(product, {
                    price: res.price,
                    extras: {
                        liq_coupon_id: res.coupon_id,
                        liq_coupon_code: code,
                        liq_damage: res.damage || '',
                    },
                });

                const line = this.currentOrder.get_last_orderline();
                if (line) {
                    line.set_unit_price(res.price);
                    line.price_manually_set = true;
                    line.set_full_product_name(`[Cupón] ${product.display_name}`);
                }

                await this.showPopup('ConfirmPopup', {
                    title: this.env._t('Cupón aplicado'),
                    body: this.env._t(`Se aplicó el cupón ${code}`),
                });
            } catch (err) {
                const msg = (err && err.message) ||
                            (err && err.data && err.data.message) ||
                            this.env._t('Cupón inválido o no autorizado.');
                await this.showPopup('ErrorPopup', {
                    title: this.env._t('No se pudo aplicar'),
                    body: msg,
                });
            }
        }
    }

    CouponButton.template = 'CouponButton';

    ProductScreen.addControlButton({
        component: CouponButton,
        condition: function () {
            return true; // botón siempre visible
        },
    });

    Registries.Component.add(CouponButton);
    return CouponButton;
});
