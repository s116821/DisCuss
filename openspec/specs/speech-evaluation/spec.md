# speech-evaluation Specification

## Purpose
Provide reproducible speech recognition and bounded-load evidence while protecting member speech and reporting the limits of synthetic measurements.

## Requirements

### Requirement: Privacy-safe measured evaluation
Speech evaluation SHALL use generated or explicitly consented fixtures and persist metrics rather than transcripts. Results MUST identify model/device/thread settings, expected and observed counts, latency, resource use and load limits. Synthetic results MUST explicitly state missing real-speaker/accent/GPU/soak coverage and cannot satisfy live Discord qualification.

#### Scenario: Deliberate overload
- **WHEN** synthetic attributed speech exceeds the admission cap
- **THEN** accepted and rejected work are measured, queue bounds hold and no member transcript is stored
