/** @odoo-module **/
import { patch } from "@web/core/utils/patch";
import { WebClient } from "@web/webclient/webclient";

patch(WebClient.prototype, {
    setup() {
        super.setup(...arguments);
        this.title.setParts({ zopenerp: "AulaMetrics" });
    },
});
