# Tessera Phase 1 Benchmark

This benchmark is the concrete acceptance artifact for Phase 1 of Tessera.

It evaluates whether Tessera behaves as a small local agent rather than merely exposing file-operation functions.

## Evaluation rule

- 10 canonical tasks: 5 FIND and 5 DO.
- FIND tasks in Phase 1 are **local-filesystem-only**.
- Each task is run 3 times independently.
- A task passes if at least 2 of its 3 runs produce the independently verified correct outcome.
- Phase 1 passes when at least **9 of 10 tasks** pass.
- A valid trajectory must be recorded for every execution.
- Human verification is required for the final benchmark result.

The benchmark is an evaluator, not part of Tessera's agent behavior.

> **Anti-gaming rule:** Do not implement the benchmark as agent functionality. The benchmark must remain external to Tessera's execution logic. Do not add task-specific logic, filenames, expected answers, or special-case branches to Tessera to make benchmark tasks pass. Tessera must only receive the user goal and the tools permitted by the task.

## Common task specification

Every task defines:

- **Task ID**
- **Category** — FIND or DO
- **User goal** — the exact natural-language request given to Tessera
- **Initial workspace** — files/directories available before execution
- **Allowed tools** — the only Tessera tools permitted for the task
- **Expected outcome** — what a correct completion must produce or identify
- **Verification procedure** — an independent check performed outside the agent
- **Failure conditions** — conditions that make the execution incorrect
- **Trajectory requirements** — minimum information that must be recorded

The initial workspaces should contain realistic distractors and should not expose the answer through a task-specific filename.

---

# FIND Tasks

## FIND-01 — Identify a document by content

**Category:** FIND

**User goal:**

> Find the document that contains the final Q3 revenue figure and tell me the revenue figure and the path of the document containing it.

**Initial workspace:**

```text
workspace/
├── reports/
│   ├── annual_report.txt
│   ├── q3_draft.txt
│   ├── q3_final.txt
│   └── q3_notes.txt
├── archive/
│   └── q3_final_old.txt
└── notes/
    ├── meeting_notes.txt
    └── unrelated.txt
```

Several files contain related Q3 information. Only `reports/q3_final.txt` contains the final figure and an explicit final-status statement. The archive file contains an older figure.

**Allowed tools:** `file_find`, `file_read`

**Expected outcome:**

Tessera identifies `reports/q3_final.txt` and reports the final Q3 revenue figure exactly as written in that file.

**Verification:**

Independently read the workspace files and compare both the selected path and reported figure against the canonical expected values.

**Failure conditions:**

- selecting the archived or draft report
- returning a figure from an incorrect file
- reporting a value not present in the selected file
- stopping at a plausible but non-final match

**Trajectory requirements:**

Record the goal, FIND actions, observations/results, selected file, and stopping decision.

---

## FIND-02 — Locate information across multiple files

**Category:** FIND

**User goal:**

> Find the project owner and the current deployment environment for the Orion project. The information may be split across different files.

**Initial workspace:**

```text
workspace/
├── projects/
│   ├── orion_overview.txt
│   ├── orion_history.txt
│   └── atlas_overview.txt
├── config/
│   ├── production.txt
│   ├── staging.txt
│   └── development.txt
└── notes/
    └── meeting.txt
```

The owner is stated in the Orion project information. The current deployment environment is stated in a configuration file. Other files contain stale or unrelated information.

**Allowed tools:** `file_find`, `file_read`

**Expected outcome:**

Tessera returns both the correct Orion owner and the current deployment environment, with the paths of the files supporting each result.

**Verification:**

Independently inspect the relevant files and compare both values and paths with the canonical expected values.

**Failure conditions:**

- using stale project information
- confusing Orion with Atlas
- returning only one of the two required facts
- claiming an environment without locating supporting local information

**Trajectory requirements:**

Record searches, files inspected, observations, extracted facts, and the stopping decision.

---

## FIND-03 — Select the relevant match among distractors

**Category:** FIND

**User goal:**

> Find the customer support policy that applies to enterprise customers and was updated after July 2026. Give me its path and effective date.

**Initial workspace:**

```text
workspace/
├── policies/
│   ├── support_standard.txt
│   ├── support_enterprise_old.txt
│   ├── support_enterprise_current.txt
│   └── support_partner.txt
├── archive/
│   └── support_enterprise_2025.txt
└── notes/
    └── policy_changes.txt
```

Multiple files mention enterprise support. Only one is both the enterprise policy and newer than July 2026.

**Allowed tools:** `file_find`, `file_read`

**Expected outcome:**

Tessera identifies `policies/support_enterprise_current.txt` and reports its correct effective date.

**Verification:**

Independently inspect all relevant candidate files and verify the policy audience, update/effective date, and selected path.

**Failure conditions:**

- selecting an older enterprise policy
- selecting a partner or standard policy
- treating a mention in notes as the policy itself
- returning an incorrect date

**Trajectory requirements:**

Record candidate discovery, relevant file reads, comparison reasoning/result, and stopping decision.

---

## FIND-04 — Resolve multiple valid matches using an additional condition

**Category:** FIND

**User goal:**

> Find all files containing the term "rollback", then identify which one describes the rollback procedure for the production database. Give me that file's path and the first step of the procedure.

**Initial workspace:**

```text
workspace/
├── docs/
│   ├── application_rollback.txt
│   ├── production_db_rollback.txt
│   ├── staging_rollback.txt
│   └── release_notes.txt
└── archive/
    └── database_rollback_2025.txt
```

Several files contain `rollback`, but only one describes the production database rollback procedure.

**Allowed tools:** `file_find`, `file_read`

**Expected outcome:**

Tessera identifies the production database rollback document and reports its first procedure step exactly enough to be independently verified.

**Verification:**

Independently search/read the workspace and verify that the selected document is the production database procedure and that the reported first step matches it.

**Failure conditions:**

- selecting application, staging, or archived rollback instructions
- returning a generic mention instead of a procedure
- returning the wrong first step

**Trajectory requirements:**

Record the initial search, candidate set, files inspected, final selection, extracted step, and stopping decision.

---

## FIND-05 — Multi-step local discovery

**Category:** FIND

**User goal:**

> Find the incident report referenced by the latest deployment handoff notes, then tell me the incident severity and the service that was affected.

**Initial workspace:**

```text
workspace/
├── handoff/
│   ├── deployment_handoff_latest.txt
│   ├── deployment_handoff_old.txt
│   └── unrelated_handoff.txt
├── incidents/
│   ├── incident_041.txt
│   ├── incident_042.txt
│   └── incident_043.txt
└── notes/
    └── incident_summary.txt
```

The latest handoff identifies the incident report by reference. The referenced report contains the severity and affected service. Other incident files and the summary contain misleading or stale information.

**Allowed tools:** `file_find`, `file_read`

**Expected outcome:**

Tessera first identifies the latest deployment handoff, follows its incident reference to the correct incident report, and returns the correct severity and affected service.

**Verification:**

Independently verify the latest handoff, referenced incident path, severity, and affected service.

**Failure conditions:**

- starting from the wrong handoff
- selecting an incident without following the reference
- using stale summary information
- returning incorrect severity/service
- continuing to search after sufficient information is established

**Trajectory requirements:**

Record the discovery chain from handoff to incident report, observations at each step, final facts, and stopping decision.

---

# DO Tasks

## DO-01 — Read, transform, and create

**Category:** DO

**User goal:**

> Read the approved team list and create `exports/team_count.txt` containing the number of approved team members and the names of those members, one per line.

**Initial workspace:**

```text
workspace/
├── source/
│   ├── team_list.txt
│   ├── old_team_list.txt
│   └── notes.txt
└── exports/
    └── README.txt
```

`source/team_list.txt` contains the current approved team list. The old list is deliberately similar but has different membership.

**Allowed tools:** `file_find`, `file_read`, `file_write`

**Expected outcome:**

Create exactly `exports/team_count.txt` containing the correct count and approved member names derived from the current team list.

**Verification:**

Independently read the source and output files and verify the count, names, path, and absence of accidental changes to existing files.

**Failure conditions:**

- using the old list
- incorrect count or names
- failing to create the output
- modifying unrelated files
- claiming completion without a correct output file

**Trajectory requirements:**

Record source discovery/read, transformation decision, write action, resulting file state, verification, and stopping decision.

---

## DO-02 — Precise edit without collateral changes

**Category:** DO

**User goal:**

> In `config/app.txt`, change only the `timeout` value from 30 to 45 seconds. Preserve every other line exactly as it is.

**Initial workspace:**

```text
workspace/
└── config/
    ├── app.txt
    └── app_backup.txt
```

`app.txt` contains multiple settings, including `timeout=30`, and unrelated comments/configuration that must remain unchanged.

**Allowed tools:** `file_find`, `file_read`, `file_edit`

**Expected outcome:**

Only the intended timeout value changes from `30` to `45`. Every other byte/line of `app.txt` remains unchanged.

**Verification:**

Compare the resulting file against a canonical expected file or a before/after diff. Verify that only the intended value changed.

**Failure conditions:**

- overwriting the whole file with reconstructed content that changes unrelated content
- changing another setting
- changing formatting or unrelated whitespace when avoidable
- modifying `app_backup.txt`
- leaving the timeout unchanged

**Trajectory requirements:**

Record the original file observation, targeted edit, resulting state, verification result, and stopping decision.

---

## DO-03 — Multi-file transformation

**Category:** DO

**User goal:**

> Read the three monthly sales files and create `reports/q2_summary.txt` containing the total number of orders and total revenue for Q2. Do not modify the source files.

**Initial workspace:**

```text
workspace/
├── sales/
│   ├── april.txt
│   ├── may.txt
│   ├── june.txt
│   └── april_old.txt
└── reports/
    └── README.txt
```

The three current monthly files contain the Q2 data. `april_old.txt` is a distractor and must not be included.

**Allowed tools:** `file_find`, `file_read`, `file_write`

**Expected outcome:**

Create `reports/q2_summary.txt` with the correct total order count and total revenue calculated from April, May, and June current files only.

**Verification:**

Independently calculate the expected totals from the canonical source files, compare them to the output, and verify that no source file changed.

**Failure conditions:**

- including the old April file
- missing a month
- incorrect arithmetic
- modifying source files
- creating an incorrect or incomplete report

**Trajectory requirements:**

Record file discovery, all source reads, aggregation result, output write, verification, and stopping decision.

---

## DO-04 — Recover from an expected file-operation failure

**Category:** DO

**User goal:**

> Create `output/summary.txt` containing the line `Status: ready`. If the destination directory does not exist, create the required directory and then complete the task.

**Initial workspace:**

```text
workspace/
├── input/
│   └── instructions.txt
└── output.txt
```

The `output/` directory does not initially exist. The task is intentionally constructed so that attempting to write directly to the destination can fail because the parent directory is absent.

**Allowed tools:** `file_find`, `file_read`, `file_write`, `file_edit`

**Expected outcome:**

Create the required `output/` directory using the capabilities actually available in the Phase 1 implementation, then create `output/summary.txt` with exactly the required line. Do not modify `output.txt`.

**Verification:**

Independently verify directory existence, exact output content, and preservation of unrelated files.

**Failure conditions:**

- infinite retrying of the same failed operation
- modifying `output.txt`
- creating incorrect content
- claiming success when the destination does not exist
- using an unapproved capability outside the task's allowed tool set

**Trajectory requirements:**

Record the failed attempt if one occurs, the observed failure, recovery decision, successful action, verification, and stopping decision.

---

## DO-05 — End-to-end local agent task

**Category:** DO

**User goal:**

> Find the latest approved release notes for Project Atlas, extract the release version and release date, and create `reports/atlas_release.txt` with the format `Version: <version>` on the first line and `Date: <date>` on the second line. Leave all source files unchanged.

**Initial workspace:**

```text
workspace/
├── releases/
│   ├── atlas_release_draft.txt
│   ├── atlas_release_2026_06.txt
│   ├── atlas_release_2026_08.txt
│   └── atlas_release_old.txt
├── notes/
│   ├── atlas_release_discussion.txt
│   └── unrelated.txt
└── reports/
    └── README.txt
```

The latest approved release is identified by content/status, not merely by filename. Draft and old release notes are distractors. The correct task requires discovery, reading, selection, extraction, writing, and verification.

**Allowed tools:** `file_find`, `file_read`, `file_write`, `file_edit`

**Expected outcome:**

Tessera identifies the latest approved Atlas release, extracts its canonical version/date, creates `reports/atlas_release.txt` in the exact required two-line format, and leaves source files unchanged.

**Verification:**

Independently determine the latest approved release from the workspace, compare version/date with the generated report, verify exact output formatting, and confirm that all source files are unchanged.

**Failure conditions:**

- selecting a draft or older release
- selecting solely by filename without validating approval/current status
- incorrect version or date
- malformed output
- modifying source files
- claiming success without independently verifiable output

**Trajectory requirements:**

Record goal interpretation, discovery actions, candidate observations, final source selection, extracted values, write action, verification result, and stopping decision.

---

# Benchmark integrity rules

1. **No benchmark-specific code in Tessera.** Tasks must be solved through the same Phase 1 interfaces used for ordinary user goals.
2. **No hidden answer injection.** Expected answers belong to the evaluator, not to Tessera's tool registry, prompts, or runtime state.
3. **No task-specific filenames or branches.** Tessera must not contain logic that recognizes benchmark task IDs, known filenames, or expected outputs.
4. **Independent verification.** Verification must be performed outside the agent's reasoning path and must inspect the actual resulting filesystem state.
5. **Fresh task state.** Each run starts from the canonical initial workspace for that task; previous runs must not modify later runs.
6. **Trajectory for every run.** Even failed runs must produce enough trajectory data to determine what Tessera attempted and where it stopped.
7. **Human review.** Automated checks may assist evaluation, but the Phase 1 milestone requires human verification of the final benchmark outcomes.
8. **No scope expansion to pass the benchmark.** If a task cannot be completed with the Phase 1 capability set, first determine whether the task is invalid for the stated scope. Do not silently introduce Phase 2+ capabilities just to obtain a passing score.

# Phase 1 benchmark result

Record the final result after implementation:

```text
Tasks passing: __ / 10
Runs passing: __ / 30
Phase 1 milestone: PASS / FAIL
Human verification: YES / NO
```

A failed benchmark is useful evidence. The correct response is to inspect the trajectories, identify whether the failure is in task design, tooling, model behavior, orchestration, or architecture, and then apply the roadmap's GO / MODIFY / MERGE / ABANDON decision process.
