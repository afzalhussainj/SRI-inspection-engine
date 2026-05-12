Inspection Engine — Operating Rules


(Authoritative Contractor Reference)

**Note**: This file captures the client-provided Operating Rules text. Implementation-level details and clarified behaviors are documented in the other `docs/` files (especially `AGGREGATION_MODEL.md` and `ADMIN_PUBLISH_FLOW.md`).




1. Purpose


Build a reusable, configuration-driven inspection engine.
All inspection behavior must be defined by configuration, not hardcoded logic.

The engine must support:

•	Single-submission inspections (NRB)
•	Multi-submission aggregated inspections (QuietRisk)


Using the same engine, same rules, same PDF system.




2. Communication Rules


•	Upwork: scope, milestones, approvals, payment decisions
•	GitHub: code, architecture docs, technical discussion, issues, PRs
•	Async only — no calls or Zoom





3. Repository Rules


•	Repo owner: No Regret Systems
•	Primary branch: main
•	All work via pull requests
•	No force-pushes to main
•	PRs must reference milestone and deliverable





4. Documentation Requirements


All documentation must live in /docs or README.md and remain current.

Required docs:

1.	Architecture Overview
System components, responsibilities, data flow
2.	Config Specification
Schemas, examples, versioning rules
3.	Rules Engine Definition
Deterministic evaluation logic, constraints
4.	Admin Publish Flow
Draft → publish → immutable versioning
5.	Aggregation Model (QuietRisk)
How multiple submissions are grouped and summarized





5. Core Engine Rules (Locked)


•	Engine code is domain-agnostic
•	No audience assumptions (consumer, HR, medical, etc.)
•	No inspection-specific language in logic layer
•	All inspection meaning comes from configuration
•	No AI inference or probabilistic scoring
•	Deterministic outputs only





6. Inspection Types (Supported by Same Engine)



A. Single-Submission Inspection (NRB)


•	One user
•	One submission
•	One PDF
•	Session ends
•	No account, no persistence beyond delivery window



B. Aggregated Multi-Submission Inspection (QuietRisk — MVP)


•	Multiple individual submissions
•	Tied to a single:

o	organization_id
o	inspection_instance_id
•	
•	No employee identity stored
•	No individual PDFs delivered to HR


Aggregation is admin-triggered in the current implementation (manual action from admin).
`closes_at` and `submission_threshold` remain operational metadata for admin workflows.




7. Aggregation Rules (QuietRisk — MVP Only)


For aggregated inspections, the engine must compute:

•	Counts by section
•	Counts by classification (Cleared / Watch / Elevated)
•	Counts by indicator tags
•	Top repeated risk patterns


Output:

•	One employer-level executive PDF
•	No dashboards
•	No logins
•	No drilldowns
•	No trend-over-time analytics





8. Output Rules


•	Same PDF generation system for all inspections
•	Fixed layout template
•	Dynamic content limited to:

o	Section name
o	Classification
o	Selected output language
o	Counts (for aggregated inspections)
•	
•	PDFs must be:

o	Reproducible
o	Non-editable
o	Email-safe
•	





9. Explicit Non-Goals


The following are intentionally excluded:

•	Dashboards
•	User or employee accounts
•	Individual drilldowns
•	Analytics beyond aggregation math
•	AI insights
•	Graphs beyond simple tables in PDF
•	Trend tracking across time





10. Milestones & Definition of Done



Milestone 1 — Architecture & Core Setup


Done when:

•	Repo initialized
•	Architecture documented
•	Data models defined
•	Config + versioning model implemented
•	Sample inspection config included



Milestone 2 — Engine + Rules


Done when:

•	Engine runs entirely from config
•	Deterministic outputs
•	Versioning + immutability enforced
•	Sample inspection fully functional



Milestone 3 — Output / PDF Layer


Done when:

•	PDF generation wired
•	Outputs reproducible from pinned versions
•	Aggregated PDF supported (QuietRisk)



Milestone 4 — Hardening & Handoff


Done when:

•	Bug fixes complete
•	Validation checks implemented
•	Written handoff documentation delivered
•	Post-delivery support window begins





11. Change Control


•	Any scope change must be:

o	Documented
o	Approved in writing on Upwork
o	Scheduled via a new milestone
•	





12. Ownership


•	All code, configs, docs, and artifacts are client IP
•	No portfolio or public reference without written permission
<img width="468" height="637" alt="image" src="https://github.com/user-attachments/assets/ae4c4ef4-2c8f-418d-a5a2-00cf8f48b73b" />
