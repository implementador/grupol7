odoo.define('bi_pos_multi_branch.pos_extended', function (require) {
    "use strict";

    const { PosGlobalState, Order, Orderline, Payment } = require('point_of_sale.models');
    const Registries = require('point_of_sale.Registries');


    const PosHomePosGlobalState = (PosGlobalState) => class PosHomePosGlobalState extends PosGlobalState {
        //@override
        async _processData(loadedData) {
            await super._processData(...arguments);
            this.pos_branch_data = loadedData['res.branch'];
        }
    }
    Registries.Model.extend(PosGlobalState, PosHomePosGlobalState);

    const PosOrderLine = (Order) => class PosOrderLine extends Order {
        constructor(obj, options) {
            super(...arguments);
            this.branch_id = this.branch_id || "";
        }

        set_branch(branch_id) {
            this.branch_id = branch_id;
        }

        get_branch() {
            return this.branch_id;
        }

        init_from_JSON(json) {
            super.init_from_JSON(...arguments);
            this.branch_id = json.branch_id || "";
        }

        export_as_JSON() {
            const json = super.export_as_JSON(...arguments);
            json.branch_id = this.get_branch() || "";
            return json;
        }

        export_for_printing() {
            const json = super.export_for_printing(...arguments);
            json.branch_id = this.get_branch() || "";
            return json;
        }

    }

    Registries.Model.extend(Order, PosOrderLine);
});

