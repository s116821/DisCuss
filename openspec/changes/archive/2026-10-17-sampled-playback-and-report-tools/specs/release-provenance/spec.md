## ADDED Requirements

### Requirement: Explicit lean quality toolchain
CI SHALL select Python 3.12 explicitly without a repository `.python-version` file. Ordinary code checks MUST NOT run the release analyzer fixture suite. Node manifests SHALL remain available for OpenSpec and semantic-release, and release fixture tests SHALL remain callable on demand. These choices MUST preserve the ordered quality, platform build and main publication gates.

#### Scenario: Ordinary pull request
- **WHEN** a pull request runs quality checks
- **THEN** Python is selected explicitly and release fixture tests are omitted while code and specification checks gate both platform builds
