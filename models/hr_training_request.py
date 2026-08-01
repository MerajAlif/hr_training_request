# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError


class HrTrainingRequest(models.Model):
    _name = 'hr.training.request'
    _description = 'HR Training Request'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc, id desc'

    _STATE_WRITE_CONTEXT_KEY = 'hr_training_request_state_transition'
    _DRAFT_ONLY_FIELDS = {
        'employee_id',
        'course_name',
        'training_provider',
        'start_date',
        'end_date',
        'company_id',
        'cost',
        'justification',
    }
    _DASHBOARD_STATES = (
        'draft',
        'submitted',
        'manager_approved',
        'hr_approved',
        'rejected',
        'cancelled',
    )

    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee',
        required=True,
        default=lambda self: self.env.user.employee_id,
        tracking=True,
    )
    manager_id = fields.Many2one(
        'hr.employee',
        string='Manager',
        related='employee_id.parent_id',
        store=True,
        readonly=True,
        tracking=True,
    )
    course_name = fields.Char(
        string='Course Name',
        required=True,
        tracking=True,
    )
    training_provider = fields.Char(
        string='Training Provider',
        tracking=True,
    )
    start_date = fields.Date(
        string='Start Date',
        tracking=True,
    )
    end_date = fields.Date(
        string='End Date',
        tracking=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        required=True,
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        related='company_id.currency_id',
        readonly=True,
    )
    cost = fields.Monetary(
        string='Cost',
        currency_field='currency_id',
        tracking=True,
    )
    justification = fields.Text(
        string='Justification',
    )
    hr_notes = fields.Text(
        string='Internal HR Notes',
        groups='hr_training_request.group_training_hr_approver',
    )
    state = fields.Selection(
        [
            ('draft', 'Draft'),
            ('submitted', 'Submitted'),
            ('manager_approved', 'Manager Approved'),
            ('hr_approved', 'HR Approved'),
            ('rejected', 'Rejected'),
            ('cancelled', 'Cancelled'),
        ],
        string='State',
        default='draft',
        required=True,
        tracking=True,
    )
    can_submit = fields.Boolean(compute='_compute_workflow_permissions')
    can_cancel = fields.Boolean(compute='_compute_workflow_permissions')
    can_manager_review = fields.Boolean(compute='_compute_workflow_permissions')
    can_hr_review = fields.Boolean(compute='_compute_workflow_permissions')

    # -------------------------------------------------------------------------
    # CRUD GUARDS
    # -------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.user.has_group('hr_training_request.group_training_hr_approver'):
            for vals in vals_list:
                if vals.get('hr_notes'):
                    raise UserError(_("Only HR approvers can set HR notes."))
        for vals in vals_list:
            if vals.get('state') and vals['state'] != 'draft':
                raise UserError(_("Training requests must be created in draft state."))
            self._check_can_request_for_employee_vals(vals)
        return super().create(vals_list)

    def write(self, vals):
        if 'state' in vals and not self.env.context.get(self._STATE_WRITE_CONTEXT_KEY):
            raise UserError(_("Use the workflow buttons to change the request state."))
        if 'hr_notes' in vals and not self.env.user.has_group(
            'hr_training_request.group_training_hr_approver'
        ):
            raise UserError(_("Only HR approvers can update HR notes."))
        draft_only_updates = self._DRAFT_ONLY_FIELDS.intersection(vals)
        if draft_only_updates:
            locked = self.filtered(lambda rec: rec.state != 'draft')
            if locked:
                raise UserError(_("Request details can only be changed while the request is in draft."))
        if 'employee_id' in vals:
            self._check_can_request_for_employee_vals(vals)
        return super().write(vals)

    # -------------------------------------------------------------------------
    # CONSTRAINTS
    # -------------------------------------------------------------------------
    @api.constrains('start_date', 'end_date')
    def _check_dates(self):
        for rec in self:
            if rec.start_date and rec.end_date and rec.end_date <= rec.start_date:
                raise ValidationError(_("End date must be after start date."))

    @api.constrains('cost')
    def _check_cost(self):
        for rec in self:
            if rec.cost < 0:
                raise ValidationError(_("Cost cannot be negative."))

    # -------------------------------------------------------------------------
    # STATE TRANSITION METHODS
    # -------------------------------------------------------------------------
    def _is_owner_user(self):
        self.ensure_one()
        return self.employee_id.user_id == self.env.user

    @api.model
    def _can_request_for_employee(self, employee):
        if self.env.is_superuser():
            return True
        if not employee:
            return False
        user = self.env.user
        if employee.user_id == user:
            return True
        if user.has_group('hr_training_request.group_training_hr_approver'):
            return not employee.company_id or employee.company_id in user.company_ids
        if user.has_group('hr_training_request.group_training_manager_approver'):
            return bool(user.employee_id and employee.parent_id == user.employee_id)
        return False

    @api.model
    def _check_can_request_for_employee_vals(self, vals):
        employee_id = vals.get('employee_id') or self.env.user.employee_id.id
        employee = self.env['hr.employee'].browse(employee_id).exists()
        if not self._can_request_for_employee(employee):
            raise UserError(_("You can only create requests for yourself or employees you are allowed to support."))

    def _is_manager_reviewer(self):
        self.ensure_one()
        is_direct_manager = (
            self.env.user.employee_id
            and self.employee_id.parent_id
            and self.env.user.employee_id == self.employee_id.parent_id
        )
        is_manager_group = self.env.user.has_group(
            'hr_training_request.group_training_manager_approver'
        )
        return bool(is_direct_manager or is_manager_group)

    def _is_hr_reviewer(self):
        return self.env.user.has_group('hr_training_request.group_training_hr_approver')

    @api.depends('state', 'employee_id.user_id', 'employee_id.parent_id')
    @api.depends_context('uid')
    def _compute_workflow_permissions(self):
        for rec in self:
            is_owner = rec._is_owner_user()
            rec.can_submit = rec.state == 'draft' and rec._can_request_for_employee(rec.employee_id)
            rec.can_cancel = rec.state in ('draft', 'submitted') and is_owner
            rec.can_manager_review = rec.state == 'submitted' and rec._is_manager_reviewer()
            rec.can_hr_review = rec.state == 'manager_approved' and rec._is_hr_reviewer()

    def _check_is_owner(self):
        self.ensure_one()
        if not self._is_owner_user():
            raise UserError(_("Only the request owner can perform this action."))

    def _check_can_submit(self):
        self.ensure_one()
        if not self._can_request_for_employee(self.employee_id):
            raise UserError(_("You are not authorized to submit this request."))

    def _check_manager_approver(self, action):
        self.ensure_one()
        if not self._is_manager_reviewer():
            raise UserError(_("You are not authorized to %s this request.") % action)

    def _check_hr_approver(self, action):
        self.ensure_one()
        if not self._is_hr_reviewer():
            raise UserError(_("You are not authorized to %s this request.") % action)

    def _set_state(self, state):
        self.with_context(**{self._STATE_WRITE_CONTEXT_KEY: True}).write({'state': state})

    @api.model
    def retrieve_dashboard_data(self):
        request_model = self.env['hr.training.request']
        user = self.env.user
        user_employee = user.employee_id
        is_hr_approver = user.has_group('hr_training_request.group_training_hr_approver')
        is_manager_approver = user.has_group('hr_training_request.group_training_manager_approver')

        state_counts = {
            state: request_model.search_count([('state', '=', state)])
            for state in self._DASHBOARD_STATES
        }
        visible_requests = request_model.search([])
        total_cost = sum(visible_requests.mapped('cost'))

        my_domain = [('employee_id.user_id', '=', user.id)]
        team_domain = [('manager_id.user_id', '=', user.id)]
        manager_queue_domain = [('state', '=', 'submitted'), ('manager_id.user_id', '=', user.id)]
        hr_queue_domain = [('state', '=', 'manager_approved')]
        action_domain = hr_queue_domain if is_hr_approver else manager_queue_domain if is_manager_approver else my_domain

        recent_requests = request_model.search_read(
            [],
            ['employee_id', 'course_name', 'start_date', 'end_date', 'cost', 'currency_id', 'state'],
            limit=6,
            order='create_date desc, id desc',
        )
        action_requests = request_model.search_read(
            action_domain,
            ['employee_id', 'course_name', 'start_date', 'end_date', 'cost', 'currency_id', 'state'],
            limit=5,
            order='create_date desc, id desc',
        )

        return {
            'roles': {
                'is_requester': user.has_group('hr_training_request.group_training_requester'),
                'is_manager_approver': is_manager_approver,
                'is_hr_approver': is_hr_approver,
            },
            'current_employee': {
                'id': user_employee.id,
                'name': user_employee.name,
            } if user_employee else False,
            'state_counts': state_counts,
            'visible_total': request_model.search_count([]),
            'visible_total_cost': total_cost,
            'my_counts': {
                'draft': request_model.search_count(my_domain + [('state', '=', 'draft')]),
                'submitted': request_model.search_count(my_domain + [('state', '=', 'submitted')]),
                'approved': request_model.search_count(my_domain + [('state', '=', 'hr_approved')]),
                'closed': request_model.search_count(my_domain + [('state', 'in', ('rejected', 'cancelled'))]),
            },
            'queue_counts': {
                'manager': request_model.search_count(manager_queue_domain),
                'hr': request_model.search_count(hr_queue_domain),
            },
            'domains': {
                'all': [],
                'my_requests': my_domain,
                'my_draft': my_domain + [('state', '=', 'draft')],
                'my_submitted': my_domain + [('state', '=', 'submitted')],
                'my_approved': my_domain + [('state', '=', 'hr_approved')],
                'my_closed': my_domain + [('state', 'in', ('rejected', 'cancelled'))],
                'team_requests': team_domain,
                'manager_queue': manager_queue_domain,
                'hr_queue': hr_queue_domain,
                'approved': [('state', '=', 'hr_approved')],
                'closed': [('state', 'in', ('rejected', 'cancelled'))],
            },
            'recent_requests': recent_requests,
            'action_requests': action_requests,
        }

    def action_submit(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_("Only draft requests can be submitted."))
            rec._check_can_submit()
            rec._set_state('submitted')

    def action_cancel(self):
        for rec in self:
            if rec.state not in ('draft', 'submitted'):
                raise UserError(_("Only draft or submitted requests can be cancelled."))
            rec._check_is_owner()
            rec._set_state('cancelled')

    def action_manager_approve(self):
        for rec in self:
            if rec.state != 'submitted':
                raise UserError(_("Only submitted requests can be manager-approved."))
            rec._check_manager_approver(_("approve"))
            rec._set_state('manager_approved')

    def action_manager_reject(self):
        self.ensure_one()
        if self.state != 'submitted':
            raise UserError(_("Only submitted requests can be rejected by manager."))
        self._check_manager_approver(_("reject"))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Reject Training Request'),
            'res_model': 'hr.training.reject.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'active_id': self.id, 'active_model': self._name},
        }

    def action_hr_approve(self):
        for rec in self:
            if rec.state != 'manager_approved':
                raise UserError(_("Only manager-approved requests can be HR-approved."))
            rec._check_hr_approver(_("approve"))
            rec._set_state('hr_approved')

    def action_hr_reject(self):
        self.ensure_one()
        if self.state != 'manager_approved':
            raise UserError(_("Only manager-approved requests can be rejected by HR."))
        self._check_hr_approver(_("reject"))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Reject Training Request'),
            'res_model': 'hr.training.reject.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'active_id': self.id, 'active_model': self._name},
        }
