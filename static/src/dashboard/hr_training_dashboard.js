/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const STATE_LABELS = {
    draft: "Draft",
    submitted: "Submitted",
    manager_approved: "Manager Approved",
    hr_approved: "HR Approved",
    rejected: "Rejected",
    cancelled: "Cancelled",
};

const STATE_CLASSES = {
    draft: "muted",
    submitted: "info",
    manager_approved: "warning",
    hr_approved: "success",
    rejected: "danger",
    cancelled: "muted",
};

export class HrTrainingDashboard extends Component {
    static template = "hr_training_request.Dashboard";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({
            loading: true,
            data: {},
        });

        onWillStart(() => this.loadDashboard());
    }

    async loadDashboard() {
        this.state.loading = true;
        this.state.data = await this.orm.call("hr.training.request", "retrieve_dashboard_data", []);
        this.state.loading = false;
    }

    get roleTitle() {
        const roles = this.state.data.roles || {};
        if (roles.is_hr_approver) {
            return "HR training approval overview";
        }
        if (roles.is_manager_approver) {
            return "Team training approval overview";
        }
        return "My training requests";
    }

    get kpis() {
        const data = this.state.data;
        const roles = data.roles || {};
        const my = data.my_counts || {};
        const queues = data.queue_counts || {};
        const kpis = [
            { label: "My Draft", value: my.draft || 0, domainKey: "my_draft", tone: "muted" },
            { label: "My Submitted", value: my.submitted || 0, domainKey: "my_submitted", tone: "info" },
            { label: "My Approved", value: my.approved || 0, domainKey: "my_approved", tone: "success" },
            { label: "Closed", value: my.closed || 0, domainKey: "my_closed", tone: "danger" },
        ];
        if (roles.is_manager_approver) {
            kpis.push({
                label: "Manager Queue",
                value: queues.manager || 0,
                domainKey: "manager_queue",
                tone: "info",
            });
        }
        if (roles.is_hr_approver) {
            kpis.push({
                label: "HR Queue",
                value: queues.hr || 0,
                domainKey: "hr_queue",
                tone: "warning",
            });
            kpis.push({
                label: "Visible Cost",
                value: this.formatAmount(data.visible_total_cost || 0),
                domainKey: "all",
                tone: "success",
            });
        }
        return kpis;
    }

    get stateRows() {
        const counts = this.state.data.state_counts || {};
        return Object.keys(STATE_LABELS).map((key) => ({
            key,
            label: STATE_LABELS[key],
            count: counts[key] || 0,
            className: STATE_CLASSES[key],
        }));
    }

    get actionTitle() {
        const roles = this.state.data.roles || {};
        if (roles.is_hr_approver) {
            return "Pending HR approval";
        }
        if (roles.is_manager_approver) {
            return "Pending manager review";
        }
        return "My latest requests";
    }

    formatAmount(value) {
        return Number(value || 0).toLocaleString(undefined, {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        });
    }

    formatDate(value) {
        return value || "-";
    }

    stateLabel(value) {
        return STATE_LABELS[value] || value;
    }

    stateClass(value) {
        return STATE_CLASSES[value] || "muted";
    }

    openDomainFromEvent(ev) {
        const domainKey = ev.currentTarget.dataset.domainKey;
        this.openDomain(domainKey);
    }

    openDomain(domainKey) {
        const domain = (this.state.data.domains || {})[domainKey] || [];
        this.action.doAction({
            type: "ir.actions.act_window",
            name: "Training Requests",
            res_model: "hr.training.request",
            views: [[false, "list"], [false, "form"]],
            view_mode: "list,form",
            domain,
        });
    }

    openRecord(ev) {
        const resId = Number(ev.currentTarget.dataset.resId);
        if (!resId) {
            return;
        }
        this.action.doAction({
            type: "ir.actions.act_window",
            name: "Training Request",
            res_model: "hr.training.request",
            views: [[false, "form"]],
            view_mode: "form",
            res_id: resId,
        });
    }

    createRequest() {
        const employee = this.state.data.current_employee;
        this.action.doAction({
            type: "ir.actions.act_window",
            name: "New Training Request",
            res_model: "hr.training.request",
            views: [[false, "form"]],
            view_mode: "form",
            context: employee ? { default_employee_id: employee.id } : {},
        });
    }
}

registry.category("actions").add("hr_training_request.dashboard", HrTrainingDashboard);
