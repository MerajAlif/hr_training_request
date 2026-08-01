# -*- coding: utf-8 -*-
from odoo import models, fields


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    training_request_count = fields.Integer(
        string='Training Requests',
        compute='_compute_training_request_count',
    )

    def _compute_training_request_count(self):
        for emp in self:
            # Note: No sudo() used intentionally so that count strictly respects the viewing user's record rules
            emp.training_request_count = self.env['hr.training.request'].search_count(
                [('employee_id', '=', emp.id)]
            )

    def action_open_training_requests(self):
        self.ensure_one()
        action = self.env['ir.actions.actions']._for_xml_id(
            'hr_training_request.action_hr_training_request_all'
        )
        action['domain'] = [('employee_id', '=', self.id)]
        action['context'] = {
            'default_employee_id': self.id,
            'search_default_employee_id': self.id,
        }
        return action
