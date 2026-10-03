# Tessera

**A local-first autonomous computer agent built around FIND · DO · RUN.**

Tessera is an AI-powered computer agent designed to turn high-level goals into reliable computer work. It can find information, interact with web pages, work with local files, and execute system workflows — while keeping execution controlled, verifiable, and user-directed.

Tessera is built around a simple idea: **AI should propose actions, but the system should remain in control of execution.**

## ✨ Core Capabilities

- **FIND** — Search, retrieve, and extract information from web pages and local resources.
- **DO** — Interact with web pages through browser automation, including navigation, clicking, filling forms, and selecting options.
- **RUN** — Execute local commands, manage files, and perform system workflows within defined boundaries.

### Key Principles

- **Local-first:** Designed to run with locally hosted models, reducing dependence on external APIs.
- **Deterministic-first:** Prefer reliable, predictable tools over unnecessary model-driven behavior.
- **Controlled autonomy:** AI-generated actions are validated before execution.
- **Verifiable results:** Tool outputs and evidence help ground the agent's decisions.
- **Provider-agnostic:** The model provider can be changed without redesigning the agent's core.
- **Security by design:** Tool permissions, workspace boundaries, and execution policies help limit unintended actions.

## 🏗️ Architecture

Tessera uses a closed-loop agent architecture. The `AgentLoop` coordinates model decisions, validates proposed actions, executes tools, and evaluates the resulting observations.

```text
                 USER GOAL
                     |
                     v
                AgentLoop
                     |
                     v
              Model Provider
                     |
             Structured Proposal
                     |
                     v
          Validation & Authorization
                     |
                     v
              Tool Execution
                     |
          +----------+----------+
          |          |          |
          v          v          v
         WEB        LOCAL      SYSTEM
          |          |          |
          +----------+----------+
                     |
                     v
                Observation
                     |
                     v
              AgentLoop (repeat)
                     |
                     v
              Final Response
```

The model acts as a decision-making component, not as an execution authority. Tessera validates proposed tool calls before allowing them to run.

## 🧠 Model Support

Tessera supports locally hosted models through [Ollama](https://ollama.com/).

The current default model is **Qwen3.5 9B**, while other compatible models can be selected at runtime.

Pull the default model:

```bash
ollama pull qwen3.5:9b
```

Run it:

```bash
ollama run qwen3.5:9b
```

Tessera's model selection follows this precedence:

1. Explicit `--model` argument
2. `TESSERA_MODEL` environment variable
3. Default model: `qwen3.5:9b`

This keeps the core independent of a specific model and allows experimentation with different local providers and models.

## ⚙️ Getting Started

### Requirements

- Python
- [Ollama](https://ollama.com/)
- A locally available model supported by your configured provider
- Chromium, installed through the project's browser setup, for browser automation

### Setup

Clone the repository:

```bash
git clone https://github.com/AsHura-Wnd/Tessera.git
cd Tessera
```

Install the project's dependencies using the package and dependency configuration included in the repository.

Pull the default model:

```bash
ollama pull qwen3.5:9b
```

Check the CLI:

```bash
python -m tessera --help
```

> Refer to the repository's current dependency configuration and setup instructions for the exact installation and browser initialization steps.

## 🚀 Usage

Tessera uses the `run` command to execute a task.

### Run a task

```bash
python -m tessera run "Create hello.txt containing exactly: Hello from Tessera." --workspace ./workspace
```

### Choose a model

```bash
python -m tessera run "Create a summary file." --workspace ./workspace --model qwen3.5:9b
```

### Limit execution steps

```bash
python -m tessera run "Find information about AI agents." --workspace ./workspace --max-steps 5
```

### Enable live execution

```bash
python -m tessera run "Your task here." --workspace ./workspace --live
```

### Use a headed browser

```bash
python -m tessera run "Your browser task here." --workspace ./workspace --live --headed
```

### Allow local network access

```bash
python -m tessera run "Your task here." --workspace ./workspace --live --allow-local
```

`--allow-local` enables access to local and loopback network targets where supported. Use it only when the task requires that access and you understand the implications.

For the full list of supported arguments, run:

```bash
python -m tessera run --help
```

## 🔐 Security

Tessera is designed to keep model-generated decisions separate from tool execution.

Security mechanisms include:

- **Tool validation:** Proposed tool calls are checked before execution.
- **Authorization:** Tool permissions and execution policies restrict which operations are allowed.
- **Workspace boundaries:** Local file and process operations are designed to remain anchored to the configured workspace.
- **Browser session ownership:** Browser tools are bound to their authorized sessions.
- **Network protections:** HTTP operations apply restrictions intended to reduce risks such as server-side request forgery (SSRF).
- **Fail-closed behavior:** Invalid or untrusted tool configurations should be rejected rather than silently allowed.

Tessera is not an in-process sandbox against malicious Python code running with the same privileges. Its security controls are intended to constrain agent tool execution, not to replace operating-system isolation.

Always review the permissions and scope of tasks before enabling live execution or local network access.

## 🧪 Testing

Tessera includes automated tests covering its agent loop, tools, authorization, validation, browser operations, CLI, and benchmark workflows.

Run the full test suite:

```bash
python -m pytest
```

Run focused security tests:

```bash
python -m pytest tests/test_authorization.py tests/test_tool_validator.py tests/test_agent_loop.py
```

## ⚠️ Current Limitations

Tessera is actively being developed. Its capabilities and reliability depend on the selected model and the task being performed.

- Multi-step browser workflows may be inconsistent across models.
- Some models may produce malformed or unsupported tool-call outputs.
- Model-generated decisions can be incorrect and require validation.
- Advanced visual perception, OCR, arbitrary JavaScript execution, and unrestricted browser control are not part of the established core capabilities.
- Local model performance depends on available hardware and model compatibility.

Tessera should be treated as an evolving agent framework rather than a fully autonomous replacement for user supervision.

## 🗺️ Project Direction

Tessera is focused on improving the reliability of its core capabilities:

- More robust multi-step task execution
- Improved browser interaction and observation
- Stronger validation and verification
- Better evidence handling and provenance
- Model flexibility without coupling the core to one provider
- Reliable recovery from tool and model failures

The priority is to build small, testable, dependable primitives before expanding into more complex autonomy.

## 🤝 Contributing

Contributions, bug reports, and ideas are welcome.

When contributing, prioritize:

- Small, focused changes
- Clear security boundaries
- Reproducible tests
- Honest capability claims
- Compatibility with Tessera's local-first and provider-agnostic design

Please open an issue to discuss larger architectural changes before implementing them.

## 📄 License

Tessera is open-source software licensed under the [MIT License](https://opensource.org/license/mit).

You are free to use, modify, distribute, and commercialize the software, subject to the terms of the license.

See the `LICENSE` file for details.

---

**Tessera — FIND · DO · RUN**

*Turning intent into reliable computer work.*
