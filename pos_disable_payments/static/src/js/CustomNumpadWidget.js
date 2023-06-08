odoo.define('point_of_sale.CustomNumpadWidget', function(require) {
    'use strict';

    const PosComponent = require('point_of_sale.PosComponent');
    const Registries = require('point_of_sale.Registries');

    /**
     * @prop {'quantity' | 'price' | 'discount'} activeMode
     * @prop {Array<'quantity' | 'price' | 'discount'>} disabledModes
     * @prop {boolean} disableSign
     * @event set-numpad-mode - triggered when mode button is clicked
     * @event numpad-click-input - triggered when numpad button is clicked
     */
    class CustomNumpadWidget extends PosComponent {
        get hasPriceControlRights() {
            return (
                this.env.pos.cashierHasPriceControlRights() &&
                !this.props.disabledModes.includes('price')
            );
        }
        get hasManualDiscount() {
            return this.env.pos.config.manual_discount && !this.props.disabledModes.includes('discount');
        }
        changeMode(mode) {
            if (!this.hasPriceControlRights && mode === 'price') {
                return;
            }
            if (!this.hasManualDiscount && mode === 'discount') {
                return;
            }
            this.trigger('set-numpad-mode', { mode });
        }
        sendInput(key) {
            let cashier = this.env.pos.get_cashier();
            if (this.props.activeMode == 'quantity') {
                if ('is_allow_qty' in cashier) {
                    if (cashier.is_allow_qty) {
                        this.trigger('numpad-click-input', { key });
                    } else {
                        alert("Sorry,You have no access to change quantity");
                    }
                } else {
                    this.trigger('numpad-click-input', { key });
                }
            } else if (this.props.activeMode == 'price') {
                if ('is_edit_price' in cashier) {
                    if (cashier.is_edit_price) {
                        this.trigger('numpad-click-input', { key });
                    } else {
                        alert("Sorry,You have no access to change Price");
                    }
                } else {
                    this.trigger('numpad-click-input', { key });
                }
            } else if (this.props.activeMode == 'discount') {
                if ('is_allow_discount' in cashier) {
                    if (cashier.is_allow_discount) {
                        this.trigger('numpad-click-input', { key });
                    } else {
                        alert("Sorry,You have no access to change discount");
                    }
                } else {
                    this.trigger('numpad-click-input', { key });
                }
            }
        }
        get decimalSeparator() {
            return this.env._t.database.parameters.decimal_point;
        }
    }
    CustomNumpadWidget.template = 'CustomNumpadWidget';
    CustomNumpadWidget.defaultProps = {
        disabledModes: [],
        disableSign: false,
    }

    Registries.Component.add(CustomNumpadWidget);

    return CustomNumpadWidget;
});