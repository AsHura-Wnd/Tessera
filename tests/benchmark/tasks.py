"""Benchmark task definitions for Tessera Phase 1.

Source of truth: tests/benchmark/README.md.
Contains exact canonical task definitions for FIND-01..FIND-05 and DO-01..DO-05.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from tessera.models.provider import ProviderResult
from tessera.verification.verifier import VerificationSpec


@dataclass(frozen=True)
class BenchmarkTask:
    """Canonical definition of a Phase 1 benchmark task."""

    task_id: str
    task_type: str
    name: str
    goal: str
    fixture_files: Mapping[str, str]
    verification_spec: VerificationSpec
    max_steps: int
    deterministic_responses: Sequence[ProviderResult]


# --- Task Definitions ---

FIND_01 = BenchmarkTask(
    task_id="FIND-01",
    task_type="FIND",
    name="Deep File Discovery by Name",
    goal="Find the file named 'database.sqlite' in the project tree and write its relative path (using forward slashes, ending with a single newline) to 'found_db.txt'.",
    fixture_files={
        "docs/guide.txt": "User manual for the service.\n",
        "src/core/app.py": "import sqlite3\nDB_PATH = 'storage/backups/2026/database.sqlite'\n",
        "storage/backups/2026/database.sqlite": "SQLITE_BINARY_DUMMY_HEADER\n",
    },
    verification_spec=VerificationSpec(
        file_exists=[
            "found_db.txt",
            "docs/guide.txt",
            "src/core/app.py",
            "storage/backups/2026/database.sqlite",
        ],
        exact_contents={
            "found_db.txt": "storage/backups/2026/database.sqlite\n",
            "docs/guide.txt": "User manual for the service.\n",
            "src/core/app.py": "import sqlite3\nDB_PATH = 'storage/backups/2026/database.sqlite'\n",
            "storage/backups/2026/database.sqlite": "SQLITE_BINARY_DUMMY_HEADER\n",
        },
    ),
    max_steps=4,
    deterministic_responses=[
        ProviderResult.create_tool_call(
            tool_name="file_find",
            arguments={"directory": ".", "pattern": "database.sqlite"},
        ),
        ProviderResult.create_tool_call(
            tool_name="file_write",
            arguments={
                "path": "found_db.txt",
                "content": "storage/backups/2026/database.sqlite\n",
                "overwrite": True,
            },
        ),
        ProviderResult.create_text("Found database.sqlite at storage/backups/2026/database.sqlite and wrote path to found_db.txt"),
    ],
)

FIND_02 = BenchmarkTask(
    task_id="FIND-02",
    task_type="FIND",
    name="Extension Pattern Match & Inventory",
    goal="Find all log files with extension '.log' in the workspace. Sort their relative paths alphabetically in ascending ASCII order (using forward slashes) and write them (one per line, ending with a trailing newline) to 'log_inventory.txt'.",
    fixture_files={
        "app.log": "2026-09-11 [INFO] Service started\n",
        "data/records.csv": "id,name\n1,alpha\n",
        "data/trace.log": "2026-09-11 [TRACE] Ping received\n",
        "logs/audit.log": "2026-09-11 [AUDIT] User login: admin\n",
        "logs/audit.log.bak": "2026-09-10 [AUDIT] Backup log\n",
    },
    verification_spec=VerificationSpec(
        file_exists=[
            "log_inventory.txt",
            "app.log",
            "data/records.csv",
            "data/trace.log",
            "logs/audit.log",
            "logs/audit.log.bak",
        ],
        exact_contents={
            "log_inventory.txt": "app.log\ndata/trace.log\nlogs/audit.log\n",
            "app.log": "2026-09-11 [INFO] Service started\n",
            "data/records.csv": "id,name\n1,alpha\n",
            "data/trace.log": "2026-09-11 [TRACE] Ping received\n",
            "logs/audit.log": "2026-09-11 [AUDIT] User login: admin\n",
            "logs/audit.log.bak": "2026-09-10 [AUDIT] Backup log\n",
        },
    ),
    max_steps=4,
    deterministic_responses=[
        ProviderResult.create_tool_call(
            tool_name="file_find",
            arguments={"directory": ".", "pattern": "*.log"},
        ),
        ProviderResult.create_tool_call(
            tool_name="file_write",
            arguments={
                "path": "log_inventory.txt",
                "content": "app.log\ndata/trace.log\nlogs/audit.log\n",
                "overwrite": True,
            },
        ),
        ProviderResult.create_text("Identified all .log files and recorded sorted inventory to log_inventory.txt"),
    ],
)

FIND_03 = BenchmarkTask(
    task_id="FIND-03",
    task_type="FIND",
    name="Key-Value Value Extraction",
    goal="Read 'config/deploy.env', find the value assigned to 'PRODUCTION_PORT', and write only that numeric port number (ending with a single trailing newline) to 'port.txt'.",
    fixture_files={
        "config/deploy.env": (
            "# Deployment Environment Configuration\n"
            "STAGING_PORT=3000\n"
            "DEBUG_PORT=8080\n"
            "PRODUCTION_HOST=internal.srv\n"
            "PRODUCTION_PORT=9443\n"
            "ADMIN_EMAIL=ops@company.local\n"
        ),
    },
    verification_spec=VerificationSpec(
        file_exists=["port.txt", "config/deploy.env"],
        exact_contents={
            "port.txt": "9443\n",
            "config/deploy.env": (
                "# Deployment Environment Configuration\n"
                "STAGING_PORT=3000\n"
                "DEBUG_PORT=8080\n"
                "PRODUCTION_HOST=internal.srv\n"
                "PRODUCTION_PORT=9443\n"
                "ADMIN_EMAIL=ops@company.local\n"
            ),
        },
    ),
    max_steps=3,
    deterministic_responses=[
        ProviderResult.create_tool_call(
            tool_name="file_read",
            arguments={"path": "config/deploy.env"},
        ),
        ProviderResult.create_tool_call(
            tool_name="file_write",
            arguments={
                "path": "port.txt",
                "content": "9443\n",
                "overwrite": True,
            },
        ),
        ProviderResult.create_text("Extracted PRODUCTION_PORT value 9443 and saved to port.txt"),
    ],
)

FIND_04 = BenchmarkTask(
    task_id="FIND-04",
    task_type="FIND",
    name="Multi-File Candidate Identification",
    goal="Among the log files in the 'logs/' directory, find which file recorded the 'CRITICAL_AUTH_FAILURE' event. Write only the base filename (e.g. 'auth_03.log', ending with a single trailing newline) to 'culprit.txt'.",
    fixture_files={
        "logs/auth_01.log": (
            "2026-09-11 10:00:00 INFO: Session initiated\n"
            "2026-09-11 10:01:00 INFO: Auth success\n"
        ),
        "logs/auth_02.log": (
            "2026-09-11 10:05:00 WARNING: Retrying login\n"
            "2026-09-11 10:05:30 WARNING: Rate limit approaching\n"
        ),
        "logs/auth_03.log": (
            "2026-09-11 10:10:00 ERROR: CRITICAL_AUTH_FAILURE invalid root signature\n"
            "2026-09-11 10:10:01 ALERT: Connection terminated\n"
        ),
        "logs/auth_04.log": (
            "2026-09-11 10:15:00 INFO: Healthcheck ok\n"
        ),
    },
    verification_spec=VerificationSpec(
        file_exists=[
            "culprit.txt",
            "logs/auth_01.log",
            "logs/auth_02.log",
            "logs/auth_03.log",
            "logs/auth_04.log",
        ],
        exact_contents={
            "culprit.txt": "auth_03.log\n",
            "logs/auth_01.log": (
                "2026-09-11 10:00:00 INFO: Session initiated\n"
                "2026-09-11 10:01:00 INFO: Auth success\n"
            ),
            "logs/auth_02.log": (
                "2026-09-11 10:05:00 WARNING: Retrying login\n"
                "2026-09-11 10:05:30 WARNING: Rate limit approaching\n"
            ),
            "logs/auth_03.log": (
                "2026-09-11 10:10:00 ERROR: CRITICAL_AUTH_FAILURE invalid root signature\n"
                "2026-09-11 10:10:01 ALERT: Connection terminated\n"
            ),
            "logs/auth_04.log": (
                "2026-09-11 10:15:00 INFO: Healthcheck ok\n"
            ),
        },
    ),
    max_steps=8,
    deterministic_responses=[
        ProviderResult.create_tool_call(
            tool_name="file_find",
            arguments={"directory": "logs", "pattern": "*.log"},
        ),
        ProviderResult.create_tool_call(
            tool_name="file_read",
            arguments={"path": "logs/auth_01.log"},
        ),
        ProviderResult.create_tool_call(
            tool_name="file_read",
            arguments={"path": "logs/auth_02.log"},
        ),
        ProviderResult.create_tool_call(
            tool_name="file_read",
            arguments={"path": "logs/auth_03.log"},
        ),
        ProviderResult.create_tool_call(
            tool_name="file_write",
            arguments={
                "path": "culprit.txt",
                "content": "auth_03.log\n",
                "overwrite": True,
            },
        ),
        ProviderResult.create_text("Identified culprit file auth_03.log and saved to culprit.txt"),
    ],
)

FIND_05 = BenchmarkTask(
    task_id="FIND-05",
    task_type="FIND",
    name="Bounded Line-Range Extraction",
    goal="Locate the report file in 'reports/', extract lines 5 through 7 (inclusive), and write those exact lines (with their existing line content and trailing newlines) to 'quarterly_summary.txt'.",
    fixture_files={
        "reports/notes.txt": "Draft ideas for upcoming year.\n",
        "reports/report_q3.txt": (
            "Line 1: Q3 Comprehensive Review\n"
            "Line 2: Confidential - Internal Only\n"
            "Line 3: Author: Analytics Team\n"
            "Line 4: Date: September 2026\n"
            "Line 5: Metric A: 1,420 active users\n"
            "Line 6: Metric B: 99.95% uptime achieved\n"
            "Line 7: Metric C: zero security incidents\n"
            "Line 8: Appendix 1: Raw telemetry\n"
            "Line 9: Appendix 2: Sign-off signatures\n"
            "Line 10: End of Document\n"
        ),
    },
    verification_spec=VerificationSpec(
        file_exists=[
            "quarterly_summary.txt",
            "reports/notes.txt",
            "reports/report_q3.txt",
        ],
        exact_contents={
            "quarterly_summary.txt": (
                "Line 5: Metric A: 1,420 active users\n"
                "Line 6: Metric B: 99.95% uptime achieved\n"
                "Line 7: Metric C: zero security incidents\n"
            ),
            "reports/notes.txt": "Draft ideas for upcoming year.\n",
            "reports/report_q3.txt": (
                "Line 1: Q3 Comprehensive Review\n"
                "Line 2: Confidential - Internal Only\n"
                "Line 3: Author: Analytics Team\n"
                "Line 4: Date: September 2026\n"
                "Line 5: Metric A: 1,420 active users\n"
                "Line 6: Metric B: 99.95% uptime achieved\n"
                "Line 7: Metric C: zero security incidents\n"
                "Line 8: Appendix 1: Raw telemetry\n"
                "Line 9: Appendix 2: Sign-off signatures\n"
                "Line 10: End of Document\n"
            ),
        },
    ),
    max_steps=5,
    deterministic_responses=[
        ProviderResult.create_tool_call(
            tool_name="file_find",
            arguments={"directory": "reports", "pattern": "*report*"},
        ),
        ProviderResult.create_tool_call(
            tool_name="file_read",
            arguments={"path": "reports/report_q3.txt", "start_line": 5, "end_line": 7},
        ),
        ProviderResult.create_tool_call(
            tool_name="file_write",
            arguments={
                "path": "quarterly_summary.txt",
                "content": (
                    "Line 5: Metric A: 1,420 active users\n"
                    "Line 6: Metric B: 99.95% uptime achieved\n"
                    "Line 7: Metric C: zero security incidents\n"
                ),
                "overwrite": True,
            },
        ),
        ProviderResult.create_text("Extracted lines 5-7 from reports/report_q3.txt to quarterly_summary.txt"),
    ],
)

DO_01 = BenchmarkTask(
    task_id="DO-01",
    task_type="DO",
    name="Create File with Exact Content",
    goal="Create a new file at 'build/metadata.json' with the exact content: '{\"version\": \"1.0.0\", \"status\": \"ready\"}'",
    fixture_files={},
    verification_spec=VerificationSpec(
        file_exists=["build/metadata.json"],
        exact_contents={
            "build/metadata.json": '{"version": "1.0.0", "status": "ready"}',
        },
    ),
    max_steps=2,
    deterministic_responses=[
        ProviderResult.create_tool_call(
            tool_name="file_write",
            arguments={
                "path": "build/metadata.json",
                "content": '{"version": "1.0.0", "status": "ready"}',
                "overwrite": True,
            },
        ),
        ProviderResult.create_text("Created build/metadata.json with required content"),
    ],
)

DO_02 = BenchmarkTask(
    task_id="DO-02",
    task_type="DO",
    name="Complete File Overwrite",
    goal="Update the existing 'status.txt' file by replacing its contents entirely with 'SERVICE_ACTIVE: ALL SYSTEMS NOMINAL'.",
    fixture_files={
        "status.txt": "MAINTENANCE_MODE: OFFLINE\n",
    },
    verification_spec=VerificationSpec(
        file_exists=["status.txt"],
        exact_contents={
            "status.txt": "SERVICE_ACTIVE: ALL SYSTEMS NOMINAL",
        },
    ),
    max_steps=2,
    deterministic_responses=[
        ProviderResult.create_tool_call(
            tool_name="file_write",
            arguments={
                "path": "status.txt",
                "content": "SERVICE_ACTIVE: ALL SYSTEMS NOMINAL",
                "overwrite": True,
            },
        ),
        ProviderResult.create_text("Overwrote status.txt with new status"),
    ],
)

DO_03 = BenchmarkTask(
    task_id="DO-03",
    task_type="DO",
    name="Targeted Search-and-Replace Edit",
    goal="In 'config/app.cfg', update the setting 'timeout = 30' to 'timeout = 120'. Do not change any other settings or comments.",
    fixture_files={
        "config/app.cfg": (
            "# Core Application Configuration\n"
            "app_name = TesseraService\n"
            "timeout = 30\n"
            "retries = 3\n"
            "keep_alive = true\n"
            "# End of Core Configuration\n"
        ),
    },
    verification_spec=VerificationSpec(
        file_exists=["config/app.cfg"],
        exact_contents={
            "config/app.cfg": (
                "# Core Application Configuration\n"
                "app_name = TesseraService\n"
                "timeout = 120\n"
                "retries = 3\n"
                "keep_alive = true\n"
                "# End of Core Configuration\n"
            ),
        },
    ),
    max_steps=3,
    deterministic_responses=[
        ProviderResult.create_tool_call(
            tool_name="file_edit",
            arguments={
                "path": "config/app.cfg",
                "target": "timeout = 30",
                "replacement": "timeout = 120",
            },
        ),
        ProviderResult.create_text("Updated timeout setting to 120 in config/app.cfg"),
    ],
)

DO_04 = BenchmarkTask(
    task_id="DO-04",
    task_type="DO",
    name="Read-Filter-Write Transformation",
    goal="Read 'data/raw_users.txt', filter for only users whose status is 'ACTIVE', and write their usernames in original encounter order (one per line, ending with a trailing newline) to 'data/active_users.txt'. Do not modify 'data/raw_users.txt'.",
    fixture_files={
        "data/raw_users.txt": (
            "alice:ACTIVE:admin\n"
            "bob:INACTIVE:guest\n"
            "carol:ACTIVE:member\n"
            "dave:PENDING:guest\n"
            "eve:ACTIVE:member\n"
        ),
    },
    verification_spec=VerificationSpec(
        file_exists=["data/raw_users.txt", "data/active_users.txt"],
        exact_contents={
            "data/raw_users.txt": (
                "alice:ACTIVE:admin\n"
                "bob:INACTIVE:guest\n"
                "carol:ACTIVE:member\n"
                "dave:PENDING:guest\n"
                "eve:ACTIVE:member\n"
            ),
            "data/active_users.txt": (
                "alice\n"
                "carol\n"
                "eve\n"
            ),
        },
    ),
    max_steps=4,
    deterministic_responses=[
        ProviderResult.create_tool_call(
            tool_name="file_read",
            arguments={"path": "data/raw_users.txt"},
        ),
        ProviderResult.create_tool_call(
            tool_name="file_write",
            arguments={
                "path": "data/active_users.txt",
                "content": "alice\ncarol\neve\n",
                "overwrite": True,
            },
        ),
        ProviderResult.create_text("Filtered active users and wrote to data/active_users.txt"),
    ],
)

DO_05 = BenchmarkTask(
    task_id="DO-05",
    task_type="DO",
    name="End-to-End Find, Read, and Update",
    goal="Locate the database migration log matching 'migration_*.log' in 'migrations/', extract the generated 'AUTH_TOKEN' value, and update 'config/security.json' by replacing 'UNCONFIGURED' with that token in the 'db_token' field (preserving surrounding indentation and structure). Do not modify the migration logs. Do not create any temporary files.",
    fixture_files={
        "config/security.json": (
            "{\n"
            '  "env": "production",\n'
            '  "db_token": "UNCONFIGURED",\n'
            '  "encryption": "AES256"\n'
            "}\n"
        ),
        "migrations/migration_v1.log": (
            "Migration v1 completed. No token issued.\n"
        ),
        "migrations/migration_v2_final.log": (
            "Migration v2 successful. AUTH_TOKEN=tok_sec_9876543210_xyz. Ready.\n"
        ),
    },
    verification_spec=VerificationSpec(
        file_exists=[
            "config/security.json",
            "migrations/migration_v1.log",
            "migrations/migration_v2_final.log",
        ],
        exact_contents={
            "config/security.json": (
                "{\n"
                '  "env": "production",\n'
                '  "db_token": "tok_sec_9876543210_xyz",\n'
                '  "encryption": "AES256"\n'
                "}\n"
            ),
            "migrations/migration_v1.log": (
                "Migration v1 completed. No token issued.\n"
            ),
            "migrations/migration_v2_final.log": (
                "Migration v2 successful. AUTH_TOKEN=tok_sec_9876543210_xyz. Ready.\n"
            ),
        },
        forbidden_files=["token.txt", "temp.txt", "migrations/token.txt"],
    ),
    max_steps=6,
    deterministic_responses=[
        ProviderResult.create_tool_call(
            tool_name="file_find",
            arguments={"directory": "migrations", "pattern": "migration_*.log"},
        ),
        ProviderResult.create_tool_call(
            tool_name="file_read",
            arguments={"path": "migrations/migration_v2_final.log"},
        ),
        ProviderResult.create_tool_call(
            tool_name="file_edit",
            arguments={
                "path": "config/security.json",
                "target": '"db_token": "UNCONFIGURED"',
                "replacement": '"db_token": "tok_sec_9876543210_xyz"',
            },
        ),
        ProviderResult.create_text("Security token updated in config/security.json"),
    ],
)

RUN_01 = BenchmarkTask(
    task_id="RUN-01",
    task_type="RUN",
    name="Local Verification Script Execution",
    goal="Execute the verification script 'check_env.py' using process_run with command 'python' and arguments ['check_env.py']. Observe the output line 'STATUS=OPERATIONAL' and write 'STATUS=OPERATIONAL\n' to 'summary.txt'.",
    fixture_files={
        "check_env.py": (
            "import sys\n\n"
            "print('STATUS=OPERATIONAL')\n"
            "sys.exit(0)\n"
        ),
    },
    verification_spec=VerificationSpec(
        file_exists=["summary.txt", "check_env.py"],
        exact_contents={
            "summary.txt": "STATUS=OPERATIONAL\n",
            "check_env.py": (
                "import sys\n\n"
                "print('STATUS=OPERATIONAL')\n"
                "sys.exit(0)\n"
            ),
        },
    ),
    max_steps=4,
    deterministic_responses=[
        ProviderResult.create_tool_call(
            tool_name="process_run",
            arguments={"command": "python", "arguments": ["check_env.py"]},
        ),
        ProviderResult.create_tool_call(
            tool_name="file_write",
            arguments={
                "path": "summary.txt",
                "content": "STATUS=OPERATIONAL\n",
                "overwrite": True,
            },
        ),
        ProviderResult.create_text("Executed check_env.py and wrote status to summary.txt."),
    ],
)

RUN_02 = BenchmarkTask(
    task_id="RUN-02",
    task_type="RUN",
    name="Test-Driven Defect Repair",
    goal="Execute 'test_calc.py' using process_run with command 'python' and arguments ['test_calc.py']. Observe the failure in stderr, edit 'calc.py' using file_edit to fix the defect so the test passes, rerun 'test_calc.py' using process_run to observe exit code 0, and write 'TESTS_PASSED\n' to 'status.txt'.",
    fixture_files={
        "calc.py": (
            "def add(a, b):\n"
            "    return a - b\n"
        ),
        "test_calc.py": (
            "from calc import add\n\n\n"
            "def test_add():\n"
            "    assert add(2, 3) == 5\n\n\n"
            "if __name__ == '__main__':\n"
            "    test_add()\n"
            "    print('ALL_TESTS_PASSED')\n"
        ),
    },
    verification_spec=VerificationSpec(
        file_exists=["status.txt", "calc.py", "test_calc.py"],
        exact_contents={
            "status.txt": "TESTS_PASSED\n",
            "calc.py": (
                "def add(a, b):\n"
                "    return a + b\n"
            ),
            "test_calc.py": (
                "from calc import add\n\n\n"
                "def test_add():\n"
                "    assert add(2, 3) == 5\n\n\n"
                "if __name__ == '__main__':\n"
                "    test_add()\n"
                "    print('ALL_TESTS_PASSED')\n"
            ),
        },
    ),
    max_steps=6,
    deterministic_responses=[
        ProviderResult.create_tool_call(
            tool_name="process_run",
            arguments={"command": "python", "arguments": ["test_calc.py"]},
        ),
        ProviderResult.create_tool_call(
            tool_name="file_edit",
            arguments={
                "path": "calc.py",
                "target": "return a - b",
                "replacement": "return a + b",
            },
        ),
        ProviderResult.create_tool_call(
            tool_name="process_run",
            arguments={"command": "python", "arguments": ["test_calc.py"]},
        ),
        ProviderResult.create_tool_call(
            tool_name="file_write",
            arguments={
                "path": "status.txt",
                "content": "TESTS_PASSED\n",
                "overwrite": True,
            },
        ),
        ProviderResult.create_text("Fixed calc.py, verified test_calc.py passes, and recorded status to status.txt."),
    ],
)

EVAL_01 = BenchmarkTask(
    task_id="EVAL-01",
    task_type="EVAL",
    name="Test Failure Repair",
    goal="Run the test suite in 'test_calc.py'. If tests fail, identify the cause, make the necessary correction in 'calc.py', rerun 'test_calc.py' to verify the fix passes, and write 'TESTS_PASSED\n' to 'status.txt'.",
    fixture_files={
        "calc.py": (
            "def multiply(a, b):\n"
            "    return a + b\n"
        ),
        "test_calc.py": (
            "import sys\n\n"
            "sys.dont_write_bytecode = True\n\n"
            "from calc import multiply\n\n\n"
            "def test_multiply():\n"
            "    assert multiply(3, 4) == 12\n\n\n"
            "if __name__ == '__main__':\n"
            "    test_multiply()\n"
            "    print('TESTS_PASSED')\n"
        ),
    },
    verification_spec=VerificationSpec(
        file_exists=["status.txt", "calc.py", "test_calc.py"],
        exact_contents={
            "status.txt": "TESTS_PASSED\n",
            "calc.py": (
                "def multiply(a, b):\n"
                "    return a * b\n"
            ),
            "test_calc.py": (
                "import sys\n\n"
                "sys.dont_write_bytecode = True\n\n"
                "from calc import multiply\n\n\n"
                "def test_multiply():\n"
                "    assert multiply(3, 4) == 12\n\n\n"
                "if __name__ == '__main__':\n"
                "    test_multiply()\n"
                "    print('TESTS_PASSED')\n"
            ),
        },
    ),
    max_steps=6,
    deterministic_responses=[
        ProviderResult.create_tool_call(
            tool_name="process_run",
            arguments={"command": "python", "arguments": ["test_calc.py"]},
        ),
        ProviderResult.create_tool_call(
            tool_name="file_edit",
            arguments={
                "path": "calc.py",
                "target": "return a + b",
                "replacement": "return a * b",
            },
        ),
        ProviderResult.create_tool_call(
            tool_name="process_run",
            arguments={"command": "python", "arguments": ["test_calc.py"]},
        ),
        ProviderResult.create_tool_call(
            tool_name="file_write",
            arguments={
                "path": "status.txt",
                "content": "TESTS_PASSED\n",
                "overwrite": True,
            },
        ),
        ProviderResult.create_text("Repaired calc.py, verified test_calc.py passes, and recorded status to status.txt."),
    ],
)

EVAL_02 = BenchmarkTask(
    task_id="EVAL-02",
    task_type="EVAL",
    name="Configuration Diagnosis",
    goal="Run 'check_config.py'. If the check fails, diagnose the configuration issue in 'config.json', make the necessary correction, rerun 'check_config.py' to verify it passes, and write 'CONFIG_REPAIRED\n' to 'status.txt'.",
    fixture_files={
        "config.json": (
            "{\n"
            '  "service_name": "gateway",\n'
            '  "port": 8080,\n'
            '  "environment": "development"\n'
            "}\n"
        ),
        "check_config.py": (
            "import json\n"
            "import sys\n\n"
            "with open('config.json', 'r', encoding='utf-8') as f:\n"
            "    cfg = json.load(f)\n\n"
            "if cfg.get('environment') != 'production':\n"
            '    sys.stderr.write(f"Invalid environment: {cfg.get(\'environment\')}. Expected \'production\'.\\n")\n'
            "    sys.exit(1)\n\n"
            "print('CONFIG_VALID')\n"
            "sys.exit(0)\n"
        ),
    },
    verification_spec=VerificationSpec(
        file_exists=["status.txt", "config.json", "check_config.py"],
        exact_contents={
            "status.txt": "CONFIG_REPAIRED\n",
            "config.json": (
                "{\n"
                '  "service_name": "gateway",\n'
                '  "port": 8080,\n'
                '  "environment": "production"\n'
                "}\n"
            ),
            "check_config.py": (
                "import json\n"
                "import sys\n\n"
                "with open('config.json', 'r', encoding='utf-8') as f:\n"
                "    cfg = json.load(f)\n\n"
                "if cfg.get('environment') != 'production':\n"
                '    sys.stderr.write(f"Invalid environment: {cfg.get(\'environment\')}. Expected \'production\'.\\n")\n'
                "    sys.exit(1)\n\n"
                "print('CONFIG_VALID')\n"
                "sys.exit(0)\n"
            ),
        },
    ),
    max_steps=6,
    deterministic_responses=[
        ProviderResult.create_tool_call(
            tool_name="process_run",
            arguments={"command": "python", "arguments": ["check_config.py"]},
        ),
        ProviderResult.create_tool_call(
            tool_name="file_edit",
            arguments={
                "path": "config.json",
                "target": '"environment": "development"',
                "replacement": '"environment": "production"',
            },
        ),
        ProviderResult.create_tool_call(
            tool_name="process_run",
            arguments={"command": "python", "arguments": ["check_config.py"]},
        ),
        ProviderResult.create_tool_call(
            tool_name="file_write",
            arguments={
                "path": "status.txt",
                "content": "CONFIG_REPAIRED\n",
                "overwrite": True,
            },
        ),
        ProviderResult.create_text("Corrected config.json environment, verified check_config.py passes, and recorded status to status.txt."),
    ],
)

EVAL_03 = BenchmarkTask(
    task_id="EVAL-03",
    task_type="EVAL",
    name="Log-Driven Local Repair",
    goal="Run 'app.py' to check authentication. If it fails, inspect the failure details and deployment logs in 'logs/deploy.log' to find the active token, update 'token.txt' with the active token, rerun 'app.py' to confirm authentication succeeds, and write 'TOKEN_REPAIRED\n' to 'status.txt'.",
    fixture_files={
        "app.py": (
            "import hashlib\n"
            "import sys\n"
            "from pathlib import Path\n\n"
            "token_file = Path('token.txt')\n"
            "if not token_file.is_file():\n"
            "    sys.stderr.write('Missing token.txt\\n')\n"
            "    sys.exit(1)\n\n"
            "token = token_file.read_text(encoding='utf-8').strip()\n"
            "expected_hash = 'ce4beeef474ee2c5fc3750767883fd17040b862f3a0fe178ad052205f6801568'\n"
            "actual_hash = hashlib.sha256(token.encode('utf-8')).hexdigest()\n\n"
            "if actual_hash != expected_hash:\n"
            '    sys.stderr.write(f"Authentication failed for token: \'{token}\'. Consult logs/deploy.log for the active issued token.\\n")\n'
            "    sys.exit(1)\n\n"
            "print('AUTH_SUCCESS')\n"
            "sys.exit(0)\n"
        ),
        "token.txt": "OLD-EXPIRED-TOKEN-000\n",
        "logs/deploy.log": (
            "[2026-09-15 08:00:00] Starting deployment sequence.\n"
            "[2026-09-15 08:00:05] Token OLD-EXPIRED-TOKEN-000 has expired and was revoked.\n"
            "[2026-09-15 08:00:10] Generating active service token...\n"
            "[2026-09-15 08:00:15] Active valid token issued: SEC-ALPHA-99482-PROD\n"
            "[2026-09-15 08:00:20] Deployment complete. Service listening.\n"
        ),
    },
    verification_spec=VerificationSpec(
        file_exists=["status.txt", "token.txt", "app.py", "logs/deploy.log"],
        exact_contents={
            "status.txt": "TOKEN_REPAIRED\n",
            "token.txt": "SEC-ALPHA-99482-PROD\n",
            "app.py": (
                "import hashlib\n"
                "import sys\n"
                "from pathlib import Path\n\n"
                "token_file = Path('token.txt')\n"
                "if not token_file.is_file():\n"
                "    sys.stderr.write('Missing token.txt\\n')\n"
                "    sys.exit(1)\n\n"
                "token = token_file.read_text(encoding='utf-8').strip()\n"
                "expected_hash = 'ce4beeef474ee2c5fc3750767883fd17040b862f3a0fe178ad052205f6801568'\n"
                "actual_hash = hashlib.sha256(token.encode('utf-8')).hexdigest()\n\n"
                "if actual_hash != expected_hash:\n"
                '    sys.stderr.write(f"Authentication failed for token: \'{token}\'. Consult logs/deploy.log for the active issued token.\\n")\n'
                "    sys.exit(1)\n\n"
                "print('AUTH_SUCCESS')\n"
                "sys.exit(0)\n"
            ),
            "logs/deploy.log": (
                "[2026-09-15 08:00:00] Starting deployment sequence.\n"
                "[2026-09-15 08:00:05] Token OLD-EXPIRED-TOKEN-000 has expired and was revoked.\n"
                "[2026-09-15 08:00:10] Generating active service token...\n"
                "[2026-09-15 08:00:15] Active valid token issued: SEC-ALPHA-99482-PROD\n"
                "[2026-09-15 08:00:20] Deployment complete. Service listening.\n"
            ),
        },
    ),
    max_steps=8,
    deterministic_responses=[
        ProviderResult.create_tool_call(
            tool_name="process_run",
            arguments={"command": "python", "arguments": ["app.py"]},
        ),
        ProviderResult.create_tool_call(
            tool_name="file_read",
            arguments={"path": "logs/deploy.log"},
        ),
        ProviderResult.create_tool_call(
            tool_name="file_write",
            arguments={
                "path": "token.txt",
                "content": "SEC-ALPHA-99482-PROD\n",
                "overwrite": True,
            },
        ),
        ProviderResult.create_tool_call(
            tool_name="process_run",
            arguments={"command": "python", "arguments": ["app.py"]},
        ),
        ProviderResult.create_tool_call(
            tool_name="file_write",
            arguments={
                "path": "status.txt",
                "content": "TOKEN_REPAIRED\n",
                "overwrite": True,
            },
        ),
        ProviderResult.create_text("Retrieved active token from logs/deploy.log, updated token.txt, verified app.py passes, and recorded status to status.txt."),
    ],
)

BENCHMARK_TASKS: dict[str, BenchmarkTask] = {
    "FIND-01": FIND_01,
    "FIND-02": FIND_02,
    "FIND-03": FIND_03,
    "FIND-04": FIND_04,
    "FIND-05": FIND_05,
    "DO-01": DO_01,
    "DO-02": DO_02,
    "DO-03": DO_03,
    "DO-04": DO_04,
    "DO-05": DO_05,
    "RUN-01": RUN_01,
    "RUN-02": RUN_02,
    "EVAL-01": EVAL_01,
    "EVAL-02": EVAL_02,
    "EVAL-03": EVAL_03,
}


def get_task(task_id: str) -> BenchmarkTask:
    """Retrieve benchmark task specification by ID."""
    if task_id not in BENCHMARK_TASKS:
        raise KeyError(f"Unknown benchmark task ID: '{task_id}'. Valid IDs: {list(BENCHMARK_TASKS.keys())}")
    return BENCHMARK_TASKS[task_id]


def list_tasks() -> list[BenchmarkTask]:
    """Retrieve all benchmark task specifications in canonical order."""
    return list(BENCHMARK_TASKS.values())
