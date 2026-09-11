# Tessera

## Identity

Tessera is a **local-first autonomous computer agent** built around three fundamental capabilities:

> **FIND · DO · RUN**

Tessera's purpose is to turn a user's high-level goal into reliable computer work. It can find information and resources, perform tasks, and run software and system workflows across the web and the user's local computer.

Tessera is not defined by a particular model, browser, website, or interface. Local AI is a reasoning capability inside the system, not the system itself.

## Core Principles

### 1. Local-first and user-controlled

Tessera's core operation must work locally. Local models, local computation, local storage, local browser/runtime access, and local knowledge are first-class. Cloud services are optional integrations, never a requirement for the core agent.

User data remains local by default. Users may choose where persistent data lives, including an internal SSD, external HDD/SSD, NAS, or other user-controlled storage. Users may explicitly upload or synchronize selected data to cloud storage.

Tessera must not silently upload user data, trajectories, screenshots, files, prompts, or knowledge to third-party services.

### 2. No per-token dependency

Local inference should not require a cloud API token quota or per-token billing. Tessera must not promise literally infinite computation: hardware, context windows, storage, and time remain finite. The intended property is **no mandatory per-token cloud usage meter for core operation**.

### 3. Deterministic-first

Use deterministic mechanisms whenever they can reliably solve a problem. AI reasoning should be introduced where ambiguity, planning, interpretation, or adaptation actually requires it.

For web understanding, prefer:

`API/HTTP → DOM → accessibility → structured data → targeted text → local LLM → vision fallback`

Vision is a specialized fallback, not Tessera's identity or default mechanism.

### 4. Verification over confident guessing

Tessera should distinguish between information it observed, information it extracted, information it verified, and information it inferred. Important results should retain provenance and evidence where practical.

### 5. General mechanisms over special cases

Build mechanisms that generalize across websites, applications, files, and environments. Avoid accumulating website-specific hacks or one-off handlers unless a genuine integration requires them.

### 6. Small reliable primitives

Do not recreate the monolithic architecture that made Vision Lite difficult to evolve. Keep planning, acquisition, observation, extraction, verification, storage, and execution modular and testable.

### 7. Controlled autonomy

Autonomy means Tessera can understand a goal, plan work, select tools, act, observe outcomes, verify progress, recover from failures when possible, and stop when a completion condition is reached. It does not mean blindly allowing an LLM to control everything.

### 8. Honest boundaries

Tessera should not promise perfect autonomy, perfect verification, infinite context, infinite storage, or the ability to reliably operate every arbitrary application. Failures should be detectable, recoverable where possible, and explainable when they cannot be resolved.

---

# FIND · DO · RUN

## FIND

Find means discovery and retrieval, including locating relevant information inside a source.

Tessera should eventually find:

- web pages and websites
- products and services
- articles, papers, and documentation
- APIs and datasets
- files, folders, code, and documents
- databases and records
- specific facts or passages
- relevant sources and corroborating evidence
- previously stored knowledge

FIND is broader than web search: it applies to both the web and the local computer.

## DO

DO means performing useful work rather than merely explaining how to perform it.

Examples include:

- browser interaction and form completion
- file creation, editing, copying, moving, renaming, and conversion
- downloading and uploading
- extraction and data transformation
- dataset creation
- CSV, JSON, Excel, SQLite, and other outputs
- document processing
- research and comparison workflows
- repetitive computer workflows

## RUN

RUN means operating software, runtimes, commands, processes, and services.

Examples include:

- Python, Java, Node/npm, pip, Git, and CLI tools
- scripts and test suites
- databases
- local servers and background services
- Docker and development environments
- process inspection and logs
- build and execution workflows

FIND, DO, and RUN are composable primitives. Research, coding, data mining, browser automation, monitoring, and system workflows are higher-level compositions of them.

---

# Data and Storage Model

Tessera should treat persistent data as a first-class part of the product, while avoiding a single giant database for every byte it produces.

Conceptually the local data layer contains:

- **Knowledge** — entities, claims, sources, evidence, observations, relationships, research history.
- **Datasets** — structured outputs and large-scale mined data.
- **Trajectories** — task plans, actions, observations, failures, recovery, and outcomes.
- **Artifacts** — downloads, reports, exports, generated files, and retained raw resources.
- **Runtime state** — jobs, schedules, active tasks, process state, and operational metadata.
- **Logs and cache** — transient/operational information with appropriate retention policies.

The application and data must be separable. The data root must be configurable so users can place large datasets and historical data on an external HDD/SSD, NAS, or other storage.

Cloud storage/synchronization is optional and explicit.

Retention must be configurable. Tessera should not retain unlimited raw pages, screenshots, logs, or other bulky transient data by default merely because storage is available.

---

# User Experience

Tessera should ultimately be a **local service/engine with multiple interfaces**, rather than tying intelligence to one UI.

The intended architecture is:

`Tessera Engine → local API/IPC → CLI / local Web UI / Desktop app / system integrations`

### CLI

Useful for developers, automation, scripting, servers, and direct control.

### Local Web UI

A convenient primary interface for tasks, research, datasets, knowledge, trajectories, storage, history, and monitoring while the engine remains local.

### Desktop application

The eventual polished user-facing experience, potentially including a system tray, notifications, global hotkey, file context actions, and desktop integration.

The interface should not own the agent logic. A long-running task should be able to continue if a UI closes.

---

# Long-Term Capability Roadmap

The roadmap is deliberately staged. Each phase must produce a working, testable vertical slice before major expansion.

## Phase 1 — Core Agent

Build the smallest reliable Tessera.

- task representation
- local planner/reasoner interface
- tool interface
- Ollama/local model adapter
- local API/service
- CLI
- logging and configuration
- basic FIND/DO/RUN
- local file discovery and manipulation
- HTTP/web search basics
- Python/CLI execution

**Milestone:** Tessera can accept a useful goal, select tools, execute them, observe results, and return a verified-enough result.

## Phase 2 — Local Computer Agent

Expand local computer capabilities.

- files and folders
- documents and code
- installed software/environment discovery
- process inspection
- script execution
- test execution
- Git and development workflows
- error detection and recovery
- basic artifact management

**Milestone:** Tessera can perform multi-step local computer work instead of isolated commands.

## Phase 3 — Web Intelligence

Build general web mechanisms.

- HTTP acquisition
- search/discovery
- browser runtime
- DOM inspection
- accessibility inspection
- structured-data extraction
- dynamic pages
- navigation and interaction
- forms and downloads
- page-state observation
- targeted LLM reasoning
- vision fallback

**Milestone:** Tessera can operate across varied websites without a collection of site-specific hacks.

## Phase 4 — Research Engine

Compose FIND/DO/RUN into reliable research workflows.

`discover → collect → understand → extract → verify → normalize → deduplicate → store → compare → report`

Support source diversity, stopping conditions, evidence collection, and efficient acquisition rather than blindly visiting large numbers of pages.

## Phase 5 — Evidence and Verification

Make results trustworthy and auditable.

- provenance
- evidence objects
- source agreement
- numerical and categorical validation
- consistency checks
- conflict detection
- freshness
- confidence/status states

Possible statuses include verified, unverified, conflicting, stale, and unknown.

## Phase 6 — Persistent Local Knowledge

Create long-lived local memory.

- entities
- claims
- sources
- evidence
- relationships
- observations
- research history
- full-text search
- historical comparison

**Milestone:** Tessera can use useful knowledge from previous work rather than starting from zero every time.

## Phase 7 — Data Mining

Turn information sources into reusable structured data.

- crawling and pagination
- extraction pipelines
- normalization
- validation
- deduplication
- dataset metadata
- CSV/JSON/Excel/SQLite/Parquet outputs
- large dataset handling
- resumable jobs

**Milestone:** Tessera can perform substantial data collection and produce a reproducible dataset.

## Phase 8 — Trajectories and Observability

Record how tasks are performed.

- plans
- tool calls
- actions
- observations
- state transitions
- failures
- recovery
- timing
- resource usage
- outcomes

Use trajectories for debugging, evaluation, reproducibility, and optimization before attempting any automatic learning from them.

## Phase 9 — Reusable Skills

Convert stable successful procedures into reusable workflows/skills.

`successful trajectory → generalized procedure → reusable skill`

Do not prematurely build autonomous self-training. First establish reliable skill representation, validation, versioning, and reuse.

## Phase 10 — Continuous Monitoring

Support long-running goals.

- scheduled research
- price monitoring
- website/document change detection
- dataset monitoring
- application/status monitoring
- server checks
- notifications

Tessera should persist job state and resume work safely.

## Phase 11 — Desktop Control

Expand beyond browser and terminal environments.

- application discovery
- accessibility-based UI interaction
- structured desktop state
- dialogs and common system interactions
- screen understanding when structured mechanisms are insufficient

Vision remains fallback-oriented.

## Phase 12 — Databases and Servers

Make RUN a serious system capability.

- SQLite
- MySQL/PostgreSQL and similar databases where supported
- Redis and other services where useful
- Docker
- local servers
- background workers
- logs and health checks
- development/server troubleshooting

Example workflow:

`find service → inspect logs → find cause → modify → test → restart → verify`

## Phase 13 — Scalable Local Data Layer

Support serious amounts of data.

- database metadata/state
- large datasets on filesystems
- raw resource management
- trajectory archives
- artifact management
- retention policies
- storage quotas
- external drives
- NAS/network storage where appropriate
- backup/export

The application must not assume the system drive is the only storage device.

## Phase 14 — Optional Cloud Storage and Sync

Add explicit cloud capabilities without changing the local-first foundation.

- selected-data upload
- backup
- synchronization
- cloud dataset archival
- cross-device sharing
- user-controlled export/import

No silent upload and no mandatory cloud dependency.

## Phase 15 — Multi-Machine Tessera

Allow users to distribute workloads across machines they control.

Examples:

- desktop GPU for local inference
- workstation/server for heavy processing
- external/NAS storage for datasets
- laptop as a portable interface

Synchronization remains optional and user-controlled.

## Phase 16 — Multimodal Computer Understanding

Expand supported inputs when the underlying system is stable.

- text
- HTML/DOM
- accessibility trees
- PDFs
- images
- screenshots
- audio/video where justified

Use the cheapest and most reliable representation first.

## Phase 17 — Advanced Long-Horizon Planning

Handle larger goals composed of many dependent subtasks.

- hierarchical plans
- dynamic replanning
- dependency tracking
- resource budgets
- progress tracking
- partial completion
- safe stopping

The system must remain observable and bounded rather than becoming an uncontrolled autonomous loop.

## Phase 18 — Self-Evaluation and Optimization

Use collected trajectories and metrics to improve engineering and execution quality.

Measure:

- task success rate
- steps per task
- tool failures
- verification failures
- LLM calls
- latency
- resource usage
- unnecessary actions

Optimization should be evidence-driven rather than based on vague claims of self-improvement.

## Phase 19 — Extensible Skill/Tool Ecosystem

Provide stable interfaces for additional capabilities.

Possible domains:

- research
- browser
- data mining
- coding
- files
- databases
- system administration
- documents
- monitoring
- custom user tools

These should compose through the same FIND/DO/RUN foundation.

## Phase 20 — Local Computer Agent Platform

The mature vision:

> **A user can give Tessera a high-level goal and Tessera can reliably perform the necessary computer work across web, local software, data, files, runtimes, and systems, while keeping the user's data and control local by default.**

Other applications can integrate with Tessera through its local API and tool/skill interfaces.

---

# What Tessera Is Not

Tessera is not:

- a Browser Use clone
- a generic scraper
- a research chatbot
- a vision-first browser agent
- an LLM wrapper
- a single-model product
- a collection of website-specific hacks
- a monolithic autonomous agent
- an AGI claim

Browser automation, research, scraping, coding, data mining, computer vision, and system administration are capabilities or workflows—not the definition of Tessera.

---

# Definition of Success

Tessera succeeds when a user can increasingly say:

> **"Tessera, do this."**

instead of:

> "Tessera, tell me how to do this."

The product should reduce the amount of computer work the human must personally perform, not merely reduce the amount of typing needed to communicate with an AI.

The ultimate goal is not to build the most complicated agent. It is to build the **most capable local computer agent we can while keeping its core understandable, modular, verifiable, efficient, private by default, and under the user's control.**
