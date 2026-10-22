/** @odoo-module **/

import { Component, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { user } from "@web/core/user";

class ArchiplanSchedule extends Component {
    static template = "archiplan_connector.Schedule";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = { link: null, error: false };
        onWillStart(async () => {
            const companyId = this.env.services.company?.currentCompany?.id || user.activeCompany?.id;
            if (!companyId) {
                this.state.link = "";
                return;
            }
            try {
                const [company] = await this.orm.read("res.company", [companyId], ["archiplan_schedule_link"]);
                this.state.link = company?.archiplan_schedule_link || "";
            } catch (error) {
                console.error("Could not load the ArchiPlan schedule link", error);
                this.state.error = true;
            }
        });
    }

    openSettings() {
        this.action.doAction("base_setup.action_general_configuration");
    }
}

registry.category("actions").add("archiplan_connector.schedule", ArchiplanSchedule);
