"""Eval-runner: launch-gate van de MVP.

Leest eval/evalset.yaml en checkt per vraag het antwoord en de bron tegen de
verwachte waarden. Launch-gate: >= 90% correct met correcte bron; re-run na
elke Library-update. Geen live API-calls in CI.

Implementatie volgt uit wayfinder-ticket "Grilling: eval-set specificeren"
(map #2) — dit is bewust een stub.
"""

from pathlib import Path


def main() -> int:
    evalset_path = Path(__file__).parent / "evalset.yaml"
    if not evalset_path.exists():
        raise FileNotFoundError(f"evalset niet gevonden: {evalset_path}")
    raise NotImplementedError(
        "eval-runner is een stub; zie ticket 'Grilling: eval-set specificeren' (map #2)"
    )


if __name__ == "__main__":
    raise SystemExit(main())
