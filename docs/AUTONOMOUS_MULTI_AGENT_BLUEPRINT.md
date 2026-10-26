# InternMind AI — Autonomous Multi-Agent Upgrade Blueprint

Client context: Thozhil (https://thozhil.co.in/)

## Product promise

One project can contain 100+ interns. Every intern receives an individualized task path, task ID, instructions, deadline, submission channel, review appointment and feedback. The system continuously processes each intern independently and advances them to the next eligible task after passing objective checks. It must not send real emails or book real meetings until the operator configures and tests the relevant integrations.

## Implemented in this package (autonomous MVP)

- React + TypeScript + Vite frontend and FastAPI backend.
- Dedicated `/autonomous.html` CSV enrollment page and `/autonomous/enroll-csv` endpoint.
- Automatically creates/reuses the Thozhil project, creates a three-stage task chain per intern, assigns stage 1, and emails task/deadline/submission/review links.
- Public token-protected submission page at `/task-submit.html`, so interns can submit without creating a password.
- Automatic private browser interview session creation, interview report, evidence-presence gate, successor task allocation, correction cycle, and fresh resubmission/review links.
- Hourly reminder agent using APScheduler.
- Optional Google Calendar API integration for real Calendar events with Meet links after one-time OAuth configuration.
- Optional local Ollama evaluation.

## Important implementation boundary

This is not a fully production-hardened multi-agent LLM system. Several workflow agents are implemented as deterministic backend services and the optional Ollama model handles interview evaluation. Submitted repository code is not executed in a hardened sandbox. The AI avatar interview runs in the InternMind browser room; Google Calendar API creates a Meet event but does not make the AI avatar join/speak inside the Meet call. A dedicated supported real-time meeting-agent integration would still be required for that exact behavior.

## Autonomous agent design

| Agent | Responsibility | Inputs | Outputs / actions |
|---|---|---|---|
| 1. Identity & Onboarding Agent | Normalize email, detect duplicate registrations, create intern profile and skills record | Registration form / approved CSV | Intern profile, welcome message, onboarding status |
| 2. Project Decomposer Agent | Break project goals into small task packages with explicit acceptance criteria and dependencies | Project brief, requirements, task bank | Task graph, unique task IDs, dependency links |
| 3. Fair Allocation Agent | Match tasks using skills, completed work, workload and dependency readiness; avoid duplicate assignment | Intern profiles, task graph, assignment history | Per-intern task plan and allocation explanation |
| 4. Deadline & Review Scheduler Agent | Estimate effort, set deadline and review window, avoid calendar conflicts | Task estimate, timezone, availability | Proposed schedule; calendar event when Google OAuth is connected |
| 5. Communication Agent | Send task details, due date, rubric, submission URL, review time and meeting link | Assignment + schedule | Email delivery status and reminder schedule |
| 6. Voice Mentor Agent | Explain the task, answer questions grounded in task docs, provide examples and speak answers | Task context, project knowledge base, intern question | Voice/text response and unresolved-question record |
| 7. Submission Intake Agent | Accept repository URLs, text, file metadata and required evidence; validate allowed types | Submission form | Versioned submission and completeness report |
| 8. Evidence & Test Agent | Check required files, rubric coverage, run approved tests in an isolated sandbox when configured | Submission, acceptance criteria, test suite | Test results, missing evidence, reproducible findings |
| 9. Independent Review Agent | Review against a fixed rubric; separate verified facts from uncertain judgments | Task rubric, evidence, test results | Score by criterion, evidence citations, confidence and decision recommendation |
| 10. Skeptic / Verification Agent | Challenge unsupported claims, check contradictory findings and re-run critical checks | Review output and raw evidence | Verified review, uncertainty flags, escalation reason |
| 11. Correction Coach Agent | Turn failed criteria into small actionable corrections with examples and a new deadline | Verified review | Correction checklist, new review slot and email |
| 12. Progression Agent | Approve only when required gates pass; assign the next dependency-ready task | Verified review, task graph, workload | APPROVED / CORRECTION_REQUIRED and next task assignment |
| 13. Risk & Fairness Agent | Detect overdue work, repeated failures, workload imbalance, missing data and anomalous scores | Activity and assignment history | Reminders, schedule adjustment proposals and audit events |
| 14. Audit & Privacy Agent | Record agent decisions, versions, evidence references and retention status | Every workflow action | Immutable-style audit trail and retention jobs |

## Unique differentiators (not just a chatbot)

1. **Personal Task DNA:** each task is linked to a competency, requirement, difficulty, expected evidence and dependency. The next task is based on demonstrated mastery, not only task completion.
2. **Skeptic Agent:** a second agent tries to disprove the reviewer’s claims and flags unsupported pass decisions.
3. **Evidence-linked feedback:** each correction references the exact acceptance criterion and the evidence that failed it.
4. **Adaptive difficulty:** if an intern repeatedly struggles, the planner can assign a smaller prerequisite task; if they consistently pass, it can unlock a harder task.
5. **Review Replay:** preserve submission version, rubric version, test logs and review result so the intern can see what changed between attempts.
6. **No-silent-failure delivery:** every email/calendar action has SENT, FAILED or PREVIEW status; failed delivery creates a retry and dashboard alert.
7. **Fair workload allocation:** balance task complexity and due dates across 100 interns, rather than assigning only by row order.
8. **Project Completion Passport:** generate a final skill evidence report listing completed tasks, test results, revisions and demonstrated competencies.

## Autonomous workflow

1. Registration arrives through a form or CSV. Normalize email and deduplicate before creating a profile.
2. Decomposer creates a dependency graph and acceptance criteria. Allocation agent assigns an eligible task to each intern.
3. Scheduler proposes deadlines and review windows in the intern's timezone.
4. Communication agent emails the task ID, goal, instructions, acceptance checklist, submission method, due date, review time and Meet URL.
5. Intern uses the voice/text mentor and submits a GitHub link/files/evidence.
6. Intake agent validates completeness. Evidence agent runs checks and only runs code inside a configured isolated sandbox.
7. Reviewer scores every criterion. Skeptic agent verifies evidence and checks contradictions.
8. If all mandatory gates pass and confidence is above configured threshold, progression agent approves and assigns the next dependency-ready task. If not, correction coach creates a checklist, schedules a re-review and sends feedback.
9. Risk agent handles reminders, missed deadlines and repeated failures. Every state transition is logged.
10. When all required tasks pass, generate a project completion report.

## Decision policy

- A model's opinion alone must not mark arbitrary code as correct. Use objective tests, required artifact checks and rubric evidence.
- Suggested initial policy: `AUTO_APPROVE` only when all mandatory tests pass, all required evidence exists, no security/quality blocker is detected, and reviewer + skeptic agents agree above a configurable confidence threshold. Otherwise `CORRECTION_REQUIRED` or `NEEDS_MORE_EVIDENCE`.
- Limit automatic retries and repeated review loops. If an item remains ambiguous after the configured retry count, pause that one workflow and notify the configured operations mailbox. This is a reliability exception, not a routine human review requirement.
- Never run submitted code on the main application server. Use a disposable container/sandbox with no secrets, restricted network and CPU/memory/time limits.

## External integrations required for real automation

### Gmail delivery

Set `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, and `SMTP_FROM` in `.env`. For Gmail, use an App Password when available; do not use the normal account password. Test with an address you control before importing real interns. The existing demo seed script deliberately refuses to run with SMTP enabled.

### Real Google Meet links and Calendar invitations

The current app does not create real Google Meet events. Add Google Cloud project configuration, enable Google Calendar API, configure OAuth consent and authorized redirect URLs, obtain tokens for the calendar owner, then create a Calendar event with conference data. Store event ID, event URL, timezone and status. A meeting URL must be confirmed by the API before emailing it; never invent a Meet link.

### AI model

For a no-cost local model option, configure Ollama and a model that fits the machine. It is not a guarantee of correct evaluation. For hosted models, configure a provider and budget separately. Keep a deterministic fallback for basic workflow checks.

### Code testing

Use task-specific test commands in an isolated execution service. The application server must never `exec` an intern's submitted code directly. If no sandbox is configured, report code correctness as `NOT_VERIFIED` rather than passing it automatically.

### Background scheduling

Use a persistent queue/scheduler (for example, APScheduler for a small prototype or Celery + Redis for a larger deployment) for reminders, retries, deadline checks and calendar sync. A web request alone is not a durable scheduler.

## Current implementation status

The ZIP is a development MVP, not a finished zero-human production system. The present app still requires a project operator to create tasks, trigger review/QA, and provide schedule details in parts of the workflow. It supports CSV imports, SMTP sending when configured, a browser voice/avatar room and basic rules/LLM evaluation. It does not yet include production Google Calendar OAuth/Meet creation, isolated code execution, a durable background queue, a complete intern self-registration portal or a fully autonomous reviewer/progression loop across every submission route.

Do not describe the system as fully autonomous until those integrations and end-to-end tests are implemented and verified.
