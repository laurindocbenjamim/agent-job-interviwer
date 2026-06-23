## Rules for Antigravity Project

### 🏛️ Architectural Pattern & Project Structure
* **Modular Monolith (Bounded Contexts)**: Always design the application as a monolith, but strictly segregated by business domains (Bounded Contexts) [1]. Each domain must encapsulate its own logic, routing, and models to allow future microservices extraction if needed.
* **Backend Structure (FastAPI)**: Organize by domain features, not by technical layers. Avoid global `routers/` or `models/` folders.
  ```text
  src/
  ├── config/             # Global configurations & env variables
  ├── shared/             # Shared utilities, database session, middleware
  └── domains/            # Bounded Contexts
      ├── users/          # Users Domain
      │   ├── router.py   # Endpoints for this domain
      │   ├── service.py  # Business logic
      │   ├── models.py   # Database models
      │   └── schemas.py  # Pydantic input/output validation
      └── orders/         # Orders Domain
          ├── router.py
          └── service.py
  ```
* **Frontend Structure**: Organize by feature modules containing their own components, state, and API hooks.
  ```text
  src/
  ├── assets/             # Global styles, images, fonts
  ├── shared/             # Global UI components (Button, Input), global context/hooks
  └── modules/            # Bounded Contexts / Features
      ├── auth/           # Authentication Feature
      │   ├── components/ # Module-specific components
      │   ├── hooks/      # Module-specific state/queries (e.g., TanStack Query)
      │   └── AuthPage.tsx
      └── dashboard/      # Dashboard Feature
          ├── components/
          └── DashboardPage.tsx
  ```

### 🛡️ Development & Methodology
* **Always use TDD approach**: Write your tests before writing the actual production code to guarantee correctness from the start.
* **Always create regression tests**: Ensure new changes never break existing behavior.
    * **Frontend**: Implement tests using **Cypress** or **Playwright**.
    * **Backend**: Implement tests using **Pytest** (for Python components).

* **Always create stress tests**: Ensure high-load resilience by implementing
    * **Backend**: Validate endpoints using simulated peak traffic. Target maximum concurrent users. Monitor CPU, memory, and database connection pools. Identify bottlenecks, leaks, and failure points before deployment

### 🔍 Observability & Error Tracking
* **Mandatory Sentry Integration**: Always integrate Sentry into the application architecture from day one.
    * **Frontend**: Track client-side exceptions, user context, and UI performance issues.
    * **Backend**: Capture unhandled API exceptions (e.g., FastAPI), request context, and database performance bottlenecks.

### ⚡ Optimization & Code Quality
* **Always create optimized scripts**: Focus on performance, efficient memory usage, algorithms with low time complexity, and clean execution.
* **Strict file size limit**: Never create a file with more than **200 lines of code**. Split logic into smaller, reusable modules if it exceeds this limit.
* **Dry & Modular Code**: Avoid code duplication. Reuse components and functions to keep the codebase small and highly maintainable.

### 🪙 Token Optimization (AI-Driven Development)
* **Concise Code Generation**: Write compact, clean code without verbose comments. Use self-explanatory variable and function names to reduce code volume.
* **No Boilerplate**: Avoid generating placeholder code, repetitive setups, or unnecessary boilerplate files unless explicitly requested.
* **Incremental Updates**: When modifying code, only output the specific lines or functions that changed. Do not rewrite unchanged parts of the file.

### 🔒 Application Security (SecOps)
* **Zero Hardcoded Secrets**: Never hardcode API keys, DSNs, tokens, or passwords. Always use environment variables (`.env`) managed via `pydantic-settings` or `python-dotenv`.
* **Input Validation & Sanitization**: Always validate and sanitize user inputs on the backend (e.g., using Pydantic models in FastAPI) to prevent SQL Injection and XSS attacks.
* **Secure Dependencies**: Only use verified, up-to-date libraries. Run security audits on dependencies regularly.


## Documentation
Always add docstring documentation to functions and important line os codes

Always Create and update the README or other documentation file for each new feature added

# AI Agent & FastAPI Development Guidelines

## 1. Architectural Patterns (Use with Intent)
- NEVER implement design patterns blindly. Apply them only to solve real architectural complexity.
- FACADE: Use to simplify FastAPI route handlers. Routes should only call a Facade/Service layer, keeping the HTTP layer thin.
- STRATEGY: Implement to abstract LLM providers (OpenAI, Anthropic, Ollama) and tools, making them interchangeable.
- STATE: Use to manage autonomous agent lifecycles (e.g., Planning, Executing, Reviewing, Idle).
- OBSERVER: Implement for event-driven logging, token counting, or streaming internal agent thoughts to WebSockets.
- DECORATOR: Apply for cross-cutting concerns like LLM response caching, rate limiting, and automated retries.

## 2. Financial & Currency Precision (Critical)
- NEVER use primitive `float` or `double` for currency, prices, or monetary values.
- ALWAYS use Python's built-in `decimal.Decimal` for monetary arithmetic to prevent floating-point rounding errors.
- Prefer encapsulating money into a Value Object (Data Class or Pydantic Model) containing both amount and currency.
- Example Pattern:
```python
from decimal import Decimal
from pydantic import BaseModel, Field

class Money(BaseModel):
    amount: Decimal = Field(..., max_digits=10, decimal_places=2)
    currency: str = "USD"
```

## 3. Strict Type Safety & Primitives
- Avoid "Primitive Obsession". If a primitive type (str, int) carries specific business rules or validation, wrap it in a Pydantic Custom Type or Value Object.
- ALWAYS use explicit Python type hints (`str`, `int`, `bool`, `dict`, `list`, or `typing` generics).
- Enable strict mode validation in Pydantic models when handling untrusted LLM outputs or external API payloads.
- Use `NewType` or Pydantic custom annotations for structural IDs (e.g., `AgentID`, `SessionID`) instead of generic strings.

## 4. FastAPI & Async Best Practices
- Define asynchronous endpoints (`async def`) for I/O bound operations, especially when waiting for LLM responses.
- Implement structured error handling using Custom FastAPI HTTPExceptions.
- Keep agent state externalized (e.g., in Redis or PostgreSQL) to ensure FastAPI instances remain stateless and horizontally scalable.


## 5. SOLID Principles Integration
- SRP: Keep FastAPI routers thin. Move orchestration to Facades and domain rules to Value Objects.
- OCP: Use the Strategy pattern to add new LLM providers or Agent Tools without modifying existing orchestrator code.
- LSP: Ensure all subclasses of an Agent State or LLM Strategy strictly adhere to the base class method signatures and return types.
- ISP: Create small, focused interfaces for Agent Tools (e.g., separate reading tools from mutating tools).
- DIP: Never instantiate LLM clients or repositories directly inside the Agent logic. Inject abstractions using FastAPI's `Depends`.

## 6. Code Management and Versioning (Git/GitHub)

Instead of just "pushing," the goal is to ensure the integrity of the main branch (`main`/`master`) and the traceability of the code.

* **Branch-Based Workflow (Git Flow / GitHub Flow):** Never commit directly to the main branch. Use feature branches (e.g., `feature/feature-name`, `bugfix/bug-fix`).

* **Code Review Approvals (Pull Requests):** No change goes into production without being reviewed by at least one other teammate (or validated by a rigorous checklist if you work alone).

* **Semantic Commit Messages:** Use a clear pattern (such as *Conventional Commits*) so that the history makes sense.

*Example:* `feat(auth): add JWT token validation on login endpoint`

---

## 7. Testing Strategy and Code Quality

To ensure the application can withstand pressure (especially if it's a system with complex business rules or API integrations), we clearly divide the testing pyramid:

* **Unit Tests:** Cover the smallest parts of the code in isolation (functions, methods, pure logic). **Minimum target:** 80% code coverage.

* **Integration Tests:** Ensure that the different modules (e.g., your API communicating with the PostgreSQL or Redis database) work well together.

**Load Tests:** Validate the system's behavior under stress (e.g., simulating 1000 simultaneous API requests using tools like Locust or K6) before any major release.


# Google Enterprise Agent System Architecture Standards

## 1. Objective & Scope
Whenever creating, modifying, or designing AI agents, you MUST strictly adhere to official Google Enterprise Agentic Design Patterns. Do not build naive, single-prompt chat scripts; design modular, state-driven agent architectures matching Google's well-architected framework blueprints.

## 2. Agent Structure & Core Principles
* **State Machine Tracking over Chat History:** Agents must track progress using explicit state-machine phases (e.g., `START`, `PROCESSING`, `REVIEW`, `COMPLETED`). Never use raw conversational chat transcripts to infer or manage application logic state.
* **Event-Driven Dormancy:** For long-running or multi-stage processes, design the architecture to allow agents to safely pause, dehydrate state, and automatically hydrate/resume via webhook triggers rather than keeping blocking processes alive.
* **Minimalist Scoping:** Keep agent instructions concise and limit tool availability. Do not provide a single agent with an unbounded set of tools; separate responsibilities into highly specialized sub-agent units.

## 3. Multi-Agent Design & Topology Patterns
When a task involves multi-step reasoning or multiple sub-agents, select and implement the matching Google orchestration pattern explicitly:

* **The Loop Pattern (Review & Critique):** Use this pattern for tasks requiring iterative refinement or self-correction (e.g., generation and validation). Code or structure a programmatic "Loop Agent" manager that repeatedly cycles through a sequence of specialized sub-agents (e.g., a *Generator* and a *Critic*) until a specific, deterministic exit condition or maximum iteration ceiling is hit. Do not use an LLM to decide when the loop ends.
* **The Coordinator Pattern (Dynamic Routing):** Use a primary coordinator agent to perform hierarchical task decomposition, dynamically routing complex user requests to specialized sub-agents based on the user's intent, and handling formal control handoffs back to the coordinator.
* **The Parallel Pattern:** Run multiple specialized sub-agents concurrently when sub-tasks can be executed independently to drastically reduce system latency, utilizing a final programmatic step to synthesize the results.
* **The Sequential Pattern:** Structure a strict "assembly line" pipeline where the output of one sub-agent feeds predictably into the next. Use this for deterministic, auditing-heavy workflows.
* **Agent-as-Tool Pattern:** Treat sub-agents as stateless tools within a parent agent's context when you need to maintain absolute control over the execution flow without full delegation.

## 4. Reference Material
Always cross-reference architecture choices against Google Cloud's official conceptual frameworks:
* [Google Cloud Architecture Center: Choose a design pattern for your agentic AI system](https://docs.cloud.google.com/architecture/choose-design-pattern-agentic-ai-system)

# Aways when comes to create agents follow the google documentations bellow

https://developers.googleblog.com/build-long-running-ai-agents-that-pause-resume-and-never-lose-context-with-adk/?utm_campaign=CDR_0xf9030db1_default_b522339477&utm_medium=external&utm_source=youtube


https://codelabs.developers.google.com/build-ai-agent-google-adk?utm_campaign=CDR_0x036db2a4_default&utm_medium=external&utm_source=youtube#5