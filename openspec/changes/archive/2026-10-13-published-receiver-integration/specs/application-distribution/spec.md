## ADDED Requirements

### Requirement: Independent published receiver integration
The application SHALL support consuming the independently published receiver through an exact PyPI version pin and hashed runtime artifacts. Native release manifests SHALL identify that package version and installers SHALL use the corresponding locked distributions. Immutable development sources remain supported without readiness gates.

#### Scenario: Published receiver consumed by the application
- **WHEN** the runtime dependency is pinned to a published receiver version
- **THEN** the lockfile and exported runtime requirements reference its verified PyPI distributions, and native release manifests identify that version rather than a development archive
