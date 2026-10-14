"""Find passages in a cached FDA label that mention a reaction term.

Each passage keeps the section it came from, so the classifier can cite it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .labels import SECTIONS


@dataclass(frozen=True)
class Passage:
    section: str
    index: int
    text: str


@dataclass(frozen=True)
class Mention:
    passage: Passage
    whole_word: bool


def label_passages(record: dict[str, Any]) -> list[Passage]:
    """Split a cached label record into passages from the searched sections."""
    if not record.get("found") or not record.get("response"):
        return []
    passages = []
    for label in record["response"].get("results") or []:
        for section in SECTIONS:
            value = label.get(section)
            if value is None:
                continue
            items = value if isinstance(value, list) else [value]
            for index, item in enumerate(items):
                if isinstance(item, dict):
                    item = item.get("text", "")
                text = " ".join(str(item).split())
                if text:
                    passages.append(Passage(section, index, text))
    return passages


def find_mentions(passages: list[Passage], term: str) -> list[Mention]:
    """Return passages containing the term, case-insensitively.

    Whole-word matches are marked whole_word=True. Matches inside longer words
    (for example 'nausea' inside 'nauseated') are kept but marked False.
    """
    term = " ".join(term.split())
    if not term:
        raise ValueError("reaction term is empty")
    whole = re.compile(rf"(?<!\w){re.escape(term)}(?!\w)", re.IGNORECASE)
    loose = re.compile(re.escape(term), re.IGNORECASE)
    mentions = []
    for passage in passages:
        if whole.search(passage.text):
            mentions.append(Mention(passage, whole_word=True))
        elif loose.search(passage.text):
            mentions.append(Mention(passage, whole_word=False))
    return mentions


def label_coverage(record: dict[str, Any]) -> str:
    """Describe how much label text was searched, for the rationale."""
    if not record.get("found") or not record.get("response"):
        return "No label record was available to search."
    results = record["response"].get("results") or []
    counts: dict[str, int] = {}
    for label in results:
        for section in SECTIONS:
            value = label.get(section)
            if value:
                counts[section] = counts.get(section, 0) + 1
    if not counts:
        return (
            f"Searched {len(results)} label(s), but none had a searchable section "
            f"({', '.join(SECTIONS)})."
        )
    found = ", ".join(f"{name} ({n})" for name, n in counts.items())
    return f"Searched {len(results)} label(s). Sections found, with label counts: {found}."