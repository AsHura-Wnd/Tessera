# Tessera — Agent Instructions

## Mission
Tessera is a private, local-first autonomous web research and data-mining agent. Its purpose is to turn messy web information into verified, structured, reusable knowledge.

Core workflow:

`discover → collect → understand → extract → verify → normalize → deduplicate → store → compare → report → monitor`

Tessera is NOT:
- a generic browser automation demo
- a screenshot-clicking agent
- a Browser Use clone
- a hardcoded scraper for one website
- a cloud-first research service
- a CAPTCHA bypass system
- a claim of general AGI

## Current Project State
The repository is intentionally minimal. Do not assume architecture or implementation exists merely because a component is described below.

Before writing implementation code, inspect the repository and produce an architecture/research plan. Code should follow from that plan.

## Prior Work to Study
A previous project, Vision Lite (`Ankur016xo/browser-agent`), is the main internal reference. Its useful ideas include:
- Playwright browser control
- Qwen2.5-VL through Ollama
- deterministic DOM grounding before vision
- visible interactive-element extraction
- screenshot/SOM perception as a fallback
- candidate ranking and evaluation
- task constraints and requested quantities
- exploration budgets and state tracking
- verification and loop detection
- URL/product-link extraction
- table extraction
- explicit failure tracking

Do not copy Vision Lite wholesale. Identify which ideas generalize to research/data extraction and which were specific to browser task execution.

Browser Use should be studied as an architectural reference, especially its mature DOM/accessibility/browser-state handling, extraction, persistence, and tool abstractions. Do not blindly reproduce its architecture or dependency footprint.

## Intelligence Hierarchy
Prefer the cheapest and most deterministic source of truth:
1. Browser/DOM state and structured page data
2. Accessibility tree and semantic browser state
3. Page structure, tables, links, metadata, and other deterministic signals
4. Local text-model reasoning
5. Local vision model only when ambiguity genuinely requires visual understanding

Vision is a fallback, not the default perception mechanism.

## Local-First Constraint
Primary development environment is Windows with Python, Playwright, Ollama, and Qwen2.5-VL 3B.

Prefer local inference and local storage wherever practical. External services must be optional and clearly separated from the core architecture.

## Target Capabilities
Tessera should eventually be able to:
- understand a natural-language research request
- plan research and identify useful source types
- discover multiple relevant sources
- navigate dynamic/authenticated websites when permitted
- collect large numbers of records
- extract requested fields into structured records
- normalize inconsistent values
- verify important claims against sources
- preserve source URLs and evidence/provenance
- deduplicate and merge records
- store reusable local knowledge
- search previously collected knowledge
- compare datasets/results over time
- produce CSV/JSON/table/report outputs
- monitor sources and detect meaningful changes

## Architecture Direction
The intended high-level flow is:

USER TASK
→ RESEARCH PLANNER
→ SOURCE DISCOVERY
→ BROWSER RUNTIME
→ PAGE INTELLIGENCE
→ EXTRACTION ENGINE
→ VERIFICATION + NORMALIZATION
→ DEDUPLICATION / MERGE
→ LOCAL KNOWLEDGE DB
→ REPORT / OUTPUT

Treat this as a direction, not a license to create all modules immediately. Validate boundaries and interfaces during the research phase.

## Engineering Principles
- Inspect existing code before changing it.
- Prefer small composable components over a giant agent loop.
- Keep deterministic operations deterministic.
- Separate browser control from research reasoning and extraction.
- Separate extraction from verification.
- Preserve provenance for every important extracted fact.
- Design for retries, partial failure, timeouts, and resumability.
- Avoid hidden global state.
- Avoid unnecessary dependencies.
- Keep provider/model integrations replaceable.
- Make behavior observable through structured logs and inspectable state.
- Write tests around deterministic logic before adding model-dependent behavior.
- Never fabricate extracted data when a source is ambiguous; represent uncertainty explicitly.

## Research-First Rule
For the initial implementation phase:
1. Inspect this repository.
2. Inspect Vision Lite's code and architecture.
3. Inspect the relevant Browser Use architecture/current APIs.
4. Identify reusable concepts, weaknesses, and unnecessary complexity.
5. Propose Tessera's architecture, interfaces, dependency choices, and phased implementation plan.
6. Only then begin implementation after the plan is internally consistent.

Do not generate a large scaffold just to make the repository look complete.

## Security / Privacy
Tessera is intended for private/local use. Do not add telemetry, credential exfiltration, covert tracking, or unnecessary cloud data transfer. Authenticated browsing must use user-authorized sessions/profiles and respect site access controls.

## Definition of Quality
A successful research run is not merely "the browser found something." It should produce structured records whose important fields can be traced back to source evidence, with uncertainty and conflicts represented rather than hidden.
