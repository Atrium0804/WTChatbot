# MASTERY.md Format

`MASTERY.md` lives at the workspace root, next to `MISSION.md`. It is the per-topic mastery tracker: the single source of truth for what the user finds new, recently learnt, or familiar, and which topics carry traps. The tutor reads it at the start of every session and every `explain` run; update it only on evidence.

## Template

```md
# Python Mastery Tracker

| Topic | Status | Since | Evidence | Traps | Records |
|---|---|---|---|---|---|
| 1.4 Operators | familiar | 2026-11-01 | LR-0003 | `/` vs `//` | LR-0003 |
| 2.3 Functions | recent | 2026-11-08 | lesson 0002 | mutable default `def f(x=[])` | LR-0007 |
| 3.5 Generators | new | - | - | generator exhausts after one pass | - |
```

## Status values

- `new` - never covered with this user.
- `recent` - covered in a recent session but not yet demonstrated. These get retrieval practice (quiz warm-up) at the start of the next session.
- `familiar` - demonstrated: the user answered a quiz question correctly or completed an exercise using the topic.

## Columns

- **Topic** - the curriculum id and name from `CURRICULUM.md`. Seed one row per curriculum topic at workspace setup, all `new`.
- **Since** - date of the last status change (ISO). `-` while `new`.
- **Evidence** - what demonstrated the current status: a learning record id, a lesson number, or a quiz result.
- **Traps** - one-line gotchas that have actually fired for this user (or that the code being explained triggers). Full write-up lives in the linked learning record; do not paste long explanations here.
- **Records** - learning-record ids in `learning-records/` linked to this row (`LR-NNNN` for `NNNN-slug.md`).

## Rules

- **Evidence moves status.** Promote `new` to `recent` after covering a topic, `recent` to `familiar` only on a correct answer or completed exercise. Demote `familiar` to `recent` when the user stumbles on it in a later session.
- **Traps are first-class.** When a trap fires, add it to the Traps cell and write a learning record; cross-link both ways.
- **One row per curriculum topic.** Never delete rows; a topic that becomes irrelevant to the mission stays at its last status.
- Update **Since** on every status change.
