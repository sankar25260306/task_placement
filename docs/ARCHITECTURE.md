# InternMind AI Architecture

## Flow
Admin project setup -> requirement IDs -> intern CSV import -> tasks and dependencies -> assignment -> task email -> submission version -> evidence QA -> mentor decision -> approval or correction cycle -> confirmed reschedule -> correction email -> resubmission -> review again.

## Agents to implement in later phases
- Requirement DNA: map REQ IDs to tasks, evidence and tests.
- Allocation Agent: suggest assignments based on skills, workload and dependency order.
- Evidence QA Agent: check evidence completeness and requirement mapping.
- Acceptance Test Planner: propose edge, invalid and boundary tests.
- Dependency/Integration Agent: verify task prerequisites and API/schema compatibility.
- Change Impact Agent: find affected tasks/tests when requirements change.
- Risk Agent: predict delay risk from due dates and blocked work.
- Originality Signal Agent: flag suspiciously similar submissions for human review only.
- Review Triage Agent: prioritize critical blockers and failures.
- Evidence Pack Agent: compile release readiness, coverage, tests, limitations and ownership.

## Production architecture
React + TypeScript frontend; FastAPI/Pydantic backend; PostgreSQL; durable queue/outbox worker; Google Calendar OAuth; private artifact storage; isolated disposable test runners; structured LLM adapter; audit and monitoring.

## Security
Never execute intern code in the API process. Use a disposable sandbox with CPU/memory/time limits and network disabled by default. Treat repository content as untrusted input. Use HTTPS, secret management, RBAC, password activation/reset, backups, retention policy and security/load testing.

## Not yet implemented in this MVP
Real LLM review, actual code execution, automatic Google Meet event creation, recurring background reminders, React dashboard, account activation/reset, durable retry queue, PostgreSQL migration scripts, and automatic next-task assignment. The mentor records the final decision. Do not describe these features as working until built and tested.
