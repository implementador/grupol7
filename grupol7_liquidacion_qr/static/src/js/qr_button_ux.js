odoo.define('grupol7_liquidacion_qr.qr_button_ux', function (require) {
    "use strict";
    const Registries = require('point_of_sale.Registries');
    const ProductScreen = require('point_of_sale.ProductScreen');

    const G7CouponPatch = (ProductScreen) => class extends ProductScreen {
        mounted() {
            super.mounted();
            // Parchea el botón nativo "Nota de cliente" -> "Cupón QR"
            this._patchCouponButton();
        }

        _patchCouponButton() {
            const root = this.el;
            if (!root) return;

            // Localiza el botón nativo por icono o aria-label (depende del idioma/tema)
            const nativeBtn =
                  root.querySelector('.control-buttons .control-button i.fa-comment')?.closest('.control-button') ||
                  root.querySelector('.control-buttons .control-button[aria-label="Customer Note"]') ||
                  root.querySelector('.control-buttons .control-button[aria-label="Nota de cliente"]');

            if (!nativeBtn || nativeBtn.classList.contains('g7-coupon-patched')) return;

            // Clona para quitar listeners OWL y reemplaza
            const clone = nativeBtn.cloneNode(true);

            // Cambia icono y etiqueta
            const icon = clone.querySelector('i');
            if (icon) icon.className = 'fa fa-qrcode';
            const label = clone.querySelector('.label') || clone.querySelector('span');
            if (label) label.textContent = 'Cupón QR';

            clone.setAttribute('aria-label', 'Cupón QR');
            clone.classList.add('g7-coupon-patched');

            // Reemplaza el botón original por el clonado (sin listeners previos)
            nativeBtn.replaceWith(clone);

            // Nuestro click -> abre popup, valida y agrega línea
            clone.addEventListener('click', () => this._onClickCoupon());
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

            // 1) Validación en backend
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

            // 2) Producto y precio del cupón
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

            // 3) Marcar cupón como usado
            try {
                await this.rpc({
                    model: 'liquidation.coupon',
                    method: 'pos_redeem_coupon',
                    args: [code, order.uid, line.id],
                });
            } catch (e) {
                this.showPopup('ErrorPopup', {
                    title: this.env._t('Cupón'),
                    body: this.env._t('Se agregó la línea, pero no se logró marcar el cupón como usado.'),
                });
            }
        }
    };
    Registries.Component.extend(ProductScreen, G7CouponPatch);
});
