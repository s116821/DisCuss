# Tasks

## 1. Local speech pipeline

- [x] 1.1 Pin development receiver/runtime/model dependencies and add managed model setup/preflight; verify missing-cache behavior and local-only model loading contracts.
- [x] 1.2 Implement per-member segmentation, bounded inference queue, timestamped detection and lifecycle cleanup; verify silence, overlap, handoff, queue overflow, cancellation and calendar boundary tests.

## 2. Coordinator and Discord adapter

- [x] 2.1 Implement one-process multi-listener coordinator with Head Hunt/fixed reconciliation and health exposure; verify timed draws, idle, mode reload, multi-server/identity faults and shutdown fixtures.
- [x] 2.2 Implement primary-only notices/controls/report delivery, durable admin disable migration and privacy commands; verify command authorization/routing and migration/retry fixtures.

## 3. Runtime delivery contract

- [x] 3.1 Add CLI run/model setup/runtime doctor, privacy-safe diagnostics, operator docs and synthetic benchmark tool; verify documented offline entrypoints and setup exits.
- [x] 3.2 Run quality and cross-component offline integration checks, record evidence and explicit live/release limitations; archive in this PR after verification.

## Workflow follow-up

- Sync canonical specs and archive before opening the runtime PR.

