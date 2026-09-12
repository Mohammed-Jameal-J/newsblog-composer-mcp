"""Standalone connectivity check.

Two modes, matching the two ways into the pipeline:

    python -m newsblog_mcp.diagnose "Qualcomm issues Amazon warrants"
        Headline mode. Runs verify_news. Give it words from a REAL published
        article title - it checks whether independent publishers carried that
        exact story.

    python -m newsblog_mcp.diagnose --topic "AI"
        Topic mode. Runs find_stories. Give it a subject, not a sentence - it
        finds what was actually reported and groups it into stories.

Runs outside MCP so you can see which search providers reach the network from
your machine. Every step prints as it happens, so a slow or blocked provider is
visible rather than looking like a hang.
"""
from __future__ import annotations

import json
import sys
import time

from .config import CONFIG
from .paths import describe as describe_paths
from .providers.search import build_providers
from .tools.stories import find_stories
from .tools.verify import verify_news

PLACEHOLDERS = {
    "a headline from today", "any real headline from this week",
    "a headline you saw in the news today", "your test headline here",
    "some headline", "test", "title",
}


def _say(*parts: object) -> None:
    print(*parts, flush=True)


def _usage_warning(query: str) -> bool:
    if query.strip().lower() in PLACEHOLDERS:
        _say("\n" + "!" * 72)
        _say("That is placeholder text, not a real query.")
        _say("")
        _say("  For headline mode, paste words from an article title that actually")
        _say("  ran, e.g.:")
        _say('    python -m newsblog_mcp.diagnose "Qualcomm issues Amazon warrants"')
        _say("")
        _say("  For topic mode, give a subject rather than a sentence:")
        _say('    python -m newsblog_mcp.diagnose --topic "AI"')
        _say("!" * 72)
        return True
    if len(query.split()) <= 2:
        _say(f"\nNote: {query!r} is short enough to read as a topic rather than a "
             f"headline.\nIf you meant a topic, re-run with --topic {query!r}.")
    return False


def _probe_providers(query: str) -> int:
    providers = build_providers(CONFIG)
    _say(f"\nTesting {len(providers)} provider(s) individually "
         f"(timeout {CONFIG.search_timeout:.0f}s each, GDELT 30s):")
    reachable = 0
    for provider in providers:
        started = time.time()
        print(f"  {provider.name:<12} ... ", end="", flush=True)
        try:
            hits = provider.search(query, limit=5)
            reachable += 1
            _say(f"OK    {len(hits)} result(s) in {time.time() - started:.1f}s")
            for hit in hits[:2]:
                _say(f"      - {hit.publisher}: {hit.title[:70]}")
        except Exception as exc:
            _say(f"FAIL  after {time.time() - started:.1f}s "
                 f"-> {type(exc).__name__}: {str(exc)[:120]}")
    return reachable


def main() -> None:
    args = sys.argv[1:]
    topic_mode = bool(args) and args[0] in ("--topic", "-t")
    if topic_mode:
        args = args[1:]
    query = args[0] if args else "artificial intelligence"

    _say("Where this install keeps its files:")
    _say(json.dumps(describe_paths(), indent=2))

    _say("\nCapabilities:")
    _say(json.dumps(CONFIG.capability_report(), indent=2))
    _usage_warning(query)

    if not _probe_providers(query):
        _say("\nNo provider reached the network. That is a firewall, proxy or VPN")
        _say("issue on this machine, not a bug in the server. Check whether your")
        _say("browser can open https://api.gdeltproject.org/api/v2/doc/doc")
        return

    if topic_mode:
        _say(f"\nTOPIC MODE - find_stories({query!r}, days=2) ...")
        started = time.time()
        result = find_stories(query, days=2, cfg=CONFIG)
        _say(f"(took {time.time() - started:.1f}s)")
        _say(f"\n{json.dumps(result['counts'], indent=2)}")
        ready = result.get("ready_to_write", [])
        if not ready:
            _say("\nNothing cleared the two-publisher bar in a 2-day window. Widen it, "
                 "or try a broader topic.")
        for n, story in enumerate(ready, 1):
            _say(f"\n{n}. {story['headline']}")
            _say(f"   {story['publisher_count']} publishers: "
                 f"{', '.join(story['publishers'][:5])}")
            _say(f"   newest article {story['age_hours']}h old, "
                 f"{len(story['fetchable_urls'])} fetchable URL(s)")
        _say("\nPass one of those headlines to verify_news, then its fetchable_urls "
             "to fetch_article_facts.")
        return

    _say(f"\nHEADLINE MODE - verify_news({query!r}) ...")
    started = time.time()
    result = verify_news(query, cfg=CONFIG)
    _say(f"(took {time.time() - started:.1f}s)\n")
    _say(json.dumps({k: v for k, v in result.items()
                     if k not in ("sources", "provider_log", "reference_candidates")},
                    indent=2))
    for ref in result.get("reference_candidates", [])[:5]:
        _say(f"  reference: {ref['publisher']} -> {ref['url'][:90]}")
    if not result["is_legit"] and not result["independent_publishers"]:
        _say("\nNothing matched. If you meant a subject rather than a specific story, "
             f"try:\n  python -m newsblog_mcp.diagnose --topic \"{query}\"")


if __name__ == "__main__":
    main()
