odoo.define('grupol7_liquidacion_qr.qr_button_ux', function (require) {
    "use strict";

    const Registries = require('point_of_sale.Registries');
    const ProductScreen = require('point_of_sale.ProductScreen');

    function log(){ try{ console.warn('[G7 Coupon]:', ...arguments); } catch(_){} }

    const G7CouponPatch = (ProductScreen) => class extends ProductScreen {
        mounted() {
            super.mounted();
            log('mounted ProductScreen');
            // Intenta de inmediato y también observa cambios de DOM
            this._ensureCouponButton();
            this._attachObserver();
        }

        willUnmount() {
            super.willUnmount();
            if (this._g7Observer) {
                this._g7Observer.disconnect();
                this._g7Observer = null;
            }
        }

        _attachObserver() {
            const root = this.el;
            if (!root || this._g7Observer) return;
            this._g7Observer = new MutationObserver(() => this._ensureCouponButton());
            this._g7Observer.observe(root, { childList: true, subtree: true });
            log('MutationObserver attached');
        }

        _ensureCouponButton() {
            const root = this.el;
            if (!root) return;

            // ¿Ya está parcheado?
            if (root.querySelector('.control-buttons .control-button.g7-coupon')) return;

            // 1) Intentar renombrar botón nativo (nota de cliente)
            const candidates = Array.from(root.querySelectorAll('.control-buttons .control-button'));
            let found = null;
            for (const btn of candidates) {
                const lbl = (btn.querySelector('.label,span')?.textContent || '').trim().toLowerCase();
                const aria = (btn.getAttribute('aria-label') || '').trim().toLowerCase();
                const hasCommentIcon = !!btn.querySelector('i.fa-comment, i.fa-comment-o');
                if (['nota de cliente','customer note'].includes(lbl) || ['nota de cliente','customer note'].includes(aria) || hasCommentIcon) {
                    found = btn;
                    break;
                }
            }

            if (found) {
                // Clona para quitar listeners previos
                const clone = found.cloneNode(true);
                const icon = clone.querySelector('i');
                if (icon) icon.className = 'fa fa-qrcode';
                const label = clone.querySelector('.label') || clone.querySelector('span') || document.createElement('span');
                label.textContent = 'Cupón QR';
                label.classList.add('label');
                if (!clone.querySelector('.label')) clone.appendChild(label);

                clone.setAttribute('aria-label', 'Cupón QR');
                clone.classList.add('g7-coupon');

                // Reemplazo
                found.replaceWith(clone);

                // Click → flujo del cupón
                clone.addEventListener('click', () => this._onClickCoupon());
                log('Renombrado botón nativo a "Cupón QR"');
                return;
            }

            // 2) Fallback: crear nuestro botón “Cupón QR” y anexarlo
            const bar = root.querySelector('.control-buttons');
            if (bar && !bar.querySelector('.g7-coupon')) {
                const btn = document.createElement('div');
                btn.className = 'control-button g7-coupon';
                btn.setAttribute('aria-label','Cupón QR');

                const i = document.createElement('i'); i.className = 'fa fa-qrcode';
                const s = document.createElement('span'); s.className = 'label'; s.textContent = 'Cupón QR';
                btn.appendChild(i); btn.appendChild(s);

                btn.addEventListener('click', () => this._onClickCoupon());
                bar.appendChild(btn);
                log('Botón “Cupón QR” creado (fallback)');
            }
        }

        async _onClickCoupon() {
            log('Click Cupón QR');
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

            let res;
            try {
                res = await this.rpc({
                    model: 'liquidation.coupon',
                    method: 'pos_validate_coupon',
                    args: [code, this.env.pos.config.id],
                });
                log('Validación OK', res);
            } catch (e) {
                log('Validación fallo', e);
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
                log('Redención OK');
            } catch (e) {
                log('Redención fallo', e);
                this.showPopup('ErrorPopup', {
                    title: this.env._t('Cupón'),
                    body: this.env._t('Se agregó la línea, pero no se logró marcar el cupón como usado.'),
                });
            }
        }
    };

    Registries.Component.extend(ProductScreen, G7CouponPatch);
    log('Módulo cargado');
});
