# -*- coding: utf-8 -*-
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import TransactionCase, tagged, new_test_user


@tagged('post_install', '-at_install')
class TestHrTrainingRequest(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Request = cls.env['hr.training.request']
        cls.Employee = cls.env['hr.employee']
        cls.RejectWizard = cls.env['hr.training.reject.wizard']

        # Setup users per requirement 1:
        # employee_a (requester), manager_a (manager_approver & parent of employee_a), hr_user (hr_approver)
        cls.employee_a_user = new_test_user(
            cls.env,
            login='employee_a',
            groups='base.group_user,hr_training_request.group_training_requester',
        )
        cls.manager_a_user = new_test_user(
            cls.env,
            login='manager_a',
            groups='base.group_user,hr_training_request.group_training_manager_approver',
        )
        cls.hr_user = new_test_user(
            cls.env,
            login='hr_user',
            groups='base.group_user,hr_training_request.group_training_hr_approver',
        )

        # Extra employee_b + manager_b (unrelated team for cross-team negative tests)
        cls.employee_b_user = new_test_user(
            cls.env,
            login='employee_b',
            groups='base.group_user,hr_training_request.group_training_requester',
        )
        cls.manager_b_user = new_test_user(
            cls.env,
            login='manager_b',
            groups='base.group_user,hr_training_request.group_training_manager_approver',
        )

        # Separate user in manager_approver group who is NOT parent_id of employee_a
        cls.other_manager_user = new_test_user(
            cls.env,
            login='other_manager',
            groups='base.group_user,hr_training_request.group_training_manager_approver',
        )

        # Linked employees
        cls.manager_a_employee = cls.Employee.create({
            'name': 'Manager A',
            'user_id': cls.manager_a_user.id,
        })
        cls.employee_a = cls.Employee.create({
            'name': 'Employee A',
            'user_id': cls.employee_a_user.id,
            'parent_id': cls.manager_a_employee.id,
        })
        cls.hr_employee = cls.Employee.create({
            'name': 'HR User Employee',
            'user_id': cls.hr_user.id,
        })

        cls.manager_b_employee = cls.Employee.create({
            'name': 'Manager B',
            'user_id': cls.manager_b_user.id,
        })
        cls.employee_b = cls.Employee.create({
            'name': 'Employee B',
            'user_id': cls.employee_b_user.id,
            'parent_id': cls.manager_b_employee.id,
        })

        cls.other_manager_employee = cls.Employee.create({
            'name': 'Other Manager',
            'user_id': cls.other_manager_user.id,
        })

    def _create_request(self, employee=None, **extra_vals):
        emp = employee or self.employee_a
        vals = {
            'employee_id': emp.id,
            'course_name': 'Python Advanced',
            'training_provider': 'Tech Institute',
            'start_date': '2026-09-10',
            'end_date': '2026-09-15',
            'cost': 300.0,
            'justification': 'Upgrade technical capabilities.',
        }
        vals.update(extra_vals)
        user = emp.user_id or self.env.user
        return self.Request.with_user(user).create(vals)

    # -------------------------------------------------------------------------
    # A. STATE MACHINE — HAPPY PATH
    # -------------------------------------------------------------------------
    def test_01_full_approval_flow(self):
        req = self._create_request(self.employee_a)
        self.assertEqual(req.state, 'draft')

        req.with_user(self.employee_a_user).action_submit()
        self.assertEqual(req.state, 'submitted')

        req.with_user(self.manager_a_user).action_manager_approve()
        self.assertEqual(req.state, 'manager_approved')

        req.with_user(self.hr_user).action_hr_approve()
        self.assertEqual(req.state, 'hr_approved')

    def test_02_manager_reject_flow(self):
        req = self._create_request(self.employee_a)
        req.with_user(self.employee_a_user).action_submit()

        action = req.with_user(self.manager_a_user).action_manager_reject()
        wizard = self.RejectWizard.with_user(self.manager_a_user).with_context(
            **action['context']
        ).create({'rejection_reason': 'Budget exceeded for Q3.'})
        wizard.action_confirm_reject()

        self.assertEqual(req.state, 'rejected')
        messages = req.message_ids.filtered(lambda m: 'Budget exceeded for Q3' in (m.body or ''))
        self.assertTrue(messages, "Rejection reason must be logged to chatter")

    def test_03_hr_reject_flow(self):
        req = self._create_request(self.employee_a)
        req.with_user(self.employee_a_user).action_submit()
        req.with_user(self.manager_a_user).action_manager_approve()

        action = req.with_user(self.hr_user).action_hr_reject()
        wizard = self.RejectWizard.with_user(self.hr_user).with_context(
            **action['context']
        ).create({'rejection_reason': 'HR Policy violation.'})
        wizard.action_confirm_reject()

        self.assertEqual(req.state, 'rejected')

    def test_04_owner_cancel_from_draft(self):
        req = self._create_request(self.employee_a)
        req.with_user(self.employee_a_user).action_cancel()
        self.assertEqual(req.state, 'cancelled')

    def test_05_owner_cancel_from_submitted(self):
        req = self._create_request(self.employee_a)
        req.with_user(self.employee_a_user).action_submit()
        req.with_user(self.employee_a_user).action_cancel()
        self.assertEqual(req.state, 'cancelled')

    # -------------------------------------------------------------------------
    # B. STATE MACHINE — ILLEGAL TRANSITIONS
    # -------------------------------------------------------------------------
    def test_06_cannot_hr_approve_from_draft(self):
        req = self._create_request(self.employee_a)
        with self.assertRaises(UserError):
            req.with_user(self.hr_user).action_hr_approve()
        self.assertEqual(req.state, 'draft')

    def test_07_cannot_manager_approve_from_draft(self):
        req = self._create_request(self.employee_a)
        with self.assertRaises(UserError):
            req.with_user(self.manager_a_user).action_manager_approve()
        self.assertEqual(req.state, 'draft')

    def test_08_cannot_submit_twice(self):
        req = self._create_request(self.employee_a)
        req.with_user(self.employee_a_user).action_submit()
        with self.assertRaises(UserError):
            req.with_user(self.employee_a_user).action_submit()

    def test_09_cannot_cancel_from_manager_approved(self):
        req = self._create_request(self.employee_a)
        req.with_user(self.employee_a_user).action_submit()
        req.with_user(self.manager_a_user).action_manager_approve()
        with self.assertRaises(UserError):
            req.with_user(self.employee_a_user).action_cancel()

    def test_10_cannot_cancel_from_hr_approved(self):
        req = self._create_request(self.employee_a)
        req.with_user(self.employee_a_user).action_submit()
        req.with_user(self.manager_a_user).action_manager_approve()
        req.with_user(self.hr_user).action_hr_approve()
        with self.assertRaises(UserError):
            req.with_user(self.employee_a_user).action_cancel()

    def test_11_no_transition_out_of_rejected(self):
        req = self._create_request(self.employee_a)
        req.with_user(self.employee_a_user).action_submit()
        action = req.with_user(self.manager_a_user).action_manager_reject()
        self.RejectWizard.with_user(self.manager_a_user).with_context(
            **action['context']
        ).create({'rejection_reason': 'Rejected.'}).action_confirm_reject()
        self.assertEqual(req.state, 'rejected')

        with self.assertRaises(UserError):
            req.with_user(self.employee_a_user).action_submit()
        with self.assertRaises(UserError):
            req.with_user(self.manager_a_user).action_manager_approve()
        with self.assertRaises(UserError):
            req.with_user(self.hr_user).action_hr_approve()
        with self.assertRaises(UserError):
            req.with_user(self.employee_a_user).action_cancel()

    def test_12_no_transition_out_of_hr_approved(self):
        req = self._create_request(self.employee_a)
        req.with_user(self.employee_a_user).action_submit()
        req.with_user(self.manager_a_user).action_manager_approve()
        req.with_user(self.hr_user).action_hr_approve()
        self.assertEqual(req.state, 'hr_approved')

        with self.assertRaises(UserError):
            req.with_user(self.employee_a_user).action_submit()
        with self.assertRaises(UserError):
            req.with_user(self.manager_a_user).action_manager_approve()
        with self.assertRaises(UserError):
            req.with_user(self.hr_user).action_hr_approve()
        with self.assertRaises(UserError):
            req.with_user(self.employee_a_user).action_cancel()

    def test_13_no_transition_out_of_cancelled(self):
        req = self._create_request(self.employee_a)
        req.with_user(self.employee_a_user).action_cancel()
        self.assertEqual(req.state, 'cancelled')

        with self.assertRaises(UserError):
            req.with_user(self.employee_a_user).action_submit()
        with self.assertRaises(UserError):
            req.with_user(self.manager_a_user).action_manager_approve()
        with self.assertRaises(UserError):
            req.with_user(self.hr_user).action_hr_approve()

    # -------------------------------------------------------------------------
    # C. ROLE-GATED ACTIONS — AUTHORIZATION CHECKS
    # -------------------------------------------------------------------------
    def test_14_only_owner_can_submit(self):
        req = self._create_request(self.employee_a)
        with self.assertRaises(UserError):
            req.with_user(self.employee_b_user).action_submit()

    def test_15_only_owner_can_cancel(self):
        req = self._create_request(self.employee_a)
        with self.assertRaises(UserError):
            req.with_user(self.manager_a_user).action_cancel()

    def test_16_direct_manager_can_approve(self):
        req = self._create_request(self.employee_a)
        req.with_user(self.employee_a_user).action_submit()
        req.with_user(self.manager_a_user).action_manager_approve()
        self.assertEqual(req.state, 'manager_approved')

    def test_17_non_manager_group_user_cannot_approve(self):
        req = self._create_request(self.employee_a)
        req.with_user(self.employee_a_user).action_submit()
        # Non-manager group user (employee_b) cannot approve
        with self.assertRaises(UserError):
            req.with_user(self.employee_b_user).action_manager_approve()

    def test_18_manager_approver_group_member_can_approve_visible_request(self):
        req = self._create_request(self.employee_a)
        req.with_user(self.employee_a_user).action_submit()
        # Any user in group_training_manager_approver who has record access (or HR approver) can approve
        req.with_user(self.manager_a_user).action_manager_approve()
        self.assertEqual(req.state, 'manager_approved')

    def test_19_employee_cannot_approve_own_request(self):
        req = self._create_request(self.employee_a)
        req.with_user(self.employee_a_user).action_submit()
        with self.assertRaises(UserError):
            req.with_user(self.employee_a_user).action_manager_approve()

    def test_20_only_hr_group_can_hr_approve(self):
        req = self._create_request(self.employee_a)
        req.with_user(self.employee_a_user).action_submit()
        req.with_user(self.manager_a_user).action_manager_approve()
        with self.assertRaises(UserError):
            req.with_user(self.manager_a_user).action_hr_approve()

    def test_21_hr_user_can_hr_approve(self):
        req = self._create_request(self.employee_a)
        req.with_user(self.employee_a_user).action_submit()
        req.with_user(self.manager_a_user).action_manager_approve()
        req.with_user(self.hr_user).action_hr_approve()
        self.assertEqual(req.state, 'hr_approved')

    # -------------------------------------------------------------------------
    # D. RECORD RULES — ROW-LEVEL VISIBILITY
    # -------------------------------------------------------------------------
    def test_22_employee_sees_only_own_records(self):
        req_a = self._create_request(self.employee_a)
        req_b = self._create_request(self.employee_b)

        records_a = self.Request.with_user(self.employee_a_user).search([])
        self.assertIn(req_a, records_a)
        self.assertNotIn(req_b, records_a)

    def test_23_employee_cannot_read_others_record_by_id(self):
        req_b = self._create_request(self.employee_b)
        with self.assertRaises(AccessError):
            _ = req_b.with_user(self.employee_a_user).course_name

    def test_24_manager_sees_own_and_team_records(self):
        req_a = self._create_request(self.employee_a)
        req_b = self._create_request(self.employee_b)
        req_mgr_a = self._create_request(self.manager_a_employee)

        records_mgr_a = self.Request.with_user(self.manager_a_user).search([])
        self.assertIn(req_a, records_mgr_a)
        self.assertIn(req_mgr_a, records_mgr_a)
        self.assertNotIn(req_b, records_mgr_a)

    def test_25_hr_sees_all_company_records(self):
        req_a = self._create_request(self.employee_a)
        req_b = self._create_request(self.employee_b)

        records_hr = self.Request.with_user(self.hr_user).search([])
        self.assertIn(req_a, records_hr)
        self.assertIn(req_b, records_hr)

    # -------------------------------------------------------------------------
    # E. FIELD-LEVEL SECURITY — hr_notes
    # -------------------------------------------------------------------------
    def test_26_non_hr_cannot_read_hr_notes(self):

        req = self._create_request(self.employee_a)
        req.with_user(self.hr_user).write({'hr_notes': 'Secret HR Note'})

        with self.assertRaises(AccessError):
            req.with_user(self.employee_a_user).read(['hr_notes'])

    def test_27_non_hr_cannot_write_hr_notes(self):
        req = self._create_request(self.employee_a)
        with self.assertRaises(UserError):
            req.with_user(self.manager_a_user).write({'hr_notes': 'Attempt by Manager'})
        with self.assertRaises(UserError):
            req.with_user(self.employee_a_user).write({'hr_notes': 'Attempt by Employee'})

    def test_28_hr_can_read_write_hr_notes(self):
        req = self._create_request(self.employee_a)
        req.with_user(self.hr_user).write({'hr_notes': 'HR Private Note'})
        self.assertEqual(req.with_user(self.hr_user).hr_notes, 'HR Private Note')

    # -------------------------------------------------------------------------
    # F. VALIDATION CONSTRAINTS
    # -------------------------------------------------------------------------
    def test_29_end_date_before_start_date_raises(self):
        with self.assertRaises(ValidationError):
            self._create_request(self.employee_a, start_date='2026-09-15', end_date='2026-09-10')

    def test_30_end_date_equal_start_date_raises(self):
        with self.assertRaises(ValidationError):
            self._create_request(self.employee_a, start_date='2026-09-10', end_date='2026-09-10')

    def test_31_negative_cost_raises(self):
        with self.assertRaises(ValidationError):
            self._create_request(self.employee_a, cost=-50.0)

    def test_32_zero_cost_allowed(self):
        req = self._create_request(self.employee_a, cost=0.0)
        self.assertEqual(req.cost, 0.0)

    # -------------------------------------------------------------------------
    # G. hr.employee INHERITANCE
    # -------------------------------------------------------------------------
    def test_33_training_request_count_computed_correctly(self):
        self._create_request(self.employee_a, course_name='Course 1')
        self._create_request(self.employee_a, course_name='Course 2')

        emp_a = self.employee_a.with_user(self.employee_a_user)
        self.assertEqual(emp_a.training_request_count, 2)

    def test_34_smart_button_count_respects_access(self):
        self._create_request(self.employee_a, course_name='Employee A Request')
        action = self.employee_a.with_user(self.employee_b_user).action_open_training_requests()
        domain = action['domain']
        visible_requests = self.Request.with_user(self.employee_b_user).search(domain)
        self.assertEqual(len(visible_requests), 0, "Smart button domain search as employee_b must not leak employee_a's data")

    # -------------------------------------------------------------------------
    # H. MANAGER CHANGE EDGE CASE
    # -------------------------------------------------------------------------
    def test_35_manager_id_updates_when_parent_changes(self):
        req = self._create_request(self.employee_a)
        self.assertEqual(req.manager_id, self.manager_a_employee)

        # Update parent_id of employee_a to manager_b
        self.employee_a.write({'parent_id': self.manager_b_employee.id})
        self.assertEqual(req.manager_id, self.manager_b_employee, "manager_id must reflect updated parent_id")

    # -------------------------------------------------------------------------
    # I. REJECT WIZARD
    # -------------------------------------------------------------------------
    def test_36_reject_without_reason_blocked(self):
        req = self._create_request(self.employee_a)
        req.with_user(self.employee_a_user).action_submit()

        action = req.with_user(self.manager_a_user).action_manager_reject()
        with self.assertRaises(ValidationError):
            self.RejectWizard.with_user(self.manager_a_user).with_context(
                **action['context']
            ).create({'rejection_reason': ''}).action_confirm_reject()

    def test_37_reject_reason_logged_to_chatter(self):
        req = self._create_request(self.employee_a)
        req.with_user(self.employee_a_user).action_submit()

        action = req.with_user(self.manager_a_user).action_manager_reject()
        wizard = self.RejectWizard.with_user(self.manager_a_user).with_context(
            **action['context']
        ).create({'rejection_reason': 'Detailed rejection explanation.'})
        wizard.action_confirm_reject()

        messages = req.message_ids.filtered(lambda m: 'Detailed rejection explanation.' in (m.body or ''))
        self.assertTrue(messages)
