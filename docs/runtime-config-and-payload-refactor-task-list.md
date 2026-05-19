# Runtime Config And Payload Refactor Task List

## Goal

Reduce structural complexity around:

- runtime configuration propagation
- provider/model capability routing
- pipeline payload typing
- manual workflow orchestration

This list is intentionally execution-oriented. It focuses on concrete refactor tasks rather than architecture discussion.

## Refactor Principles

- preserve current behavior while tightening structure
- avoid broad rewrites
- move from implicit conventions to explicit contracts
- make each phase independently testable
- remove compatibility branches only after replacement paths are stable

## Phase 1: Stabilize Runtime Boundaries

### Task 1. Introduce `RunContext`

Create a single immutable runtime context object that contains:

- resolved `Settings`
- resolved workflow options for this run
- key derived paths when useful

Target outcome:

- lower layers stop accepting long-lived `settings + options` pairs
- call signatures become narrower and more predictable

Suggested first scope:

- `movie_pipeline`
- `narration`
- `narration_speech`
- `narration_video`

Definition of done:

- at least one full workflow path uses `RunContext`
- no new lower-level APIs are added that require both `settings` and `options`

### Task 2. Make Provider Resolution Capability-First Everywhere

Standardize all provider routing through one capability-based entrypoint.

Current target capabilities:

- narration
- polish
- tts
- embedding

Refactor tasks:

- consolidate provider selection into one small API
- remove remaining ad hoc default-provider reads where capability-specific selection is intended
- make TTS routing behavior explicit and documented

Definition of done:

- all capability routing is discoverable from one place
- tests cover capability -> provider -> adapter resolution

### Task 3. Tighten Config Precedence Rules

Refactor config merging to express explicit priority:

- env override
- local yaml
- packaged defaults

Required cleanup:

- document precedence in code comments
- reduce overlapping flat/nested interpretation paths
- keep compatibility only where still operationally necessary

Definition of done:

- one test file fully documents precedence cases
- no silent fallback logic remains unexplained

## Phase 2: Type Payload Contracts

### Task 4. Introduce Typed Payload Models

Define typed representations for workflow payload sections.

Minimum target structures:

- narrated segment payload
- speech payload
- rendered video payload
- subtitle merge payload
- workflow artifacts payload

Recommended first step:

- `TypedDict`

Possible later step:

- `pydantic` models for validation and serialization

Definition of done:

- payload assembly functions return typed payload structures
- downstream access no longer relies on raw `dict[str, object]` everywhere

### Task 5. Centralize Payload Serialization

Right now payloads are built and mutated in multiple places.

Refactor tasks:

- create dedicated serializer / mapper helpers
- keep JSON field naming in one layer
- avoid manual field copying in many modules

Definition of done:

- payload-to-JSON logic is centralized per major payload type
- stage code works with typed objects first, raw dicts second

### Task 6. Eliminate Phase-Ambiguous Variable Names

Standardize variable naming in orchestration code.

Examples:

- `text_payload`
- `speech_payload`
- `final_payload`
- `render_payload`

Avoid repeated generic names like:

- `payload`
- `base`
- `movie`

unless scope is very small and obvious.

Definition of done:

- top-level workflow functions read linearly by phase
- reviewers can infer state transitions from variable names alone

## Phase 3: Separate Artifact Transform From Rendering

### Task 7. Make Subtitle Merge A Formal Pipeline Stage

Move subtitle merge from script-style orchestration into formal pipeline behavior.

Target:

- `speech_video.json + source.srt -> final subtitle artifact`

Requirements:

- reusable API
- deterministic output
- dedicated tests
- explicit artifact metadata

Definition of done:

- subtitle merge can be invoked from formal workflow code
- manual scripts call the same API instead of owning the logic

### Task 8. Keep Renderers Focused On Packaging

Rendering modules should not grow into orchestration modules.

Refactor tasks:

- keep narration-video renderer focused on:
  - audio mixing
  - subtitle track packaging or burn-in
  - final media output
- keep text splitting, cue generation, and artifact shaping outside renderer

Definition of done:

- renderer consumes prepared inputs
- renderer does not own business interpretation of narration text

### Task 9. Standardize Final Video Subtitle Strategy

Decide and encode one explicit strategy per environment:

- soft subtitle track
- hard subtitle burn-in
- both

Do not let this remain accidental.

Refactor tasks:

- detect ffmpeg subtitle capability if hard burn-in is desired
- encode output mode in metadata
- expose final subtitle artifact path in a stable field

Definition of done:

- final video packaging mode is explicit
- output metadata tells the user what happened

## Phase 4: Pull Production Logic Out Of Manual Scripts

### Task 10. Move Mature Workflow Steps Into Core Pipeline

Candidates already acting like product logic:

- speech continuation from saved text JSON
- subtitle merge
- transcript generation
- final media packaging variants

Manual scripts should become thin wrappers around stable APIs.

Definition of done:

- manual scripts mostly perform:
  - path selection
  - toggles
  - printing artifacts
- core logic lives in importable modules

### Task 11. Standardize Workflow Artifact Outputs

Define a stable artifact model for:

- text JSON
- speech JSON
- final subtitle file
- audio dir
- final video
- transcript file

Definition of done:

- artifact paths are always emitted in a predictable structure
- scripts and services consume the same artifact schema

## Phase 5: Cleanup And Simplification

### Task 12. Remove Transitional Config Compatibility Paths

After new schema usage is stable:

- remove obsolete flat compatibility branches
- remove provider/index assumptions that no longer apply
- simplify defaults that exist only for migration

Definition of done:

- schema code expresses current architecture, not historical migrations

### Task 13. Align Python And Node Config Semantics

If both stacks consume config:

- provider routing semantics must match
- capability defaults must match
- env override behavior must match

Definition of done:

- same config produces the same intent in both runtimes

### Task 14. Add One Architecture Diagram

Create one short developer-facing diagram showing:

- Settings load
- RunContext creation
- capability routing
- pipeline stage sequence
- artifact evolution

Definition of done:

- onboarding no longer depends on reading multiple scattered comments first

## Priority Order

### Highest Priority

1. `RunContext`
2. capability-first provider resolution cleanup
3. typed payload contracts
4. subtitle merge as formal pipeline stage

### Medium Priority

5. central payload serialization
6. manual script logic migration
7. config precedence simplification
8. final video subtitle mode standardization

### Lower Priority

9. compatibility path removal
10. Python/Node semantic alignment
11. architecture diagram

## Suggested Delivery Plan

### Iteration 1

- introduce `RunContext`
- standardize capability provider resolution
- add tests for config and routing invariants

### Iteration 2

- type key payload structures
- centralize payload serialization helpers
- rename top-level orchestration variables by phase

### Iteration 3

- formalize subtitle merge stage
- move mature manual script logic into pipeline modules
- standardize artifact outputs

### Iteration 4

- simplify config precedence
- remove migration-only branches
- document architecture

## Completion Criteria

This refactor direction is successful when:

- lower-level APIs no longer routinely require both `settings` and `options`
- payload shapes are typed and IDE-discoverable
- manual scripts are wrappers, not primary workflow owners
- config precedence is explainable in a few sentences
- provider routing is capability-first and easy to trace
