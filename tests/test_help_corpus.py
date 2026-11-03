"""11-D1: the assistant's app_help tool answers from the exported Help guides."""
from dora_api.features.assistant import tools
from dora_api.features.help.help_corpus import load_corpus, search_help


def test__corpus__loads_every_topic_with_entries():
    corpus = load_corpus()
    assert len(corpus) >= 10
    assert all(topic["entries"] for topic in corpus)


def test__search_help__ranks_the_matching_guide_first():
    hits = search_help("how do I back up my install")
    assert hits[0]["title"] == "Back up your install"
    assert hits[0]["topic"] == "Data and access"


def test__search_help__stopwords_alone_find_nothing():
    assert search_help("how do I") == []


def test__app_help_tool__is_a_data_tool_with_a_help_nav():
    assert tools.is_data_tool("app_help")
    assert tools.nav_for("app_help") == {"path": "/help", "label": "Open Help"}
    rows = tools.run_tool("app_help", {"topic": "price alert"})
    assert any(r["title"] == "Watch a price" for r in rows)
