# HR Training Request PRD

This module implements the `hr_training_request` workflow for Odoo 18 Community, plus product-grade catalog configuration and an access-aware dashboard.

## Objective

Employees request external training or certification. Requests move through a strict approval chain:

1. Draft to Submitted by the request owner.
2. Submitted to Manager Approved or Rejected by the direct manager or manager approver group.
3. Manager Approved to HR Approved or Rejected by the HR approver group.

## Non-Negotiables

- Security is enforced through ACLs, record rules, field groups, and Python guards.
- UI button visibility is convenience only; workflow methods validate permissions server-side.
- Direct writes to `state` are blocked.
- Request business fields are editable only in draft.
- HR notes are visible and writable only for HR approvers.
- Dashboard and catalog features must never bypass ACLs, record rules, or workflow guards.
- Provider/course configuration must preserve request snapshots for audit history.

## Acceptance Criteria

- Requesters see only their own requests.
- Manager approvers see their own requests and direct reports' requests.
- HR approvers see company-wide requests.
- Invalid date ranges and negative costs are rejected.
- The employee smart button opens requests for the selected employee while respecting record rules.
- Managers and HR can maintain Training Providers and Training Courses under Configuration.
- Requesters can select catalog providers/courses but cannot edit catalog master data.
- Selecting a course fills provider/course snapshots and default cost while keeping draft cost editable.
- Provider/course smart buttons open related requests through access-aware domains.
