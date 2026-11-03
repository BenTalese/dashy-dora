"""The Help guides, as the assistant's `app_help` tool reads them (11-D1).

The guides are written once, in the SPA's `src/help/helpContent.ts`, and
exported to `help_corpus.json` beside this file; `helpCorpusExport.spec.ts`
fails when the export drifts. The model fetches only the guides a question
needs instead of carrying the whole app description in every prompt.
"""
import json
import re
from functools import lru_cache
from pathlib import Path

_CORPUS_PATH = Path(__file__).with_name("help_corpus.json")

_MAX_HITS = 5

# Words that match nearly every guide and so rank nothing.
_STOPWORDS = frozenset({
    "a", "an", "and", "are", "can", "do", "does", "for", "from", "how", "i",
    "in", "is", "it", "my", "of", "on", "or", "the", "to", "what", "where",
    "why", "with", "you", "your", "dora", "app",
})


@lru_cache(maxsize=1)
def load_corpus() -> list[dict]:
    with open(_CORPUS_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def _words(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in _STOPWORDS]


def _matches(word: str, haystack: list[str]) -> bool:
    # A shared stem is enough: "lists" finds "list", "cooking" finds "cook".
    return any(h.startswith(word) or word.startswith(h) for h in haystack if len(h) >= 3)


def search_help(query: str, limit: int = _MAX_HITS) -> list[dict]:
    """The guides that best answer `query`: a word in the title counts three
    times, in the topic name twice, anywhere else in the guide once."""
    words = [w for w in _words(query) if len(w) >= 3]
    if not words:
        return []
    scored: list[tuple[int, int, dict]] = []
    order = 0
    for topic in load_corpus():
        topic_words = _words(topic["title"])
        for entry in topic["entries"]:
            title_words = _words(entry["title"])
            body_words = _words(" ".join(
                entry.get(k) or "" for k in ("summary", "how", "note", "setting")
            ))
            score = 0
            for word in words:
                if _matches(word, title_words):
                    score += 3
                if _matches(word, topic_words):
                    score += 2
                if _matches(word, body_words):
                    score += 1
            if score:
                scored.append((score, order, {
                    "topic": topic["title"],
                    "title": entry["title"],
                    "summary": entry["summary"],
                    "how": entry.get("how"),
                    "setting": entry.get("setting"),
                    "note": entry.get("note"),
                    "path": entry.get("path") or entry.get("setting_path"),
                }))
            order += 1
    scored.sort(key=lambda s: (-s[0], s[1]))
    return [row for _, _, row in scored[:limit]]
