# Tessera Roadmap

The roadmap is a **hypothesis, not a contract**.

Tessera's long-term direction is ambitious, but the near-term work must remain small, measurable, and evidence-driven. A later phase may be cut, merged, reordered, or redesigned when real implementation and trajectory data show that the current plan is wrong.

---

# Near-Term Development Direction

These phases represent the current development direction. They are not unconditional commitments: each phase must earn continuation through its exit criteria.

## Phase 1 — Local Agent Core

**Status:** Current

Build the smallest useful and reliable Tessera.

**Timebox:** Target 3–4 weeks of focused work. Review the phase at that point regardless of completion status.

### Scope

- task representation
- bounded execution state and stopping conditions
- model/provider interface
- configurable local Ollama adapter
- tool interface and registry
- fixed allow-list validation for tool calls
- per-task action budgets for tool usage
- explicit capability and safety boundaries within the fixed Phase 1 tool set
- local file discovery
- local file read/write/edit operations
- append-only trajectory recording
- deterministic verification
- CLI only: `tessera run "<goal>"`

### Explicitly out of scope

- web search and HTTP/network access
- browser automation
- vision/multimodal processing
- arbitrary command/process execution
- local API/IPC service
- web UI or desktop UI
- databases and knowledge graphs
- large-scale data mining
- cloud integrations
- reusable skills
- self-learning/self-optimization

### Architectural rule

The model proposes structured intent. Tessera validates that proposal against registered tools, schemas, safety policy, workspace boundaries, budgets, and stopping conditions before execution. The model/provider must remain replaceable and must not own the execution layer.

`ModelProvider → replaceable model backend`

A model such as `qwen2.5vl:3b` may be used for development if available, but no specific model is canonical or required by Tessera's architecture. Phase 1 reasoning is text-first.

### Phase 1 safety boundary

Each tool call is checked against a fixed allow-list of Phase 1 operations and a per-task action budget (for example, a maximum number of file writes/edits). Phase 1 does **not** introduce a dynamic policy engine, general permission framework, or generalized sandboxing system.

### Phase 1 benchmark

Define 10 predefined local tasks:

- 5 FIND tasks
- 5 DO tasks

FIND tasks in this phase are **local-filesystem-only**, such as locating a file matching criteria or locating text within files.

Run the benchmark repeatedly and record a trajectory for every execution.

### Milestone

> **Tessera completes at least 9/10 predefined test tasks with a human-verified correct outcome, with a valid trajectory recorded for every run.**

The benchmark should test actual agent behavior—goal interpretation, tool selection, execution, observation, and stopping—not a hidden hardcoded sequence.

### Phase 1 verification boundary

Deterministic verification in Phase 1 means checking local file state before/after an operation and confirming that the resulting file content or expected state matches the task's objective. It should not grow into the broader evidence/provenance system planned for later phases.

### Phase exit

Before moving forward, inspect benchmark results and trajectories. Decide whether the architecture should **GO, MODIFY, MERGE, or ABANDON** the next planned step.

---

## Phase 2 — Local Computer Execution

**Status:** Planned

Expand Tessera from local file work into controlled software and system execution.

Potential capabilities:

- command/process execution
- Python, Java, Node/npm, Git, and other CLI tools
- script execution
- test execution
- installed software/environment discovery
- process inspection
- logs and error inspection
- artifact management
- bounded recovery from execution failures

### Milestone direction

Tessera can perform multi-step local computer work instead of being limited to file operations.

The exact implementation should be determined by Phase 1 evidence and should preserve explicit capability boundaries and approval requirements for dangerous operations.

---

## Phase 3 — Web Intelligence

**Status:** Planned

Introduce networked information acquisition only after the local agent core is reliable.

Potential capabilities:

- HTTP acquisition
- web search/discovery
- browser runtime
- DOM inspection
- accessibility inspection
- structured-data extraction
- dynamic-page handling
- navigation and interaction
- forms and downloads
- page-state observation
- targeted LLM reasoning
- vision fallback where structured mechanisms are insufficient

### Milestone direction

Tessera can operate across varied websites using general mechanisms rather than a collection of site-specific hacks.

The acquisition stack should remain deterministic-first:

`HTTP/API → DOM → accessibility → structured data → targeted text → local LLM → vision fallback`

---

## Phase 4 — Research and Verification

**Status:** Planned

Compose FIND, DO, and RUN into reliable research workflows.

Potential workflow:

`discover → collect → understand → extract → verify → normalize → deduplicate → store → compare → report`

Potential capabilities:

- source discovery
- source diversity
- evidence collection
- stopping conditions
- efficient acquisition budgets
- extraction and normalization
- deduplication and merging
- provenance
- verification and conflict detection
- research reports

### Milestone direction

Tessera can turn a high-level research request into a bounded, reproducible workflow whose important conclusions are supported by retained evidence and provenance.

The exact architecture remains subject to Phase 1–3 results.

---

# Future Direction — Unscoped, Aspirational

The following capabilities describe plausible long-term directions. They are **not numbered commitments, scheduled sprints, or promises that Tessera will implement all of them**.

## Persistent Local Knowledge

Long-lived local knowledge containing entities, claims, sources, evidence, relationships, observations, research history, full-text search, and historical comparison.

## Data Mining

Substantial information collection and structured dataset production, including crawling, pagination, normalization, validation, deduplication, dataset metadata, CSV/JSON/Excel/SQLite/Parquet outputs, large-dataset handling, and resumable jobs.

## Trajectories and Observability

Rich records of plans, tool calls, actions, observations, state transitions, failures, recovery, timing, resource usage, and outcomes for debugging, evaluation, reproducibility, and optimization.

## Reusable Skills

Stable successful procedures generalized into reusable, validated, versioned workflows rather than prematurely attempting autonomous self-training.

## Continuous Monitoring

Scheduled research, price monitoring, change detection, dataset/application/server monitoring, persistent job state, safe resumption, and notifications.

## Desktop Control

Application discovery, accessibility-based interaction, structured desktop state, dialogs and common system interactions, with visual understanding used only when structured mechanisms are insufficient.

## Databases and Servers

Serious RUN capabilities for SQLite, supported SQL databases, services, Docker, local servers, background workers, logs, health checks, development workflows, and troubleshooting.

## Scalable Local Data Layer

Large datasets, database metadata/state, raw resource management, trajectory archives, artifact management, retention policies, storage quotas, external drives, NAS/network storage, backup, and export.

## Optional Cloud Storage and Sync

Explicit user-controlled upload, backup, synchronization, archival, sharing, and export/import without changing Tessera's local-first foundation.

## Multi-Machine Execution

Potential distribution of workloads across machines the user controls—for example, using a desktop GPU for inference, a workstation/server for heavy processing, and NAS/external storage for datasets.

This is intentionally **not a current commitment** and should only be pursued if real use cases justify the added distributed-systems complexity.

## Multimodal Computer Understanding

Text, HTML/DOM, accessibility trees, PDFs, images, screenshots, and potentially audio/video where justified. Use the cheapest and most reliable representation first.

## Advanced Long-Horizon Planning

Hierarchical plans, dynamic replanning, dependency tracking, resource budgets, progress tracking, partial completion, and safe stopping while remaining observable and bounded.

## Self-Evaluation and Optimization

Evidence-driven optimization using trajectories and metrics such as task success rate, steps per task, tool failures, verification failures, model calls, latency, resource usage, and unnecessary actions.

## Extensible Skill and Tool Ecosystem

Stable interfaces for research, browser, data mining, coding, files, databases, system administration, documents, monitoring, and custom user tools, all composed through FIND/DO/RUN.

## Local Computer Agent Platform

The long-term vision is a local computer agent that can take a high-level goal and reliably perform the necessary computer work across web, local software, data, files, runtimes, and systems while keeping the user's data and control local by default.

---

# Uncommitted Infrastructure Ideas

Some possible capabilities are especially infrastructure-heavy and should not be treated as inevitable product phases:

- multi-machine/distributed execution
- advanced service orchestration
- large-scale workload scheduling
- complex cross-device synchronization
- autonomous self-training systems

They may be built if validated by actual user needs and evidence. They may also be permanently rejected.

---

# Kill / Go Criteria

Every phase ends with an explicit review.

A phase may be:

- **GO** — evidence supports continuing as planned.
- **MODIFY** — the goal is sound but the architecture or implementation needs to change.
- **MERGE** — the phase overlaps another capability and should be combined.
- **ABANDON** — evidence shows the capability is unnecessary, impractical, or harmful to the project's core.

### Rules

1. The roadmap is a hypothesis, not a contract.
2. Real trajectory data and benchmark results outrank the roadmap.
3. A failed architectural assumption must be corrected rather than defended because work has already been invested.
4. Do not add a new subsystem merely because it appears later on this roadmap.
5. Every phase must produce a working, testable vertical slice before major expansion.
6. A phase is not complete because its code exists; it is complete when its acceptance criteria are met.

This is deliberate protection against scope creep, sunk-cost reasoning, and repeating the architectural failure mode of Vision Lite.
