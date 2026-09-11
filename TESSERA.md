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

In the near term, success means: **Tessera reliably does a small number of well-defined things, and is honest about the rest.**

The product should reduce the amount of computer work the human must personally perform, not merely reduce the amount of typing needed to communicate with an AI.

The ultimate goal is not to build the most complicated agent. It is to build the **most capable local computer agent we can while keeping its core understandable, modular, verifiable, efficient, private by default, and under the user's control.**
