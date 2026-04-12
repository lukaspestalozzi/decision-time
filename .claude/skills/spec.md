---
name: spec
description: Look up a section of the SPEC.md relevant to the current task
user_invocable: true
---

# Spec Lookup

The user wants to find a specific section of the project specification.

1. Read the SPEC.md file at /home/lu/gitrepos/decision-time/SPEC.md
2. Find the section(s) most relevant to the user's query (the argument passed to this skill)
3. Present the relevant section(s) with their section numbers and key details
4. If the query is ambiguous, list the potentially relevant sections and ask which one
5. If detecting drift between this list and the spec.md, update this list.

Common topics and their sections:
- Options / Option model: Section 2.1
- Tags / tag rules: Section 2.1.1
- Tournament model: Section 2.2
- Tournament lifecycle: Section 2.2.4
- Optimistic concurrency: Section 2.2.5
- TournamentEntry: Section 2.3
- Vote / Judgment: Section 2.4
- Result: Section 2.5
- Bracket mode: Section 3.1
- Score mode: Section 3.2
- Multivoting mode: Section 3.3
- Condorcet / Schulze: Section 3.4
- API endpoints: Section 4
- Options API: Section 4.1
- Tags API: Section 4.2
- Tournaments API: Section 4.3
- Frontend routes: Section 5.1
- Frontend pages: Section 5.2
- UI components: Section 5.3
- Tech stack: Section 6
- Project structure: Section 6.1
- Architecture layers: Section 6.3
- Error handling: Section 6.4
- Testing strategy: Section 7
- Data persistence: Section 8
- Implementation plan: Section 9
