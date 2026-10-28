## ADDED Requirements

### Requirement: Native application download surface
DisCuss releases SHALL upload only the Windows installer ZIP, Linux installer tarball and their SHA-256 checksum file, with provenance. The application wheel SHALL be embedded in each native bundle rather than published separately; application builds MUST NOT produce a redundant Python source distribution. Each bundle SHALL include its target OS installer. GitHub-generated source links remain available separately.

#### Scenario: Application release downloads
- **WHEN** a DisCuss release publishes after both native builds pass
- **THEN** its uploaded download assets are the two tested native bundles and their checksums, with no standalone wheel or Python source tarball

#### Scenario: Native installer consumes internal wheel
- **WHEN** an operator extracts the bundle for their operating system
- **THEN** its matching installer installs the embedded version-matching wheel and does not require a separate Python package download from the release
