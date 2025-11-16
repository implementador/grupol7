odoo.define('grupol7_liquidacion_qr.qr_button_ux', function (require) {
    "use strict";

    const Registries = require('point_of_sale.Registries');
    const ProductScreen = require('point_of_sale.ProductScreen');

    const G7CouponPos = (ProductScreen) => class extends ProductScreen {
        mounted() {
            super.mounted();
            // Ocultar el botón nativo "Customer Note" para evitar concatenaciones
            const noteBtn = this.el.querySelector('button[aria-label="Customer Note"]');
            if (noteBtn) noteBtn.style.display = 'none';

            // Inyectar nuestro botón solo una vez
            if (!this.el.querySelector('.g7-coupon-btn')) {
                const container =
                    this.el.querySelector('.control-buttons') ||
                    this.el.querySelector('.control-panel .buttons') ||
                    this.el;
                if (container) {
                    const btn = document.createElement('button');
                    btn.className = 'button g7-coupon-btn';
                    btn.setAttribute('aria-label', 'Cupón QR');
                    btn.innerHTML = '<i class="fa fa-qrcode"></i><span style="margin-left:6px">Cupón QR</span>';
                    btn.addEventListener('click', () => this._onClickCoupon());
                    container.appendChild(btn);
                }
            }
        }

        async _onClickCoupon() {
            const { confirmed, payload } = await this.showPopup('TextInputPopup', {
                title: this.env._t('Cupón QR'),
                startingValue: '',
                confirmText: this.env._t('Aplicar'),
                cancelText: this.env._t('Cancelar'),
                placeholder: this.env._t('Escanee o escriba el código del cupón'),
            });
            if (!confirmed) return;

            const code = (payload || '').trim();
            if (!code) return;

            // Validación en backend
            let res;
            try {
                res = await this.rpc({
                    model: 'liquidation.coupon',
                    method: 'pos_validate_coupon',
                    args: [code, this.env.pos.config.id],
                });
            } catch (e) {
                return this.showPopup('ErrorPopup', {
                    title: this.env._t('Cupón'),
                    body: e?.data?.message || this.env._t('No fue posible validar el cupón.'),
                });
            }

            const product = this.env.pos.db.get_product_by_id(res.product_id);
            if (!product) {
                return this.showPopup('ErrorPopup', {
                    title: this.env._t('Cupón'),
                    body: this.env._t('El producto del cupón no está disponible en este PdV.'),
                });
            }

            const order = this.currentOrder;
            const line = order.add_product(product, {
                price: res.price,
                extras: { coupon_id: res.coupon_id, coupon_code: code },
            });

            try {
                await this.rpc({
                    model: 'liquidation.coupon',
                    method: 'pos_redeem_coupon',
                    args: [code, order.uid, line.id],
                });
            } catch (e) {
                this.showPopup('ErrorPopup', {
                    title: this.env._t('Cupón'),
                    body: this.env._t('Se agregó la línea, pero no se logró marcar el cupón como usado. Revise el backend.'),
                });
            }
        }
    };
    Registries.Component.extend(ProductScreen, G7CouponPos);
});
