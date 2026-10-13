# calendar-reporting Specification

## Purpose
Produce fair window-specific total and scaled standings with durable scheduling, retry and overlap-safe retention.

## Requirements

### Requirement: Calendar-window rankings
Daily, ISO-weekly, monthly and yearly windows SHALL use server-local boundaries and half-open UTC ranges. Totals, per-word counts and rates MUST use the same window. Scaled eligibility SHALL default to 1800 monitored seconds per member per window; total standings MUST NOT inherit that cutoff.

#### Scenario: Daylight saving and qualification
- **WHEN** a reporting day has 23 or 25 hours or a member has under 30 monitored minutes
- **THEN** boundaries reflect actual elapsed time and only the scaled board excludes the short observation

### Requirement: Ordered bounded presentation
Both boards SHALL support descending default or ascending order with deterministic ties. Scaled rows SHALL show count, duration and cusses/hour, including qualified zero-count members. Output MUST respect message limits and prevent word/member text from creating mass mentions.

#### Scenario: Large standings
- **WHEN** a leaderboard exceeds one message's size
- **THEN** rendering produces bounded deterministic pages without losing rows

### Requirement: Durable independent scheduling
Enabled cadences SHALL queue immutable window snapshots and advance cursors transactionally, independently of voice occupancy. Defaults SHALL enable week/month/year and disable day. Empty daily reports MUST be suppressed. Retries/restarts MUST use unique period/page receipts; external lost-ack ambiguity MUST be documented.

#### Scenario: Restart at a shared boundary
- **WHEN** a restart catches up several due cadences
- **THEN** each complete window queues once in deterministic order and acknowledged pages are not resent

### Requirement: Overlap-safe bounded retention
Retirement at the largest enabled period SHALL preserve all events and exposure needed by unfinished shorter windows. Unacknowledged reports MUST block retirement. With all cadences disabled an explicit bounded retention policy SHALL apply.

#### Scenario: Week crossing the year
- **WHEN** yearly history retires while an ISO week still spans December and January
- **THEN** that unfinished week's counts and durations remain complete

### Requirement: Readable named summary reports
Standings and scheduled leaderboards SHALL show separated ranked totals and monitored-hour rates with human-readable local calendar dates. They MUST NOT include per-word breakdowns. Member names SHALL resolve at presentation; unavailable identities SHALL use neutral labels, never numeric IDs. Names MUST be escaped and bounded in UTF16 units; pagination MUST retain section context and deterministic receipts.

#### Scenario: Scheduled delivery after restart
- **WHEN** a queued snapshot is delivered after restart
- **THEN** names resolve within reserved page slots without persisting display names or shifting acknowledged page boundaries

#### Scenario: Earlier queued report
- **WHEN** an earlier ID-based report is pending
- **THEN** publication removes word rows and replaces member IDs with resolved or neutral labels while preserving receipt identity
