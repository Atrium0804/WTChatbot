"""Herken gedeelde leeftijds- en categorienotaties in gebruikersberichten."""

import re

_BARE_YEAR_MESSAGE = re.compile(r"^\s*(?:19|20)\d{2}\s*[.?!]*\s*$")
_DUTCH_NUMBERS = {
    "nul": 0, "een": 1, "twee": 2, "drie": 3, "vier": 4, "vijf": 5,
    "zes": 6, "zeven": 7, "acht": 8, "negen": 9, "tien": 10, "elf": 11,
    "twaalf": 12, "dertien": 13, "veertien": 14, "vijftien": 15, "zestien": 16,
    "zeventien": 17, "achttien": 18,
}
_AGE_YEAR_PATTERNS = [
    re.compile(rf"\b(?:kind|zoon|dochter|klein(?:kind)?|neef|nicht)\s+van\s+(\d+|{'|'.join(_DUTCH_NUMBERS)})\b", re.IGNORECASE),
    re.compile(rf"\b(\d+|{'|'.join(_DUTCH_NUMBERS)})\s+jaar(?:\s+oud)?\b", re.IGNORECASE),
    re.compile(rf"\b(?:een\s+)?(\d+|{'|'.join(_DUTCH_NUMBERS)})\s*-?\s*jarige\b", re.IGNORECASE),
]
_OLD_CATEGORY_PATTERN = re.compile(
    r"\b(?:categorie(?:ën|en)?|cat\.?)\s*(\d+(?:\s*(?:,|/|&|-|\ben\b|t/m)\s*\d+)*)\b",
    re.IGNORECASE,
)
_MAX_CATEGORY_RANGE = 10
_NIEUWELING_PATTERN = re.compile(r"(?<!u17[\s-])\bnieuweling", re.IGNORECASE)
_CALENDAR_PATTERN = re.compile(
    r"\bMU(\d{1,2})\s*(?:[,/&]|\ben\b)?\s*VU(\d{1,2})\b|\b([MV])U(\d{1,2})\b",
    re.IGNORECASE,
)


def _parse_age(token: str) -> int | None:
    token = token.lower()
    if token.isdigit():
        return int(token)
    return _DUTCH_NUMBERS.get(token)


def is_bare_year_message(message: str) -> bool:
    return _BARE_YEAR_MESSAGE.match(message) is not None


def find_ages_in_years(message: str) -> list[int]:
    """Leeftijden in jaren in het bericht (#82): "kind van 6" -> [6]."""
    ages: list[int] = []
    for pattern in _AGE_YEAR_PATTERNS:
        for match in pattern.finditer(message):
            age = _parse_age(match.group(1))
            if age is not None and 0 <= age <= 18 and age not in ages:
                ages.append(age)
    return ages


def has_old_category_fragment(message: str) -> bool:
    return _OLD_CATEGORY_PATTERN.fullmatch(message) is not None


def old_category_numbers(message: str) -> list[int]:
    """Nummers achter "categorie"/"cat."; reeksen worden naar nummers uitgebreid."""
    numbers: list[int] = []
    for group in _OLD_CATEGORY_PATTERN.findall(message):
        tokens = re.findall(r"\d+|t/m|-", group)
        for index, token in enumerate(tokens):
            if not token.isdigit():
                continue
            is_range_end = index >= 2 and tokens[index - 1] in ("t/m", "-")
            start = int(tokens[index - 2]) + 1 if is_range_end else int(token)
            if int(token) - start > _MAX_CATEGORY_RANGE:
                start = int(token)
            for number in range(start, int(token) + 1):
                if number not in numbers:
                    numbers.append(number)
    return numbers


def has_nieuweling_mention(message: str) -> bool:
    return _NIEUWELING_PATTERN.search(message) is not None


def has_calendar_categories(message: str) -> bool:
    return _CALENDAR_PATTERN.search(message) is not None


def calendar_categories(message: str) -> list[tuple[int | None, int | None]]:
    """Kalenderaanduidingen als (jongens, meisjes)-U-nummers."""
    categories = []
    for boys, girls, sex, age in _CALENDAR_PATTERN.findall(message):
        if sex:
            boys, girls = (age, "") if sex.upper() == "M" else ("", age)
        categories.append(
            (int(boys) if boys else None, int(girls) if girls else None)
        )
    return categories
