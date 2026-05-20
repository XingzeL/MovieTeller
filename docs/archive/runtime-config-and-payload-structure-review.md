# Runtime Config And Payload Structure Review

## Summary

Current architecture is serviceable for a small-to-medium system, but it is entering a phase where complexity is compounding.

The direction is broadly correct:

- centralized `Settings`
- workflow-level `Options`
- provider/model routing through gateway
- staged pipeline outputs persisted as JSON

The main issue is not that the design is wrong. The issue is that the first-stage design has succeeded, and the second-stage consolidation has not happened yet.

Current status:

- maintainability: medium
- readability: medium to low for newcomers
- immediate risk: manageable
- long-term risk: rising

## What Is Working Well

### 1. Centralized Settings

`Settings` is the right abstraction for:

- API keys
- provider base URLs
- ffmpeg / media tool paths
- model defaults
- general runtime defaults

This avoids config lookups being spread across the codebase.

### 2. Workflow-Level Option Objects

`FullWorkflowOptions` and `MoviePipelineOptions` separate:

- global defaults
- per-run execution choices

This is useful for:

- tests
- partial workflows
- text-only / speech-enabled / video-enabled variants

Using `replace(...)` on frozen dataclasses is explicit and safer than mutating nested dictionaries.

### 3. Gateway-Level Capability Routing

Provider selection is moving in the right direction:

- default provider for most capabilities
- TTS provider override
- model defaults by capability

This is cleaner than letting every business module know which vendor it is using.

## Main Structural Risks

### 1. Dual Track: `settings` And `options`

This is the biggest maintainability risk.

The system currently carries both:

- `settings`
- `pipeline_options` / `workflow_options`

through many layers.

This creates repeated ambiguity:

- which values are global configuration
- which values are per-run overrides
- which layer owns precedence

Typical failure modes:

- caller updates `options` but forgets related `settings`
- lower layers read from both and drift in behavior
- debugging requires tracing both objects through the call chain

This design is still workable now, but it does not scale gracefully.

### 2. Weakly Typed Runtime Payloads

The pipeline result payloads are mostly large `dict[str, object]` structures.

This is flexible and JSON-friendly, but it has real cost:

- field names rely on convention
- payload shape evolves across stages without formal type guarantees
- refactors are fragile
- spelling mistakes surface late
- IDE support is weak

This is already visible in structures like:

- `narratedSegments`
- `speech`
- `renderedVideo`
- `workflowArtifacts`
- `subtitleMerge`

As more post-processing stages are added, this becomes a larger maintenance burden.

### 3. Manual Test Scripts Carrying Production Logic

Some manual scripts are no longer just test harnesses. They are acting as real orchestration layers.

Examples of responsibilities now living in manual flow scripts:

- text-only reuse
- speech generation continuation
- subtitle merge
- transcript export
- final packaging decisions

This creates two risks:

- logic drifts away from the formal pipeline
- developers stop knowing whether the real workflow lives in `manual_tests/` or in the pipeline package

For a while this is acceptable for fast iteration. Long-term it becomes a maintenance liability.

### 4. Configuration Precedence Is Harder Than It Looks

Config merging currently involves:

- packaged defaults
- local YAML
- nested YAML blocks
- flat compatibility fields
- environment-variable overrides

This already produced subtle precedence bugs during recent work.

The system still functions, but the mental model is becoming expensive:

- where does the real value come from
- does flat override nested
- does env override packaged defaults only, or nested YAML too

This area is especially likely to keep producing "works in terminal, fails in IDE" class issues.

## Readability Assessment

### Good

Many names are intentional and descriptive:

- `workflow_options_from_settings`
- `text_only_options`
- `_synthesize_speech_from_payload`
- `build_subtitled_narration_srt`

Docstrings also help explain stage intent.

### Hard

The main readability issue is state-model complexity, not local naming.

Typical top-level variables in one flow can include:

- `settings`
- `base`
- `movie`
- `text_only_options`
- `text_payload`
- `payload`

An experienced author can track this easily. A new contributor must reconstruct:

- what is config
- what is a per-run variant
- what is a serialized intermediate
- what is the current phase result

This makes the code understandable, but not lightweight to read.

## Current Overall Judgment

This design is still viable if:

- the system remains mid-sized
- a small number of core developers maintain it
- pipeline stages do not multiply too quickly

It becomes risky if:

- more providers are added
- more post-processing stages are added
- more entrypoints are introduced
- team size grows
- multiple people modify payload shape concurrently

The architecture does not need to be replaced. It needs to be consolidated.

## Recommended Direction

### Priority 1: Introduce A Single Runtime Context

Goal:

- reduce long-lived `settings + options` duality

Recommended shape:

- one explicit immutable run context object
- contains both resolved settings and per-run execution choices
- lower layers accept one object instead of two

Benefits:

- clearer ownership
- fewer precedence mistakes
- easier debugging
- simpler call signatures

### Priority 2: Type The JSON Payload Shapes

Goal:

- formalize payload structures without losing JSON compatibility

Recommended options:

- `TypedDict` first for low-friction typing
- `pydantic` later if validation becomes important

At minimum, type these structures:

- narrated segment payload
- speech payload
- rendered video payload
- workflow artifacts payload
- subtitle merge payload

Benefits:

- safer refactors
- better IDE support
- easier onboarding
- less silent shape drift

### Priority 3: Separate Data Transform From Media Packaging

Current trend:

- subtitle merge logic
- transcript export logic
- final media packaging logic

are beginning to cluster near orchestration.

Recommended separation:

- data stage: build and transform timeline artifacts
- media stage: render audio/video/subtitle outputs from artifacts

Benefits:

- each stage is simpler
- testing is more direct
- renderers stay focused on render behavior

### Priority 4: Pull Mature Logic Out Of `manual_tests/`

If a manual script step is now part of the intended product flow, it should move into formal pipeline code.

Manual scripts should ideally remain:

- reproducible test harnesses
- debugging utilities
- wrappers around stable pipeline APIs

They should not remain the only home of production-grade orchestration logic.

### Priority 5: Simplify Config Precedence Rules

Recommended long-term rule:

- one canonical schema
- one explicit env override layer
- no long-term coexistence of equivalent flat and nested config forms unless absolutely necessary

Benefits:

- fewer subtle bugs
- easier support in terminal / IDE / CI
- lower cognitive load

## Suggested Near-Term Refactor Order

### Phase 1

- keep existing behavior stable
- define runtime context object
- type core payload structures

### Phase 2

- move manual-script orchestration steps into formal pipeline modules
- reduce direct payload mutation across stages

### Phase 3

- simplify config precedence
- remove transitional compatibility branches that are no longer needed

## Final Conclusion

The current system is not in bad shape. It is in a transitional shape.

Its strongest ideas are sound:

- centralized settings
- workflow option objects
- capability-based gateway routing

Its weakest parts are also clear:

- `settings` + `options` dual propagation
- weakly typed payload dictionaries
- production logic accumulating in manual scripts
- configuration precedence complexity

If the system continues growing, the most valuable architectural move is not a rewrite. It is consolidation:

- one runtime context
- typed payload contracts
- cleaner stage boundaries
- formal pipeline ownership of mature workflow steps

## See also

- [runtime-config-architecture.md](runtime-config-architecture.md) — diagrams and entry points after consolidation work.
- [runtime-config-dual-pass-inventory.md](runtime-config-dual-pass-inventory.md) — dual-pass boundary inventory.
