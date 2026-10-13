# Design

## Context

See proposal.md. The repositories have no existing package implementation. The exact reference is OnVelvetVelma main after PR #11.

## Goals / Non-Goals

Goals: reproduce the reference version chain and analyzer; enforce cross-platform quality and same-PR OpenSpec completion; build verifiable project-specific output.
Non-goals: receive audio, connect to Discord, run native startup installers, or publish a functional release from this foundation.

## Decisions

- Copy Hatchling/uv-dynamic-versioning configuration and importlib.metadata fallback, substituting distribution/module names only. Do not create an alternate classifier.
- Exercise the installed commit-analyzer with real fixture messages via Node; a lockfile pins its dependency graph. Keep semantic-release 25 and conventionalcommits 9.
- Use reusable release workflow called by main quality. Explicit RELEASE_READY and PYPI_PUBLISH_READY repository variables prevent unqualified publication and unregistered trusted publishing.
- Build from the checked-out release tag; compare wheel/sdist metadata to tag. Bundle DisCuss scaffold files without claiming native installers are ready. Later installer changes replace the scaffold route.
- CI validates OpenSpec strictly; a Python merge-readiness check rejects active changes, unfinished archives and mismatched new delta blocks. Git operations in tests and this check go through a PowerShell script with profiles loaded.
- Preserve GPL-3.0 licenses already selected by the owner. Reference tooling ancestry is credited separately.

## Risks / Trade-offs

- New repositories lack PyPI registration and live qualification → publication variables remain disabled.
- Local Windows success does not establish Linux success → run both platforms in GitHub Actions before calling foundation ready.
- Semantic-release creates tags using GITHUB_TOKEN → build/upload/publish in the same workflow rather than relying on a tag event.

## Migration Plan

Merge foundation after quality passes. Subsequent feature work uses its own completed archive. Rollback uses Git revert; no machine service or token state is changed by this PR.
