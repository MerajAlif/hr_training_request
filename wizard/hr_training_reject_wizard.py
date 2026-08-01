# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class HrTrainingRejectWizard(models.TransientModel):
    _name = 'hr.training.reject.wizard'
    _description = 'Training Request Rejection Wizard'

    training_request_id = fields.Many2one(
        'hr.training.request',
        string='Training Request',
        required=True,
        readonly=True,
    )
    rejection_reason = fields.Text(
        string='Rejection Reason',
        required=True,
    )

    @api.constrains('rejection_reason')
    def _check_rejection_reason(self):
        for rec in self:
            if not rec.rejection_reason or not rec.rejection_reason.strip():
                raise ValidationError(_("Rejection reason cannot be empty."))


    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        active_id = self.env.context.get('active_id')
        if active_id and 'training_request_id' in fields_list:
            res['training_request_id'] = active_id
        return res

    def action_confirm_reject(self):
        self.ensure_one()
        request = self.training_request_id
        if not request:
            raise UserError(_("No training request found."))

        # Determine who is rejecting based on current state
        if request.state == 'submitted':
            request._check_manager_approver(_("reject"))
        elif request.state == 'manager_approved':
            request._check_hr_approver(_("reject"))
        else:
            raise UserError(_("This request cannot be rejected in its current state."))

        # Post the rejection reason to chatter
        request.message_post(
            body=_("Request rejected. Reason: %s") % self.rejection_reason,
            message_type='comment',
            subtype_xmlid='mail.mt_note',
        )

        # Set state to rejected
        request._set_state('rejected')

        return {'type': 'ir.actions.act_window_close'}
