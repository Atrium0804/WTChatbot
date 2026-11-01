# Python Curriculum

The ordered topic map for the Python Tutor. `SKILL.md` walks this list in order when picking the next topic: the first topic with status `new` or `recent` whose prerequisites are all `familiar` in `MASTERY.md`.

Columns: **Prereqs** are topic ids that must be `familiar` first. **Typical traps** are the gotchas most learners hit; when one fires in a session, it moves into the topic's Traps cell in `MASTERY.md` plus a learning record.

## Phase 1 - Basics: running and talking Python

| # | Topic | Prereqs | Typical traps |
|---|---|---|---|
| 1.1 | Running Python: REPL, `python file.py`, venv, pip | - | venv not activated, so packages land in the wrong interpreter; `python` vs `python3` |
| 1.2 | Variables, naming (snake_case), assignment, dynamic typing | 1.1 | reassignment silently changes the type; reusing a name as both variable and something else |
| 1.3 | Builtin types: int, float, bool, None, `type()`, conversions | 1.2 | float precision (`0.1 + 0.2`); `bool` is a subclass of `int` (`True + 1 == 2`) |
| 1.4 | Operators: arithmetic, comparison chains, `and`/`or`/`not`, `in` | 1.3 | `/` is float division, `//` floors; `&`/`|` are bitwise, not logical; chained comparisons (`1 < x < 10`) |
| 1.5 | Strings: methods, indexing, immutability, f-strings | 1.3 | strings are immutable; f-string quote nesting before Python 3.12; implicit concatenation |
| 1.6 | `print()`, `input()`, comments, docstrings | 1.2 | `input()` always returns `str`; forgetting the cast |

## Phase 2 - Constructs: control flow, functions, data, files

| # | Topic | Prereqs | Typical traps |
|---|---|---|---|
| 2.1 | Conditionals: `if`/`elif`/`else`, truthiness | 1.4 | `=` instead of `==` in a condition; truthiness of empty containers and `0` |
| 2.2 | Loops: `for`, `while`, `break`/`continue`/`else`, `range`, `enumerate`, `zip` | 2.1 | off-by-one in `range`; `for...else` runs when no `break` happened |
| 2.3 | Functions: `def`, parameters, defaults, `*args`/`**kwargs`, `return`, LEGB scope | 2.1 | mutable default arguments (`def f(x=[])`); late binding of closures over loop variables |
| 2.4 | Collections: list, tuple, dict, set; methods; membership tests | 1.3 | `[0] * 5` aliases one list; mutating a dict while iterating it |
| 2.5 | Indexing and slicing, negative indices, step | 2.4 | slice end is exclusive; `[:]` is a shallow copy, not a deep one |
| 2.6 | Comprehensions: list/dict/set, conditional expressions | 2.2, 2.4 | over-compressing hurts readability; in Python 3 the loop variable no longer leaks |
| 2.7 | Errors: `try`/`except`/`else`/`finally`, `raise`, common exception types, EAFP | 2.3 | bare `except:` swallows everything including `KeyboardInterrupt`; except clauses ordered most-specific first |
| 2.8 | Modules and imports: stdlib overview, `__name__ == "__main__"`, scripts vs modules | 2.3 | circular imports; relative paths breaking when a script is run from another directory |
| 2.9 | File I/O: `open()`, `with`, read/write, `pathlib` | 2.7 | forgetting `encoding="utf-8"`; files not closed without `with`; cwd-relative paths |

## Phase 3 - Paradigms and idioms: writing Python the Python way

| # | Topic | Prereqs | Typical traps |
|---|---|---|---|
| 3.1 | Procedural scripts: structuring a script top to bottom, `main()` | 2.3, 2.8 | everything at module level runs on import |
| 3.2 | OOP: classes, `__init__`, `self`, instance vs class attributes | 2.3, 2.4 | mutable class attributes shared across instances; forgetting `self` |
| 3.3 | Inheritance and dunders: `super()`, `__str__` vs `__repr__`, `__eq__` | 3.2 | `super()` call order in multiple inheritance; `__repr__` should be unambiguous, `__str__` readable |
| 3.4 | Functional: first-class functions, `map`/`filter`, `lambda`, `functools`, immutability | 2.3 | `lambda` in a loop closes over the variable, not the value; side effects inside `map` |
| 3.5 | Iterators and generators: `iter`/`next`, `yield`, generator expressions | 2.2, 3.4 | a generator is exhausted after one pass; `StopIteration` handling |
| 3.6 | Context managers: `with`, `__enter__`/`__exit__`, `contextlib` | 2.7, 3.2 | exceptions inside the `with` body still trigger `__exit__` - cleanup must be exception-safe |
| 3.7 | Decorators: `@decorator`, `functools.wraps`, decorator order | 2.3, 3.2 | forgetting `@wraps` erases the function's name/docstring; decorators apply bottom-up |
| 3.8 | Typing and dataclasses: type hints, `@dataclass`, `NamedTuple` | 3.2 | hints are not enforced at runtime; mutable defaults in dataclasses need `field(default_factory=...)` |
| 3.9 | Pythonic idioms: unpacking, `:=` walrus, `match` (3.10+), EAFP vs LBYL, the Zen of Python | 2.4, 2.6 | walrus scope in comprehensions; `match` is structural pattern matching, not a switch |

## Rules

- Keep the order: a topic's prereqs must be `familiar` before the topic is picked.
- Traps listed here are expectations, not history. Only traps that actually fired belong in `MASTERY.md`; do not pre-fill them.
- When the mission changes, mark out-of-scope phases in `MISSION.md` rather than editing this list.
