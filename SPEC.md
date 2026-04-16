# decision-time — Specification Document

**Version:** 0.8
**Date:** 2026-04-16

---

## 1. Overview

**decision-time** is a self-hosted decision-making tool. Users create options (tagged for organization), select them
into tournaments, and run tournament-style voting processes to arrive at a winner. It runs as a single Docker container
with a web frontend and persists data on disk.

### 1.1 Core Workflow

1. Create **Options** (things to choose between), organized with tags
2. Create a **Tournament**, select Options into it via search/browse
3. Run the Tournament (vote/judge)
4. Get a **Result** (winner + full ranking)

### 1.2 Scope (v1)

- Single user, no authentication
- Multi-ballot support for Score, Multivoting, and Condorcet modes (voter count set upfront, no identity/auth)
- Custom voter labels (e.g., "Alice", "Bob") configurable per tournament
- Single ballot for Bracket mode (group discusses each matchup together)
- Four tournament modes: Bracket, Score, Multivoting, Condorcet
- Undo/edit ballot while tournament is still active (Score, Multivote, Condorcet)
- Persistent storage via JSON files on disk
- Fully testable in CI

### 1.3 Multi-Ballot Compatibility Matrix

| Mode        | Ballots    | Completion trigger                                            |
|-------------|------------|---------------------------------------------------------------|
| Bracket     | 1 (fixed)  | Final matchup decided                                         |
| Score       | N (config) | All N ballots submitted                                       |
| Multivoting | N (config) | All N ballots submitted                                       |
| Condorcet   | N (config) | All N voters complete all pairwise matchups, Schulze computed |

### 1.4 Multi-Voter UX

Multi-ballot modes support concurrent voting from independent devices/tabs. Each voter opens the tournament URL
independently and selects their voter slot from a dropdown. Voters who have already submitted are grayed out. The engine
rejects any vote with a `voter_label` that already has a ballot on record.

Voter labels are fully customizable via the `voter_labels` config field (e.g., `["Alice", "Bob", "Carol"]`). The
tournament setup UI provides a chip input for adding voter names.

The voting URL supports a `?voter=Alice` query param to pre-select the voter slot (user can still change it). This
enables easy sharing between devices.

For Bracket mode (single ballot), the `voter_label` is hardcoded to `"default"` — assigned automatically, invisible to
the user. No voter selector is shown.

---

## 2. Domain Model

### 2.1 Option

An option is something that can be chosen. It is the atomic unit of the system.

| Field       | Type     | Required | Notes                                     |
|-------------|----------|----------|-------------------------------------------|
| id          | UUID     | auto     | Primary key                               |
| name        | string   | yes      | Display name (max 256 chars)              |
| description | string   | no       | Longer explanation (no limit)             |
| tags        | string[] | no       | Freeform tags for organization and search |
| created_at  | datetime | auto     |                                           |
| updated_at  | datetime | auto     |                                           |

- Options exist independently.
- Options are globally unique by `id`, but duplicate `name` values are allowed (different Options may share a name).
- Tags provide freeform organization: an option tagged `italian`, `short` can be found by searching for either tag. Tags
  are not entities — they are just strings on the Option.
- Deleting an Option is always safe. Active tournaments use snapshotted entries and are unaffected.

#### 2.1.1 Tag Rules

- Tags match `[a-z0-9-]+` (lowercase letters, numbers, hyphens only).
- Tags are auto-normalized on write: strip special characters, replace whitespace with hyphens, lowercase, collapse
  multiple hyphens. Example: `"Baby Name!"` → `"baby-name"`.
- Empty strings after normalization are discarded.

### 2.2 Tournament

A tournament is a decision process applied to a set of Options.

| Field               | Type              | Required | Notes                                                                                             |
|---------------------|-------------------|----------|---------------------------------------------------------------------------------------------------|
| id                  | UUID              | auto     | Primary key                                                                                       |
| name                | string            | yes      | What decision is being made (max 256 chars)                                                       |
| description         | string            | no       | Context for the decision (no limit)                                                               |
| mode                | TournamentMode    | yes      | bracket / score / multivote / condorcet. Editable in draft, frozen on activation.                 |
| status              | TournamentStatus  | auto     | draft / active / completed / cancelled                                                            |
| config              | JSON              | no       | Mode-specific configuration. Editable in draft, frozen on activation. Defaults provided per mode. |
| version             | int               | auto     | Optimistic concurrency version, incremented on every write.                                       |
| selected_option_ids | UUID[]            | auto     | Options chosen for this tournament. Editable in draft, frozen on activation. Starts empty.        |
| entries             | TournamentEntry[] | auto     | Created on activation, empty in draft                                                             |
| state               | JSON              | auto     | Mode-specific engine state                                                                        |
| votes               | Vote[]            | auto     | All submitted votes                                                                               |
| result              | Result            | auto     | Computed on completion, null otherwise                                                            |
| created_at          | datetime          | auto     |                                                                                                   |
| updated_at          | datetime          | auto     |                                                                                                   |
| completed_at        | datetime          | auto     | Set when status → completed                                                                       |

All sub-entities (entries, state, votes, result) are **embedded** in the tournament JSON file. There are no separate
files for votes or results. This keeps the tournament as a single atomic document — one read, one write, one lock.

#### 2.2.1 Tournament Creation

Only `name` and `mode` are required at creation time. Everything else uses defaults or starts empty.

```json
POST /tournaments
{
  "name": "Baby name decision",
  "mode": "bracket"
}
```

Typical stepper flow:

1. `POST /tournaments` → creates draft (version: 1)
2. `PUT /tournaments/{id}` with `{"selected_option_ids": [...], "version": 1}` → add options
3. `PUT /tournaments/{id}` with `{"config": {...}, "version": 2}` → configure
4. `POST /tournaments/{id}/activate` with `{"version": 3}` → go

#### 2.2.2 Tournament Population

In draft state, the user populates the tournament by searching/browsing Options and adding them to`selected_option_ids`.
The Tournament Setup UI provides:

- **Search by name**: case-insensitive substring match across option names and tags.
- **Filter by tag**: select a tag to narrow the pool (click to toggle).
- **Select all**: select all options in the current filtered view at once. The button shows the count of filtered
  results (e.g., "Select all (12)"). Works in combination with search and tag filters.
- **Individual toggle**: click an option to select/deselect it.
- **Remove**: remove options from the selection sidebar.

Tag searches are live — new options tagged appropriately appear immediately.

#### 2.2.3 Activation Validation

A tournament can only be activated if it has at least **2 options** in `selected_option_ids` (after removing any IDs
referencing deleted Options). This minimum applies to all modes.

#### 2.2.4 Tournament Lifecycle

```
draft → active → completed
  │                  ↑
  │                  │ (all votes/rounds done)
  └──→ cancelled     │
         ↑           │
         └───────────┘ (can cancel at any point)
```

- **draft**: Tournament created. Mode, config, and `selected_option_ids` can all still be changed. No entries exist yet
  — they are created on activation.
- **active**: Voting is in progress. Config, selected options, and entries are frozen.
- **completed**: All rounds/votes are done. Results are final.
- **cancelled**: Abandoned. Preserved for history but not actionable.

#### 2.2.5 Optimistic Concurrency

Every mutation to a tournament (`PUT` config/options, `activate`, `cancel`, `vote`) requires the client to send the
current `version`. If the version on disk has changed, the server returns `409 Conflict`. The client re-fetches and
retries. One rule, no exceptions.

#### 2.2.6 Clone

Any tournament (regardless of status) can be cloned via `POST /tournaments/{id}/clone`. This creates a new tournament in
**draft** status with the same mode, config, and `selected_option_ids`. Entries are **not** copied — they are
re-resolved from `selected_option_ids` on activation, producing fresh snapshots. Options that were deleted since the
original tournament are silently excluded during activation. Returns the full new tournament object.

#### 2.2.7 Tournament Update (Partial)

`PUT /tournaments/{id}` accepts partial updates. The client sends only the fields to change — `name`, `description`,
`mode`, `selected_option_ids`, `config`. Fields not included are left unchanged. Requires `version`.

**Mode change rule:** if `mode` is supplied and differs from the current mode, any `config` in the same request is
**ignored** and the config is reset to defaults for the new mode. Config is mode-specific (bracket enforces a single
voter; score defines score ranges; etc.), so cross-mode config values would fail validation. Clients that want to
customize the new mode's config should issue a follow-up `PUT` with only `config`. Mode changes are permitted only in
`draft` status.

### 2.3 TournamentEntry

Snapshot of an Option as it entered a Tournament. Created on activation, not on tournament creation. This decouples
tournament results from later edits to the Option.

| Field           | Type | Required | Notes                                     |
|-----------------|------|----------|-------------------------------------------|
| id              | UUID | auto     | Unique within the tournament              |
| option_id       | UUID | yes      | Ref → Option (may be dangling if deleted) |
| seed            | int  | no       | Position/seed (used by Bracket)           |
| option_snapshot | JSON | yes      | Full Option entity at time of activation  |

The `option_snapshot` contains the complete Option (id, name, description, tags, timestamps). This avoids piecemeal
field selection and ensures nothing is lost.

### 2.4 Vote / Judgment

The shape of a vote depends on the tournament mode. All modes share a common envelope:

| Field         | Type       | Required | Notes                                                                            |
|---------------|------------|----------|----------------------------------------------------------------------------------|
| id            | UUID       | auto     | Unique within the tournament                                                     |
| voter_label   | string     | yes      | e.g. "Alice" — must be unique per tournament (except Bracket which uses "default") |
| round         | int        | no       | Round number (Bracket only)                                                      |
| submitted_at  | datetime   | auto     |                                                                                  |
| payload       | JSON       | yes      | Mode-specific vote data                                                          |
| status        | VoteStatus | auto     | `active` or `superseded` (default: `active`)                                     |
| superseded_at | datetime   | auto     | Set when vote is undone, null otherwise                                          |

Votes are **append-only**. When a voter undoes their vote, the original record is marked `superseded` (not deleted) and
`superseded_at` is set. Tournament state is recomputed by replaying only `active` votes. This preserves a full audit
trail.

For Bracket mode, multiple Vote records exist (one per matchup), all with `voter_label: "default"`. For Condorcet mode,
multiple Vote records exist per voter (one per pairwise matchup). For ballot modes (Score, Multivote), one Vote per
voter.

Duplicate `voter_label` detection: the engine rejects any ballot submission where the `voter_label` already has an
active ballot on record. For Bracket, "complete" means all matchups in the tournament have been decided (since it's
always single-voter).

Payload schemas per mode are defined in Section 3.

#### 2.4.1 Undo / Edit Ballot

Voters can undo their most recent active vote while the tournament is still active (i.e., not all required votes have
been submitted yet). Once the last vote is submitted and the tournament transitions to `completed`, no further undos are
possible.

Undo behavior:

- Marks the voter's latest `active` vote as `superseded`.
- Replays all remaining `active` votes to recompute tournament state.
- The voter can then submit a new ballot.
- Controlled by the `allow_undo` config flag (default: `true`). When `false`, the undo endpoint rejects all requests.
- The frontend pre-captures the voter's previous scores/allocations before the undo call, so the re-opened ballot can
  be pre-filled for a smooth editing experience.

### 2.5 Result

| Field       | Type     | Required | Notes                                                          |
|-------------|----------|----------|----------------------------------------------------------------|
| winner_ids  | UUID[]   | yes      | Ref → TournamentEntry. Multiple if tied.                       |
| ranking     | JSON     | yes      | Ordered list of entries with scores. Ties share the same rank. |
| metadata    | JSON     | no       | Mode-specific stats                                            |
| computed_at | datetime | auto     |                                                                |

Ties are allowed. When multiple entries share the top rank, all are winners. The UI shows "It's a tie!" with the tied
options.

---

## 3. Tournament Modes

Each mode implements a common interface:

```
TournamentEngine:
  validate_config(config) → errors[]
  initialize(entries[], config) → initial_state
  get_vote_context(state, voter_label) → VoteContext
  submit_vote(state, voter_label, vote_payload) → updated_state
  is_complete(state) → bool
  compute_result(state) → Result
```

`get_vote_context` returns a tagged union:

- `{type: "bracket_matchup", entry_a, entry_b, round, round_name, match_number, matches_in_round}` — for Bracket
- `{type: "condorcet_matchup", entry_a, entry_b, matchup_number, total_matchups}` — for Condorcet
- `{type: "ballot", entries[], ballot_type: "score"|"multivote", ballots_submitted, ballots_required}` — for Score,
  Multivoting
- `{type: "already_voted"}` — when the voter has already submitted
- `{type: "completed", result}` — when the tournament is done

The frontend dispatches on `type`:

- `"bracket_matchup"` → show one matchup with round context, call `/vote` per matchup
- `"condorcet_matchup"` → show one matchup with overall progress, call `/vote` per matchup
- `"ballot"` → show full ballot form, call `/vote` once
- `"already_voted"` → show ballot summary with "Edit my ballot" option (if `allow_undo` is enabled)
- `"completed"` → show results

Both Bracket and Condorcet use a matchup-based UI but with different semantics: Bracket eliminates losers round by
round, Condorcet runs every option against every other option (round-robin). The progress indicator reflects this —
Bracket shows "Round 2, Match 1 of 2", Condorcet shows "Matchup 3 of 10".

Matchup selection is **instant** — clicking an option immediately submits the vote for that matchup (no separate confirm
step). This streamlines the experience, especially for Condorcet where voters go through many matchups.

This abstraction allows adding new modes without modifying core logic.

### 3.1 Single Elimination Bracket

**Concept:** Options are seeded into a bracket. Each round presents head-to-head matchups. Winner advances, loser is
eliminated.

**Config (all optional, defaults shown):**

```json
{
  "shuffle_seed": true,
  "third_place_match": false
}
```

**Vote payload:**

```json
{
  "matchup_id": "uuid",
  "winner_entry_id": "uuid"
}
```

**State schema:**

```json
{
  "rounds": [
    {
      "round_number": 1,
      "name": "Quarter-finals",
      "matchups": [
        {
          "matchup_id": "uuid",
          "entry_a_id": "uuid",
          "entry_b_id": "uuid",
          "winner_id": null,
          "is_bye": false
        },
        {
          "matchup_id": "uuid",
          "entry_a_id": "uuid",
          "entry_b_id": null,
          "winner_id": "uuid",
          "is_bye": true
        }
      ]
    }
  ],
  "current_round": 1
}
```

**Behavior:**

- If option count is not a power of 2, pad to next power of 2. Extra slots become byes (randomly placed since seeding is
  random).
- Seeding is always randomized in v1. Manual seeding is a v2 feature.
- Byes have `entry_b_id: null` and `winner_id` pre-set to the non-null entry.
- Each round must be fully completed before the next round begins.
- `get_vote_context` returns the first matchup in the current round with `winner_id: null`. If called from two tabs
  simultaneously, the same matchup is returned — optimistic concurrency on vote submission ensures only one write
  succeeds.
- Round names are auto-generated: "Final", "Semi-finals", "Quarter-finals", "Round of 16", etc. For non-standard
  sizes, "Round N".
- Result: full bracket tree. Ranking: winner (1st), finalist (2nd), semifinalists (tied 3rd), quarter-finalists (tied
  5th), etc.
- Ties in Bracket: only at the ranking level (e.g., both semifinal losers share 3rd place). The winner is always
  singular.

**Voters:** Single ballot. `voter_label` is hardcoded to `"default"`. No `voter_count` config.

### 3.2 Score / Rating

**Concept:** Each option is independently rated on an integer scale. Highest average score wins.

**Config (all optional, defaults shown):**

```json
{
  "min_score": 1,
  "max_score": 5,
  "voter_labels": ["Voter 1"],
  "allow_undo": true
}
```

Scores are always integers.

**Vote payload:**

```json
{
  "scores": [
    {
      "entry_id": "uuid",
      "score": 4
    },
    {
      "entry_id": "uuid",
      "score": 2
    }
  ]
}
```

**State schema:**

```json
{
  "ballots_required": 2,
  "ballots_submitted": 1,
  "votes": []
}
```

**Behavior:**

- All options are presented at once.
- Every option must be scored before submission.
- Result: options ranked by average score descending, with score distribution metadata.
- Ties are allowed — entries with equal average share the same rank.
- v1 uses simple averaging. More robust aggregation strategies are a v2 consideration.

**Voters:** One ballot per voter label. Tournament completes immediately when all ballots are submitted.

### 3.3 Multivoting

**Concept:** Voter has a fixed budget of votes to distribute across options. Can give multiple votes to one option or
spread them.

**Config (all optional, defaults shown):**

```json
{
  "total_votes": null,
  "max_per_option": null,
  "voter_labels": ["Voter 1"],
  "allow_undo": true
}
```

- `total_votes`: how many votes each voter can distribute. Default: `null` → computed as `number_of_options * 2` on
  activation.
- `max_per_option`: optional cap. `null` means no cap (all votes on one option is allowed).

**Vote payload:**

```json
{
  "allocations": [
    {
      "entry_id": "uuid",
      "votes": 4
    },
    {
      "entry_id": "uuid",
      "votes": 3
    },
    {
      "entry_id": "uuid",
      "votes": 3
    }
  ]
}
```

**State schema:**

```json
{
  "ballots_required": 2,
  "ballots_submitted": 1,
  "total_votes": 10,
  "votes": []
}
```

**Behavior:**

- Sum of allocations must equal `total_votes`.
- Options not in the payload receive 0 votes.
- Result: options ranked by total votes received descending (summed across all ballots).
- Ties are allowed — entries with equal totals share the same rank.

**Voters:** One ballot per voter label. Tournament completes immediately when all ballots are submitted.

### 3.4 Condorcet (Schulze Method)

**Concept:** Every option is compared head-to-head against every other option in a round-robin. Each voter sees one
matchup at a time and picks a winner. The pairwise results are aggregated into a matrix, and the Schulze method
determines the strongest-path winner. If a Condorcet winner exists (an option that beats all others pairwise), it is
always selected.

**Config (all optional, defaults shown):**

```json
{
  "voter_labels": ["Voter 1"],
  "allow_undo": true
}
```

**Vote payload (one per matchup per voter):**

```json
{
  "matchup_id": "uuid",
  "winner_entry_id": "uuid"
}
```

**State schema:**

```json
{
  "ballots_required": 2,
  "ballots_submitted": 0,
  "matchups": [
    {
      "matchup_id": "uuid",
      "entry_a_id": "uuid",
      "entry_b_id": "uuid"
    }
  ],
  "voter_matchup_orders": {
    "Alice": [
      "matchup_id_7",
      "matchup_id_3",
      "matchup_id_1",
      "..."
    ],
    "Bob": [
      "matchup_id_2",
      "matchup_id_5",
      "matchup_id_9",
      "..."
    ]
  },
  "voter_progress": {
    "Alice": {
      "completed_matchups": 3,
      "total_matchups": 10
    },
    "Bob": {
      "completed_matchups": 0,
      "total_matchups": 10
    }
  },
  "votes": []
}
```

**Behavior:**

- For N options, each voter completes N*(N-1)/2 pairwise matchups.
- Matchup orders are pre-generated and randomized per voter on activation (seeded RNG for determinism and testability).
  Stored in `voter_matchup_orders`.
- The UI presents one matchup at a time (type `condorcet_matchup`). Progress shows "Matchup 3 of 10."
- A voter submits one vote per matchup (multiple `/vote` calls per voter).
- A voter is "complete" when all their pairwise matchups are decided.
- The tournament is complete when all voters have finished all matchups.
- On completion, votes are aggregated into a pairwise matrix and the Schulze method computes the ranking.
- The Schulze method is implemented from scratch (~50 lines, Floyd-Warshall variant for strongest paths). No external
  library dependency.
- The Schulze method finds the strongest path between every pair of options, producing a complete ordering.
- If a Condorcet winner exists, it is guaranteed to be ranked first.
- Ties are possible if the strongest paths between two options are equal in both directions. Multiple winners are
  reported.
- Result includes the pairwise matrix and Schulze path strengths as metadata.

**Voters:** One ballot per voter label. Multiple voters vote concurrently, each working through their own set of
matchups independently. Tournament completes immediately when all voters finish all matchups.

---

## 4. API Design

Base URL: `/api/v1`

The `/v1` prefix is a convention for good practice. No backward compatibility guarantees are made.

All error responses use a consistent envelope:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Human-readable description"
  }
}
```

Standard error codes: `NOT_FOUND`, `VALIDATION_ERROR`, `INVALID_STATE` (e.g., voting on a draft tournament),`CONFLICT` (
optimistic concurrency version mismatch), `INTERNAL_ERROR`.

### 4.1 Options

| Method | Path          | Description                          | Response                     |
|--------|---------------|--------------------------------------|------------------------------|
| GET    | /options      | List all, with search/filter         | 200: Option[]                |
| POST   | /options      | Create option                        | 201: Option                  |
| POST   | /options/bulk | Create many from JSON array of names | 201: Option[] (created only) |
| GET    | /options/{id} | Get one                              | 200: Option                  |
| PUT    | /options/{id} | Update                               | 200: Option                  |
| PATCH  | /options/bulk | Bulk add/remove tags                 | 200: Option[]                |
| DELETE | /options/{id} | Delete (always safe)                 | 204                          |

**Query params for GET /options:**

- `q`: case-insensitive substring match on name.
- `tags_all`: comma-separated. Options must have ALL listed tags (AND logic).
- `tags_any`: comma-separated. Options must have at least one listed tag (OR logic).
- Both can be combined: `tags_all=short&tags_any=italian,german` → must be short AND (Italian OR German).

**Bulk import (`POST /options/bulk`):**

```json
{
  "names": [
    "Luna",
    "Mira",
    "Nova"
  ],
  "tags": [
    "baby-name",
    "italian"
  ]
}
```

- `tags` is optional. When provided, applied to all created options.
- Blank/whitespace-only names are skipped.
- Leading and trailing whitespace is trimmed.
- Names that match an existing Option (exact match after trim) are skipped.
- Duplicates within the request are also deduplicated.
- Response: array of newly created Options only.

**Bulk tag update (`PATCH /options/bulk`):**

```json
{
  "option_ids": [
    "uuid",
    "uuid"
  ],
  "add_tags": [
    "italian"
  ],
  "remove_tags": [
    "german"
  ]
}
```

- Additive/subtractive — does not replace existing tags, only adds or removes specified ones.
- Tags are auto-normalized per tag rules (Section 2.1.1).
- Response: array of updated Options.

### 4.2 Tags

| Method | Path  | Description          | Response      |
|--------|-------|----------------------|---------------|
| GET    | /tags | List all tags in use | 200: string[] |

Returns a deduplicated, sorted list of all tags across all Options. No CRUD — tags are created/deleted implicitly by
editing Options. Scans all option files on each call (acceptable for v1 scale; in-memory caching is a v2 consideration).

### 4.3 Tournaments

| Method | Path                                         | Description                                                    | Response          |
|--------|----------------------------------------------|----------------------------------------------------------------|-------------------|
| GET    | /tournaments                                 | List all, filter by status                                     | 200: Tournament[] |
| POST   | /tournaments                                 | Create (status=draft).                                         | 201: Tournament   |
| GET    | /tournaments/{id}                            | Get full tournament with state                                 | 200: Tournament   |
| PUT    | /tournaments/{id}                            | Partial update (draft only). Requires `version`.               | 200: Tournament   |
| DELETE | /tournaments/{id}                            | Delete tournament                                              | 204               |
| POST   | /tournaments/{id}/activate                   | Validate (≥2 options), snapshot, activate. Requires `version`. | 200: Tournament   |
| POST   | /tournaments/{id}/cancel                     | Cancel tournament. Requires `version`.                         | 200: Tournament   |
| POST   | /tournaments/{id}/clone                      | Clone to new draft                                             | 201: Tournament   |
| GET    | /tournaments/{id}/vote-context?voter={label} | Get current vote context for a voter                           | 200: VoteContext  |
| POST   | /tournaments/{id}/vote                       | Submit a vote. Requires `version`.                             | 200: Tournament   |
| POST   | /tournaments/{id}/undo                       | Undo latest vote for a voter. Requires `version`.              | 200: {tournament, vote_context} |
| GET    | /tournaments/{id}/result                     | Get result (completed only)                                    | 200: Result       |
| GET    | /tournaments/{id}/state                      | Get full internal state (debug)                                | 200: JSON         |

**Query params for GET /tournaments:**

- `status`: comma-separated status filter. E.g., `?status=active,draft`.

**Tournament creation payload:**

```json
{
  "name": "Baby name decision",
  "mode": "bracket",
  "description": "optional"
}
```

Only `name` and `mode` are required. Tournament starts with empty `selected_option_ids` and default config for the
chosen mode.

**Tournament update payload (partial):**

```json
{
  "version": 2,
  "selected_option_ids": [
    "uuid",
    "uuid"
  ],
  "config": {
    "voter_count": 2
  },
  "name": "Updated name",
  "description": "Updated description"
}
```

Only `version` is required. All other fields are optional — only included fields are updated.

**Optimistic concurrency:** All mutating operations on a tournament (`PUT`, `activate`, `cancel`, `vote`) require the
client to send the current `version`. If the version on disk doesn't match, the server returns `409 Conflict`.

### 4.4 Health

| Method | Path           | Description  | Response                |
|--------|----------------|--------------|-------------------------|
| GET    | /api/v1/health | Health check | 200: `{"status": "ok"}` |

Used for Docker `HEALTHCHECK` and uptime monitoring. Prometheus-style metrics may be added as the project matures.

---

## 5. Frontend Structure (Angular)

### 5.1 Routes

| Route                     | Page                | Notes                                        |
|---------------------------|---------------------|----------------------------------------------|
| `/`                       | Dashboard           | Active tournaments, recent results           |
| `/options`                | Options Management  | CRUD, search, bulk import                    |
| `/tournaments/new`        | Tournament Setup    | Stepper: mode → options → config → activate  |
| `/tournaments/:id`        | Tournament Overview | Status, config summary, links to vote/result |
| `/tournaments/:id/vote`   | Voting UI           | `?voter=Voter+2` pre-selects slot            |
| `/tournaments/:id/result` | Results             | Winner, ranking, visualizations              |
| `/random`                 | Quick Pick          | Random decision from existing options        |

### 5.2 Pages

- **Dashboard**: Active tournaments, recent results, quick actions. Empty state: "Create your first tournament" CTA.
- **Options**: CRUD for options. Search/filter by name and tag. Bulk import (paste textarea, split by newlines, POST as
  JSON). Bulk tag management (select multiple, add/remove tags). Tag input fields provide autocomplete suggestions from
  existing tags. Empty state: "Add options to get started."
- **Tournament Setup**: Angular Material Stepper — Step 1: Name + pick mode. Step 2: Select options (search by name/tag,
  bulk add, drag-and-drop). Step 3: Configure mode-specific settings (including voter count for multi-ballot modes).
  Step 4: Review and activate.
- **Tournament Play**: Mode-specific voting UI (bracket matchup, condorcet matchup, rating cards, vote allocator).
  Dispatches on `VoteContext.type`. Voter selection dropdown for multi-ballot modes (pre-selectable via query param).
- **Tournament Result**: Winner announcement (handles ties), full ranking, mode-specific visualizations (bracket tree,
  pairwise matrix, score chart).
- **Quick Pick**: Random decision-maker. User selects from their existing option pool (same search/filter/tag UI as
  tournament setup), then triggers a cycling highlight animation that decelerates over ~3–4 seconds before revealing a
  random winner. Purely frontend — no tournament is created, no data is persisted. Fun, lightweight alternative to a
  full tournament.

### 5.3 Key UI Components

- `OptionCard` — displays an option with name, description, tags.
- `OptionSearch` — search/filter interface for finding and selecting options. Used in tournament setup and options
  management. Supports `q`, `tags_all`, `tags_any`.
- `BracketView` — visual bracket tree (SVG or canvas). Renders from bracket state schema.
- `ScoreSlider` — integer rating input for score tournaments.
- `VoteAllocator` — drag/click interface for distributing multivotes.
- `PairwiseMatrix` — visualization of Condorcet pairwise results and Schulze path strengths.
- `ResultChart` — visualization of final rankings (bar chart, bracket tree, pairwise matrix, etc.).
- `VoterSelector` — dropdown to pick voter slot, grays out submitted voters. Hidden for Bracket mode.
- `DecisionSpinner` — cycling highlight animation widget for Quick Pick. Rapidly highlights options in sequence with
  exponential deceleration, landing on a pre-chosen random winner. Respects `prefers-reduced-motion`.

---

## 6. Technology Stack

| Layer       | Choice                    | Notes                                            |
|-------------|---------------------------|--------------------------------------------------|
| Language    | Python 3.12+              | Type hints + Pydantic everywhere                 |
| Backend     | FastAPI                   | Built on Pydantic, async support                 |
| Persistence | JSON files on disk        | One file per entity, no DB needed                |
| Typing      | mypy (strict)             | Enforced in CI                                   |
| Validation  | Pydantic v2               | Request/response models, configs                 |
| Frontend    | Angular 19                | Standalone components, signals, new control flow |
| Styling     | Angular Material          | Pre-built components + custom theme              |
| Container   | Docker (single container) | Multi-stage build                                |
| Testing     | See Section 7             |                                                  |

### 6.1 Project Structure

```
decision-time/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app + lifespan + CORS
│   │   ├── schemas/             # Pydantic models (domain + API)
│   │   ├── routers/             # API route handlers
│   │   ├── services/            # Business logic
│   │   ├── engines/             # Tournament mode implementations
│   │   │   ├── base.py          # Abstract TournamentEngine
│   │   │   ├── bracket.py
│   │   │   ├── score.py
│   │   │   ├── multivote.py
│   │   │   └── condorcet.py
│   │   ├── repositories/        # JSON file persistence layer
│   │   │   ├── options.py
│   │   │   └── tournaments.py
│   │   └── config.py            # App configuration (incl. CORS)
│   ├── tests/
│   │   ├── unit/
│   │   │   └── engines/         # Engine logic tests (no I/O)
│   │   ├── integration/         # Services + real file repos (tmpdir)
│   │   └── api/                 # Full HTTP round-trip tests
│   ├── pyproject.toml
│   └── mypy.ini
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── options/         # Options feature module
│   │   │   ├── tournaments/     # Tournament feature module
│   │   │   ├── shared/          # Shared components, pipes, services
│   │   │   └── app.routes.ts
│   │   └── environments/
│   └── package.json
├── e2e/                         # Playwright end-to-end tests
├── docker-compose.yml
├── Dockerfile
├── Makefile                     # Dev commands
├── .env.example
├── SPEC.md                      # This file
└── README.md
```

### 6.2 Serialization Conventions

- **UUIDs**: v4, serialized as strings. E.g. `"550e8400-e29b-41d4-a716-446655440000"`.
- **Datetimes**: ISO 8601, always UTC, with `Z` suffix. E.g. `"2026-04-11T14:30:00Z"`.
- Pydantic v2 handles both natively with appropriate model config.
- The Angular frontend parses these as strings and converts for display as needed.

### 6.3 Architecture Layers

```
Router → Service → Repository
                 → Engine
```

- **Router**: HTTP concerns only. Parse request, call service, return response. No business logic.
- **Service**: Orchestration and validation. Calls repository for I/O, calls engine for tournament logic. Enforces
  business rules (draft-only edits, activation validation, version checks).
- **Engine**: Pure logic, no I/O. Takes state in, returns state out. Stateless.
- **Repository**: File I/O only. Read, write, delete JSON files. No base class — `OptionRepository` and
  `TournamentRepository` are independent, sharing utility functions (`read_json`, `write_json`, `list_dir`,
  `acquire_lock`).

### 6.4 Error Handling

Custom exception classes raised by services and engines:

| Exception           | HTTP Status | Error Code         | When                                          |
|---------------------|-------------|--------------------|-----------------------------------------------|
| `NotFoundError`     | 404         | `NOT_FOUND`        | Entity doesn't exist                          |
| `ValidationError`   | 422         | `VALIDATION_ERROR` | Invalid input, business rule violated         |
| `InvalidStateError` | 409         | `INVALID_STATE`    | Wrong lifecycle state (e.g., voting on draft) |
| `ConflictError`     | 409         | `CONFLICT`         | Optimistic concurrency version mismatch       |

FastAPI exception handlers at the app level catch these and map to the standard error envelope. Pydantic request
validation errors are auto-mapped via FastAPI's built-in handler (format overridden to match the envelope).

### 6.5 Logging

- Python `logging` module with human-readable output (always).
- Log level controlled by `LOG_LEVEL` env var (default: `info`).
- `TRACE` level: individual HTTP requests.
- `INFO` level: tournament state transitions (draft→active→completed), vote submissions, startup/shutdown.
- `ERROR` level: file I/O errors, unexpected exceptions.
- No sensitive data in logs.

### 6.6 Configuration

Environment variables (documented in `.env.example`):

| Variable       | Default | Description                                                                 |
|----------------|---------|-----------------------------------------------------------------------------|
| `DATA_DIR`     | `/data` | Path to data directory                                                      |
| `PORT`         | `8009`  | Server port                                                                 |
| `CORS_ORIGINS` | `*`     | Comma-separated allowed origins (dev: `*`, prod: same-origin so not needed) |
| `LOG_LEVEL`    | `info`  | Logging level (trace/debug/info/warning/error)                              |

### 6.7 Docker

Multi-stage build:

1. **Stage 1 (build-frontend)**: Node image, `npm ci`, `ng build` → static files in `dist/`.
2. **Stage 2 (production)**: Python slim image, install backend deps, copy Angular build into `static/` directory.

FastAPI serves the Angular static files directly (no Nginx — single process). Port `8009` exposed.

```
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8009"]
```

Docker Compose mounts a volume for persistence:

```yaml
volumes:
  - decision_time_data:/data
```

`HEALTHCHECK` uses `GET /api/v1/health`.

### 6.8 Dev Environment

- **Backend**: Python venv, `uv sync --extra dev`, `uvicorn app.main:app --reload --port 8010`.
- **Frontend**: `ng serve` on port 8009 with proxy config forwarding `/api/*` to `localhost:8010`.
- Developer opens `http://localhost:8009` — the same port as production. The Angular dev server handles frontend
  requests and proxies API calls to the backend on port 8010.
- No Docker required for local development.
- Documented in `README.md` with step-by-step setup instructions.

### 6.9 OpenAPI Documentation

FastAPI auto-generates OpenAPI docs, exposed at:

- `/docs` — Swagger UI (interactive)
- `/api/v1/openapi.json` — raw OpenAPI spec

Useful for frontend development and manual API testing.

---

## 7. Testing Strategy

All tests must run in CI without manual intervention. **Test-driven development (TDD)**: tests are written before
implementation.

### 7.1 Backend

| Layer       | Tool           | Scope                                | Target |
|-------------|----------------|--------------------------------------|--------|
| Unit        | pytest         | Tournament engines, pure logic       | 90%+   |
| Integration | pytest         | Services + file repos (tmpdir)       | 80%+   |
| API         | pytest + httpx | Full request/response via TestClient | 80%+   |
| Type check  | mypy           | Strict mode, zero errors             | 100%   |
| Lint        | ruff           | Formatting + lint rules              | 100%   |

**Engine tests are the most critical.** Each engine must have tests for:

- Normal flow (start to finish, single and multi-ballot where applicable)
- Edge cases: 2 options (minimum), odd numbers (3, 5, 7 for bracket byes), ties
- Invalid vote rejection (wrong entry ID, duplicate voter, out-of-range score, wrong vote sum)
- State consistency (no double-voting, no voting on completed tournament)
- Deterministic results (same input → same output)
- Optimistic concurrency conflicts (tournament repo)

**Bracket test fixtures** for common entry counts (2, 3, 4, 5, 8) documenting expected bracket structure and bye
placement will be included alongside engine implementation.

**Schulze method** must have dedicated unit tests verifying correct winner detection, cycle resolution, and tie handling
against known reference examples.

### 7.2 Frontend

| Layer | Tool       | Scope                               |
|-------|------------|-------------------------------------|
| Unit  | Jest       | Components, services, pipes         |
| E2E   | Playwright | Full user flows through the browser |
| Lint  | ESLint     | Strict TypeScript rules             |

### 7.3 CI Pipeline

```
┌─────────────┐    ┌──────────────┐    ┌──────────────┐    ┌────────────┐
│ Lint + Type  │ →  │ Backend Unit │ →  │ Frontend Unit│ →  │    E2E     │
│ Check        │    │ + Integration│    │   Tests      │    │  (Docker)  │
└─────────────┘    └──────────────┘    └──────────────┘    └────────────┘
```

Single command to run everything: `make ci` or `docker compose run --rm test`.

### 7.4 Makefile Targets

```
make dev-backend     # uvicorn with reload
make dev-frontend    # ng serve with proxy
make dev             # both in parallel
make test            # all tests (backend + frontend)
make test-backend    # pytest only
make test-frontend   # jest only
make lint            # ruff + eslint
make typecheck       # mypy
make ci              # lint + typecheck + all tests
make build           # docker build
make run             # docker run with volume mount
make clean           # remove build artifacts, __pycache__, dist/
```

---

## 8. Data Persistence

Data is stored as JSON files on disk, one file per entity.

```
/data/
  options/
    {id}.json
  tournaments/
    {id}.json          # single document: config, selected_option_ids, entries, state, votes, result
```

- Configurable data directory (default: `/data`).
- Docker volume mount for persistence: `-v decision_time_data:/data`.
- No migrations needed — schema changes are handled by adding optional fields with defaults.
- All tournament data (entries, state, votes, result) embedded in a single JSON file per tournament.
- Repositories are independent classes sharing utility functions (`read_json`, `write_json`, `list_dir`,
  `acquire_lock`) — no base class.
- **File locking** (via `filelock` library) prevents concurrent write corruption (e.g., multiple browser tabs submitting
  votes simultaneously).
- **Optimistic concurrency** on tournaments: each tournament has a `version` field. All mutating operations that
  reference a stale version are rejected with HTTP 409.
- **No cross-entity operations.** Deleting an option does not require updating any other files. Tournaments reference
  options via `selected_option_ids` in draft, but activation snapshots them into entries. Dangling IDs in
  `selected_option_ids` are silently excluded on activation.

### 8.1 Known Limitations (v1)

- **Tournament file growth:** A tournament with many options, multiple voters, and many pairwise matchups produces a
  JSON file that is fully rewritten on every vote. Acceptable at v1 scale (dozens of options, handful of voters) but may
  need optimization later.
- **No built-in backup/restore.** Data is plain JSON files — users can copy the `/data` directory. Structured
  backup/restore and data folder merging are v2 considerations.
- **Tag aggregation performance.** `GET /tags` scans all option files. Acceptable for v1; in-memory caching with
  invalidation is a v2 improvement.

---

## 9. Implementation Plan

Test-driven development throughout. Tests are written before implementation in every phase.

### Phase 0: Setup

Project folder structure, build setup, test setup. Goal: a green build without any code written yet.
Initialization of a Claude.md with coding guidelines and reasonable rules.
Initialization of useful claude skills for the development. Suggest them before adding.

### Phase 1: Foundation

Repository utilities (`read_json`, `write_json`, `list_dir`, `acquire_lock`), `OptionRepository`,`TournamentRepository`,
Pydantic schemas, app config. Verified with integration tests using tmpdir.

### Phase 2: First Mode End-to-End

Engine base interface + Bracket engine. API routes (options CRUD, tournament lifecycle). Full flow test: create
options → create tournament → add options → activate → vote all matchups → verify result. Backend only, tested via httpx
TestClient.

### Phase 3: Remaining Engines

Score, Multivoting, Condorcet engines. Each with comprehensive unit tests (including Schulze reference examples) before
implementation.

### Phase 4: Frontend Shell

Angular 19 setup, routing, Angular Material theme. API services. Options CRUD page. Tournament setup stepper (Bracket
only first).

### Phase 5: Frontend Voting + Results

Bracket voting UI and result display. Then Score, Multivote, Condorcet UIs. Voter selector component.

### Phase 6: Polish + Docker

Bulk import/tags, search/filter, Dockerfile, docker-compose, E2E tests (Playwright), CI pipeline, README.

---

## 10. Future Considerations (Not in v1)

These are explicitly out of scope but the architecture should not block them:

- **Authentication**: User accounts, shared tournaments via link.
- **Additional tournament modes**: Ranked Choice (IRV), STAR voting, Swiss system.
- **Option metadata**: Images, links, custom fields.
- **Import/export**: CSV import for options, JSON export for tournaments.
- **Tournament templates**: Save a tournament config for reuse.
- **Real-time**: WebSocket for live multi-voter tournaments.
- **Robust score aggregation**: Alternatives to simple averaging for Score mode (normalization, median, etc.).
- **Manual bracket seeding**: User-defined seed positions.
- **Backup/restore**: Structured export, import, and data folder merging.
- **Consistency repair**: CLI command to scan and fix dangling references.
- **Saved searches / smart collections**: Named tag queries that act like virtual lists.
- **In-memory tag cache**: Cache aggregated tags with invalidation on option writes.
- **Prometheus metrics**: Detailed operational metrics beyond health check.

---

## 11. Decisions Log

Preserved for traceability.

1. **Frontend styling**: Angular Material. ✅
2. **Bulk option creation**: Paste names, trim, deduplicate. JSON body with optional tags. ✅
3. **Tournament state storage**: JSON files on disk. All tournament data in one file. ✅
4. **Bracket seeding**: Random only in v1. ✅
5. **Multi-ballot support**: `voter_count` in config for Score, Multivote, Condorcet. Auto-complete when all submitted.
   ✅
6. **Minimum options per tournament**: 2 for all modes, validated on activation. ✅
7. **Bracket multi-ballot**: Not supported — single ballot, voter_label hardcoded to "default". ✅
8. **TournamentEntry snapshot**: Full Option entity (all fields). ✅
9. **Tournament mode mutability**: Editable in draft (clients may change mode via `PUT`; config resets to defaults
    on mode change). Frozen on activation. ✅
10. **Draft state semantics**: Config and selected options editable. Entries created on activation. ✅
11. **Score aggregation**: Integer scores only, simple average in v1. ✅
12. **Engine interface**: `get_vote_context` returns tagged union (bracket_matchup, condorcet_matchup, ballot,
    already_voted, completed). ✅
13. **Search**: Filtering via `GET /options` with `q`, `tags_all`, `tags_any`. ✅
14. **File concurrency**: File locking + optimistic concurrency on all tournament mutations. ✅
15. **Tournament JSON growth**: Known limitation, acceptable for v1. ✅
16. **Backup/restore**: Manual (copy `/data`). Structured approach in v2. ✅
17. **Tournament population**: Direct option selection via search/browse. ✅
18. **Tournament cloning**: Copies config + selected_option_ids, re-snapshots on activation. Returns full object. ✅
19. **Pagination**: Not needed for v1. ✅
20. **Error response schema**: Consistent envelope with `code` and `message`. ✅
21. **Multi-voter UX**: Independent devices, voter slot dropdown, engine rejects duplicate labels. Pre-select via query
    param. ✅
22. **Tie-breaking**: Ties allowed. Shared ranks. Multiple winners reported. ✅
23. **Bracket tree schema**: Concrete round/matchup structure. Byes have null entry + pre-set winner. ✅
24. **Bracket ranking**: Winner (1st), finalist (2nd), semifinalists (tied 3rd), etc. ✅
25. **Bracket bye algorithm**: Pad to power of 2, randomly place byes. ✅
26. **Votes/Result embedding**: All embedded in tournament JSON file. ✅
27. **CORS**: Configured in backend, permissive in dev, locked down in production. ✅
28. **Tournament Setup UX**: Angular Material Stepper. ✅
29. **Organization via tags**: Options organized by tags + direct selection into tournaments. ✅
30. **Option deletion**: Always safe. No cascade. Dangling IDs silently excluded on activation. ✅
31. **Tags API**: `GET /tags` returns aggregated list. Scan-based in v1, cached in v2. ✅
32. **Tag rules**: `[a-z0-9-]+`, auto-normalized on write. ✅
33. **Tag search semantics**: `tags_all` (AND) and `tags_any` (OR), combinable. ✅
34. **Name search**: Case-insensitive substring match. ✅
35. **Tournament update**: Partial update via PUT. Only version required, other fields optional. ✅
36. **Tournament creation**: Only name + mode required. Starts with empty options, default config. ✅
37. **Bulk tag management**: `PATCH /options/bulk` with add_tags / remove_tags. ✅
38. **Name limits**: 256 chars for option and tournament names. No limit on descriptions. ✅
39. **Status filter**: `GET /tournaments?status=active,draft` comma-separated OR. ✅
40. **Delete responses**: 204 No Content. ✅
41. **Activation/clone/update responses**: Return full tournament object. ✅
42. **Frontend routes**: Defined with deep-linkable voting URL + voter query param. ✅
43. **Condorcet mode**: Pairwise round-robin with Schulze resolution. Matchup-based UI (one at a time). ✅
44. **Build order**: 6 phases, backend-first, TDD throughout. ✅
45. **Dev environment**: Python venv + ng serve with proxy, no Docker for dev. ✅
46. **Dockerfile**: Multi-stage, FastAPI serves Angular static files, port 8009. ✅
47. **Environment variables**: DATA_DIR, PORT (8009), CORS_ORIGINS, LOG_LEVEL. ✅
48. **Schulze implementation**: From scratch, ~50 lines, no external dependency. ✅
49. **Condorcet matchup ordering**: Pre-generated on activation, randomized per voter, seeded RNG. ✅
50. **VoteContext subtypes**: `bracket_matchup` and `condorcet_matchup` as separate types. ✅
51. **Condorcet voter initialization**: Pre-generated on activation for all voter slots. ✅
52. **Bracket next matchup**: First matchup in current round with `winner_id: null`. ✅
53. **Angular version**: Angular 19, standalone components, signals, new control flow. ✅
54. **Frontend testing**: Jest (not Karma). ✅
55. **Serialization**: UUID v4 as strings, datetimes ISO 8601 UTC with Z suffix. ✅
56. **Repository design**: No base class. Independent repos sharing utility functions. ✅
57. **Architecture layers**: Router → Service → (Engine + Repository). ✅
58. **Error handling**: Custom exceptions mapped to HTTP by FastAPI handlers. ✅
59. **Logging**: Human-readable always, TRACE for requests, INFO for state changes, ERROR for failures. ✅
60. **Makefile**: dev, test, lint, typecheck, ci, build, run, clean targets. ✅
61. **API versioning**: `/v1` prefix, no backward compatibility guarantees. ✅
62. **Health check**: `GET /api/v1/health`. Prometheus metrics as v2 consideration. ✅
63. **OpenAPI docs**: Exposed at `/docs` and `/api/v1/openapi.json`. ✅
64. **Custom voter labels**: `voter_labels` config field replaces `voter_count`. Fully customizable names. ✅
65. **Undo / edit ballot**: Voters can undo while tournament is active. Append-only votes with `superseded` status.
    Controlled by `allow_undo` config flag. ✅
66. **Immediate tournament completion**: No cool-off period. Tournament transitions to `completed` immediately when the
    last required vote is submitted. Undo is only available while the tournament is still active. ✅
67. **Tag autocomplete**: Tag input fields in option create/edit and bulk import dialogs suggest existing tags via
    autocomplete dropdown. ✅
68. **Select all filtered**: Tournament population step includes a "Select all" button that adds all currently filtered
    options to the selection. ✅
69. **Auto-confirm matchups**: Bracket and Condorcet matchup UIs submit the vote immediately on click — no separate
    confirm button. ✅
70. **Dev server port alignment**: Frontend dev server runs on port 8009 (same as production), backend on 8010
    internally. Proxy handles API routing. ✅
71. **Quick Pick feature**: Frontend-only random decision page at `/random`. Uses existing options from the API with the
    same selection UI as tournament setup. Cycling highlight animation with deceleration for tension. No backend
    changes. No data persistence. ✅

---

## Annex A: Design History

This section provides context on how the spec evolved. It is not normative.

- **v0.1** (2026-04-11): Initial draft. SQLite persistence, Lists as organizational containers, single-voter only, four
  tournament styles.
- **v0.2** (2026-04-11): Business analyst review. Added multi-ballot support via `voter_count`, tournament cloning,
  activation validation (minimum 2 options), error response schema, optimistic concurrency. Renamed "style" to "mode."
- **v0.3** (2026-04-11): Senior engineer review. Switched from SQLite to JSON file persistence. Embedded votes/result in
  tournament file. Concrete state schemas per engine. Tagged union for `get_vote_context`. Tied winners support.
  Multi-voter UX with voter slot dropdown. Bracket tree schema defined.
- **v0.4** (2026-04-11): Removed Lists entirely. Options organized by tags instead. Tournaments populated by direct
  option selection via search/browse. Eliminated all cross-entity operations and cascade logic.
- **v0.5** (2026-04-11): Second engineer review. Added tag search semantics (`tags_all`/`tags_any`), partial tournament
  updates, bulk tag management, config defaults, tag normalization rules, frontend routes, API response types, field
  length limits.
- **v0.6** (2026-04-11): Replaced Ranked Choice (IRV) with Condorcet (Schulze method). Pairwise round-robin with
  matchup-based UI. IRV deferred to v2.
- **v0.7** (2026-04-12): Developer review. Added implementation plan (6 phases, TDD), architecture layers, error
  handling pattern, logging strategy, dev environment setup, Dockerfile details, environment variables, Makefile
  targets, serialization conventions, OpenAPI docs, health check endpoint. Angular 19, Jest, no base repository class,
  Schulze from scratch, VoteContext subtypes for bracket/condorcet.
- **v0.8** (2026-04-16): Post-implementation updates. Custom voter labels (replaces voter_count). Undo/edit ballot
  feature with append-only vote history and allow_undo config. Removed cool-off grace period — tournaments complete
  immediately on last vote. Tag autocomplete in option dialogs. "Select all" button in tournament population.
  Auto-confirm for bracket and condorcet matchups. Dev server port alignment (frontend on 8009, backend on 8010).

---

*This is a living document. Updated as decisions are made.*
