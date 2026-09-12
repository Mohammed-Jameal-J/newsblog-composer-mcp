"""Offline smoke test. Run from the project root:

    python tests/smoke_test.py

Exercises everything that does not need the public internet: schema templating
and its mismatch checks, the heuristic scorer, the trademark filter, and article
extraction against a fixture served over local HTTP.
"""
from __future__ import annotations

import json
import os
import sys
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
os.environ.setdefault("NO_PROXY", "127.0.0.1,localhost")
os.environ.setdefault("no_proxy", "127.0.0.1,localhost")

from newsblog_mcp.config import CONFIG, Config              # noqa: E402
from newsblog_mcp.providers.imagegen import sanitize_prompt  # noqa: E402
from newsblog_mcp.tools.facts import fetch_article_facts     # noqa: E402
from newsblog_mcp.tools.schema import build_schema           # noqa: E402
from newsblog_mcp.tools.pack import build_publishing_pack      # noqa: E402
from newsblog_mcp.tools import profile as profile_mod          # noqa: E402
from newsblog_mcp.tools.save import save_and_present          # noqa: E402
from newsblog_mcp.tools.score import find_ai_words, score_ai_text  # noqa: E402
from newsblog_mcp.tools.seo import seo_audit, seo_keywords    # noqa: E402

PASSED, FAILED = [], []


def check(name: str, condition: bool, detail: str = "") -> None:
    (PASSED if condition else FAILED).append(name)
    print(f"  {'PASS' if condition else 'FAIL'}  {name}{'  -> ' + detail if detail else ''}")


def house_cfg() -> Config:
    """A fully configured house identity, so the schema tests exercise the real
    publishing path rather than the unconfigured defaults."""
    cfg = Config()
    cfg.site_name = "Example Media"
    cfg.site_base_url = "https://blog.example.com"
    cfg.author_name = "Test Author"
    cfg.publisher_name = "Example Media"
    cfg.publisher_url = "https://example.com"
    cfg.publisher_logo_url = "https://example.com/logo.png"
    cfg.site_timezone = "America/Chicago"
    cfg.permalink_pattern = "{base}/{yyyy}/{mm}/{slug}.html"
    cfg.body_includes_h1 = False
    cfg.cta_url = "https://example.com"
    cfg.cta_link_text = "Example Media"
    return cfg


HOUSE = house_cfg()

GOOD_ARTICLE = {
    "headline": "Regulator opens inquiry into datacentre power use",
    "description": ("The national grid regulator has opened a formal inquiry into "
                    "datacentre electricity demand after an alleged 34 percent rise."),
    "date_published": "2026-09-02T09:15:00+00:00",
    "intro": ["The regulator opened a formal inquiry on Tuesday.",
              "It follows an eighteen-month rise in demand."],
    "sections": [
        {"heading": "What happened",
         "paragraphs": ["Demand rose 34 percent in eighteen months."]},
        {"heading": "What the regulator said",
         "paragraphs": ["It wants eighteen months of meter data from operators."]},
        {"heading": "How operators responded",
         "paragraphs": ["An industry group disputed the figure."],
         "bullets": ["Can you prove where inference runs?",
                     "Is the meter data auditable?"]},
        {"heading": "What happens next",
         "paragraphs": ["The inquiry reports in March 2027."]},
    ],
    "cta": ("If your team is weighing grid exposure in its datacentre plans, "
            "Example Media can help you model it."),
}
GOOD_FAQ = [
    {"question": "Who opened the inquiry?", "answer": "The national grid regulator."},
    {"question": "When will it report?", "answer": "March 2027."},
    {"question": "How much capacity was added?", "answer": "Operators added 2.1 GW during 2025."},
    {"question": "Does this affect operators outside the region?",
     "answer": "Not directly, though the filing requirements may be copied elsewhere."},
]
GOOD_IMAGE = {"url": "https://cdn.example.com/banner.png", "alt": "Power lines at dusk"}
GOOD_REFS = [{"title": "Regulator opens inquiry", "url": "https://news.example.com/inquiry",
              "publisher": "Example News"}]


def test_schema_valid() -> None:
    print("\n[build_schema] valid input")
    out = build_schema(GOOD_ARTICLE, GOOD_FAQ, GOOD_IMAGE, GOOD_REFS, cfg=HOUSE)
    check("no validation issues", not out["validation"]["issues"],
          str(out["validation"]["issues"]))
    check("every FAQ question rendered",
          all(q["question"] in out["html_body"] for q in GOOD_FAQ))
    check("no H1 in the body (Blogger renders the title)",
          "<h1" not in out["html_body"])
    check("byline uses the configured author and an unpadded date",
          "By Test Author" in out["html_body"] and "September 2, 2026" in out["html_body"])
    check("CTA rendered as a link on the configured anchor text",
          '<a href="https://example.com"' in out["html_body"]
          and ">Example Media</a>" in out["html_body"])
    check("bullets rendered as a list", "<ul" in out["html_body"]
          and "Is the meter data auditable?" in out["html_body"])
    check("house styling applied",
          "max-width: 720px" in out["html_body"]
          and "font-size: 22px" in out["html_body"])
    check("Blogger permalink pattern used",
          out["canonical_url"]
          == "https://blog.example.com/2026/09/regulator-opens-inquiry-into-datacentre-power-use.html",
          out["canonical_url"])
    check("paste_block carries both scripts then the body",
          out["paste_block"].count("application/ld+json") == 2
          and out["paste_block"].rstrip().endswith("</div>"))
    check("image url in <img> and in schema",
          GOOD_IMAGE["url"] in out["html_body"] and GOOD_IMAGE["url"] in out["json_ld_article"])
    check("reference url in body", GOOD_REFS[0]["url"] in out["html_body"])
    check("references separate publisher and title with a plain hyphen, not an em dash",
          "Example News - Regulator opens inquiry" in out["html_body"]
          and "&mdash;" not in out["html_body"],
          str([l.strip() for l in out["html_body"].splitlines()
               if "Example News" in l][:1]))
    check("nothing in the rendered body is an em dash",
          "\u2014" not in out["html_body"])
    import json
    article_ld = json.loads(out["json_ld_article"])
    faq_ld = json.loads(out["json_ld_faq"])
    check("NewsArticle JSON-LD parses and is typed",
          article_ld["@type"] == "NewsArticle" and article_ld["headline"])
    check("image is a plain string, matching the house format",
          article_ld["image"] == GOOD_IMAGE["url"], str(article_ld["image"]))
    check("datePublished carries the site's offset, not Z",
          article_ld["datePublished"].endswith("-05:00"), article_ld["datePublished"])
    check("publisher carries url and logo",
          article_ld["publisher"]["url"] == "https://example.com"
          and article_ld["publisher"]["logo"]["url"].endswith("logo.png"))
    check("FAQPage JSON-LD parses with 4 questions",
          faq_ld["@type"] == "FAQPage" and len(faq_ld["mainEntity"]) == 4)


def test_schema_catches_mismatch() -> None:
    print("\n[build_schema] deliberately mismatched input")
    out = build_schema(GOOD_ARTICLE, GOOD_FAQ, {"url": "", "alt": ""},
                       [{"title": "made up", "url": "not-a-url"}], cfg=HOUSE)
    issues = " | ".join(out["validation"]["issues"])
    check("flags missing image", "image" in issues.lower(), issues)
    check("flags fabricated reference url", "not a real fetched URL" in issues, issues)
    check("validation.ok is False", out["validation"]["ok"] is False)


def test_scorer() -> None:
    print("\n[score_ai_text] heuristic")
    slop = (
        "In today's fast-paced world, the landscape of technology continues to evolve. "
        "Moreover, this represents a game-changing and revolutionary shift for the industry. "
        "Furthermore, it is important to note that the implications are truly significant. "
        "Ultimately, this serves as a testament to the pivotal role of cutting-edge innovation. "
        "It is not just about technology, but about people and the crucial future ahead."
    )
    human = (
        "The regulator opened the inquiry on Tuesday. It wants eighteen months of meter data.\n\n"
        "Operators added 2.1 GW last year. Three sites near Norwich now draw more power than "
        "the city itself, which is the number that got attention inside the department.\n\n"
        "Raman put it plainly: the grid cannot be planned on estimates. The report lands in "
        "March 2027."
    )
    a = score_ai_text(slop, cfg=CONFIG)
    b = score_ai_text(human, cfg=CONFIG)
    check("labelled as not a real detector", a["is_real_detector"] is False)
    check("AI-slop scores below clean copy",
          a["style_score"] < b["style_score"], f"{a['style_score']} vs {b['style_score']}")
    check("the heuristic does NOT report a human score",
          a["human_score"] is None and "not" in a["what_this_measures"].lower(),
          str(a.get("what_this_measures", ""))[:80])
    check("stock phrases flagged", any("stock AI phrase" in f for f in a["flagged_patterns"]),
          str(a["flagged_patterns"]))


def test_trademark_filter() -> None:
    print("\n[sanitize_prompt] trademark filter")
    safe, removed = sanitize_prompt(
        "A banner showing the Nvidia logo next to an iPhone running ChatGPT"
    )
    lowered = safe.lower()
    check("brand names stripped",
          not any(t in lowered for t in ("nvidia", "iphone", "chatgpt")), safe)
    check("logo request neutralised", "logo" not in lowered.split("no logos")[0], safe)
    check("terms reported", {"nvidia", "iphone", "chatgpt"} <= set(removed), str(removed))


def test_publisher_identity() -> None:
    """Aggregator redirects must not collapse many outlets into one publisher."""
    print("\n[verify_news] publisher identity behind aggregator links")
    from newsblog_mcp.providers.search import SearchHit
    from newsblog_mcp.tools import verify as verify_mod

    title = "Regulator opens inquiry into datacentre power use"
    # Distinct wordings, as three newsrooms covering one event would actually
    # write them. Identical headlines would (correctly) trip the syndication
    # check and downgrade confidence.
    wordings = [
        (0, "Reuters", "Regulator opens inquiry into datacentre power use"),
        (1, "The Guardian", "Grid watchdog to examine datacentre electricity demand"),
        (2, "Bloomberg", "Datacentre power use faces formal regulator inquiry"),
    ]
    fake = [
        SearchHit(title=wording, url=f"https://news.google.com/rss/articles/CBMi{n}",
                  publisher=name, published_date="2026-09-02T09:00:00+00:00",
                  snippet=title, provider="google_rss", fetchable=False)
        for n, name, wording in wordings
    ] + [
        SearchHit(title="Regulator opens datacentre power inquiry, seeks meter data",
                  url="https://www.reuters.com/business/inquiry",
                  publisher="reuters.com", published_date="2026-09-02T09:00:00+00:00",
                  snippet=title, provider="gdelt", fetchable=True)
    ]
    original = verify_mod.gather
    verify_mod.gather = lambda queries, cfg=None, limit=10, days=None: (fake, [
        {"provider": "stub", "query": "x", "ok": True, "count": len(fake)}])
    try:
        out = verify_mod.verify_news(title, cfg=CONFIG)
    finally:
        verify_mod.gather = original

    check("three distinct outlets counted, not one aggregator domain",
          len(out["independent_publishers"]) == 3, str(out["independent_publishers"]))
    check("google.com never appears as a publisher",
          "google.com" not in out["independent_publishers"],
          str(out["independent_publishers"]))
    check("reuters.com and Reuters counted once, not twice",
          sum("reuters" in p.lower() for p in out["independent_publishers"]) == 1,
          str(out["independent_publishers"]))
    check("verdict is legit with 3 publishers", out["is_legit"] is True
          and out["confidence"] == "high", out["reasoning"])
    check("reference_candidates only contains fetchable publisher URLs",
          [r["url"] for r in out["reference_candidates"]]
          == ["https://www.reuters.com/business/inquiry"],
          str(out["reference_candidates"]))


BING_WRAPPED = ("http://www.bing.com/news/apiclick.aspx?ref=FexRss&aid=&tid=6aa15&"
                "url=https%3a%2f%2fwww.cnbc.com%2f2026%2f08%2f26%2fnvidia-whisper.html"
                "&c=529&mkt=en-in")


def test_syndication_detection() -> None:
    """Wire copy on ten sites is one source, not ten publishers."""
    print("\n[verify_news] syndicated wire copy")
    from newsblog_mcp.providers.search import SearchHit
    from newsblog_mcp.tools import verify as verify_mod

    title = "OpenAI agents attacked RubyGems before Hugging Face incident, researchers say"

    def hit(t, pub, url):
        return SearchHit(title=t, url=url, publisher=pub,
                         published_date="2026-09-12T08:00:00+00:00", snippet="",
                         provider="stub", fetchable=True)

    wire = [hit(title, d, f"https://{d}/story")
            for d in ("bnnbloomberg.ca", "rappler.com", "abc.net.au", "ntd.com",
                      "whbl.com")]
    original = verify_mod.gather
    verify_mod.gather = lambda queries, cfg=None, limit=10, days=None: (wire, [])
    try:
        out = verify_mod.verify_news(title, cfg=CONFIG)
    finally:
        verify_mod.gather = original

    check("five domains still counted", len(out["independent_publishers"]) == 5)
    check("but flagged as syndicated", out["syndication"]["likely_syndicated"] is True,
          str(out["syndication"]))
    check("only one distinct wording found",
          out["syndication"]["distinct_wordings"] == 1)
    check("confidence downgraded from high to medium",
          out["confidence"] == "medium", out["confidence"])
    check("reasoning names the wire-copy risk",
          "wire story" in out["reasoning"] and "independently" in out["reasoning"],
          out["reasoning"][-150:])

    # Genuinely independent coverage must NOT be flagged.
    varied = [
        hit("OpenAI agents attacked RubyGems before Hugging Face incident", "reuters.com",
            "https://reuters.com/a"),
        hit("Researchers find malicious Ruby packages traced to AI agents", "wsj.com",
            "https://wsj.com/b"),
        hit("RubyGems halted signups after flood of AI-written packages", "theregister.com",
            "https://theregister.com/c"),
    ]
    verify_mod.gather = lambda queries, cfg=None, limit=10, days=None: (varied, [])
    try:
        out2 = verify_mod.verify_news(title, cfg=CONFIG)
    finally:
        verify_mod.gather = original
    check("distinct wordings are not flagged as syndicated",
          out2["syndication"]["likely_syndicated"] is False,
          str(out2["syndication"]))


def test_bing_unwrap() -> None:
    print("\n[bing_rss] redirect unwrapping")
    from newsblog_mcp.providers.search import _unwrap_bing
    out = _unwrap_bing(BING_WRAPPED)
    check("real publisher URL recovered",
          out == "https://www.cnbc.com/2026/08/26/nvidia-whisper.html", out)
    check("a plain URL is left alone",
          _unwrap_bing("https://www.reuters.com/x") == "https://www.reuters.com/x")
    check("an unwrappable bing link is returned as-is",
          _unwrap_bing("http://www.bing.com/news/apiclick.aspx?ref=x")
          == "http://www.bing.com/news/apiclick.aspx?ref=x")


def test_find_stories_clustering() -> None:
    print("\n[find_stories] clustering and ranking")
    from newsblog_mcp.providers.search import SearchHit
    from newsblog_mcp.tools import stories as stories_mod
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    recent = (now - timedelta(hours=3)).isoformat()
    older = (now - timedelta(days=5)).isoformat()  # outside a 2-day window

    def hit(title, pub, url, when):
        return SearchHit(title=title, url=url, publisher=pub, published_date=when,
                         snippet="", provider="stub", fetchable=True)

    fake = [
        hit("Regulator opens inquiry into datacentre power use", "reuters.com",
            "https://www.reuters.com/a", recent),
        hit("Regulator opens formal inquiry into datacentre power use", "bbc.co.uk",
            "https://www.bbc.co.uk/b", recent),
        hit("Grid regulator opens inquiry into datacentre power consumption",
            "theguardian.com", "https://www.theguardian.com/c", recent),
        hit("Chipmaker unveils new mobile processor line", "cnbc.com",
            "https://www.cnbc.com/d", older),
    ]
    original = stories_mod.gather
    stories_mod.gather = lambda queries, cfg=None, limit=10, days=None: (fake, [])
    try:
        out = stories_mod.find_stories("datacentres", days=2, cfg=CONFIG)
    finally:
        stories_mod.gather = original

    check("three variants of one story collapse into one",
          out["stories"][0]["publisher_count"] == 3,
          str([(s["headline"][:40], s["publisher_count"]) for s in out["stories"]]))
    check("the unrelated older story is dropped by the 2-day window",
          out["counts"]["too_old"] == 1, str(out["counts"]))
    check("corroborated story is ready_to_write",
          len(out["ready_to_write"]) == 1
          and out["ready_to_write"][0]["publisher_count"] == 3)
    check("age_hours reported", out["stories"][0]["age_hours"] is not None
          and out["stories"][0]["age_hours"] < 5,
          str(out["stories"][0]["age_hours"]))
    check("fetchable urls carried through",
          len(out["ready_to_write"][0]["fetchable_urls"]) == 3)


def test_schema_rejects_aggregator_reference() -> None:
    print("\n[build_schema] aggregator reference rejected")
    out = build_schema(GOOD_ARTICLE, GOOD_FAQ, GOOD_IMAGE,
                       [{"title": "Via Google", "url":
                         "https://news.google.com/rss/articles/CBMiabc"}], cfg=HOUSE)
    issues = " | ".join(out["validation"]["issues"])
    check("aggregator redirect flagged as an unusable reference",
          "aggregator redirect" in issues, issues[:160])


def test_fetch_facts_local() -> None:
    print("\n[fetch_article_facts] against a locally served fixture")
    directory = str(Path(__file__).resolve().parent / "fixtures")
    handler = partial(SimpleHTTPRequestHandler, directory=directory)
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        url = f"http://127.0.0.1:{port}/sample_article.html"
        out = fetch_article_facts([url, f"http://127.0.0.1:{port}/missing.html"], cfg=CONFIG)
    finally:
        server.shutdown()

    check("one URL extracted, one failure reported",
          out["summary"]["urls_extracted"] == 1 and out["summary"]["urls_failed"] == 1,
          str(out["summary"]))
    check("failure carries a reason",
          bool([r for r in out["per_url"] if not r["ok"]][0]["error"]))
    check("facts found and each carries source_url",
          out["facts"] and all(f["source_url"] for f in out["facts"]),
          f"{len(out['facts'])} facts")
    check("boilerplate excluded",
          not any("rights reserved" in f["text"].lower() or "subscribe" in f["text"].lower()
                  for f in out["facts"]))
    check("quote extracted and attributed",
          any("Raman" in q["attribution"] for q in out["quotes"]),
          str([q["attribution"] for q in out["quotes"]]))
    check("quotes stay under 15 words",
          all(len(q["text"].split()) <= 15 for q in out["quotes"]))
    check("figures picked up",
          any("34" in f["value"] for f in out["figures"]),
          str([f["value"] for f in out["figures"]][:6]))


SOURCE_TEXTS = [
    "The national grid regulator opened a formal inquiry into datacentre power use on "
    "Tuesday, saying datacentre power demand had risen 34 percent in eighteen months.",
    "Operators added 2.1 GW of new datacentre capacity during 2025. Three of the largest "
    "datacentre sites now draw more power than the city of Norwich.",
    "Datacentre power use has become the central question for grid planners, and the "
    "regulator said datacentre operators must file meter data.",
]


def test_seo_keywords() -> None:
    print("\n[seo_keywords] offline extraction")
    out = seo_keywords("Regulator opens inquiry into datacentre power use",
                       texts=SOURCE_TEXTS, include_suggestions=False, cfg=CONFIG)
    check("primary keyword is a multi-word phrase from the sources",
          " " in out["primary_keyword"] and "datacentre" in out["primary_keyword"],
          out["primary_keyword"])
    check("secondary keywords returned", len(out["secondary_keywords"]) >= 3,
          str(out["secondary_keywords"][:5]))
    check("no secondary keyword is a substring of another",
          not any(a != b and (a in b or b in a)
                  for a in out["secondary_keywords"] for b in out["secondary_keywords"]),
          str(out["secondary_keywords"]))
    check("entities extracted", bool(out["entities"]), str(out["entities"][:5]))
    check("meta description within 155 chars",
          len(out["suggested_meta_description"]) <= 155,
          str(len(out["suggested_meta_description"])))
    check("meta title within 60 chars", len(out["suggested_meta_title"]) <= 60)
    check("slug is hyphenated and lowercase",
          out["suggested_slug"] == out["suggested_slug"].lower()
          and " " not in out["suggested_slug"], out["suggested_slug"])


GOOD_HTML = """
<article><img src="https://cdn.example.com/b.png" alt="Datacentre power lines at dusk" />
<h1>Datacentre power use draws a regulator inquiry</h1>
<p>Datacentre power use is now under formal review. The national grid regulator opened
an inquiry on Tuesday after demand rose 34 percent in eighteen months, and it wants
eighteen months of meter data from every operator in the region.</p>
<h2>What the grid regulator said</h2><p>%s</p>
<h2>How datacentre operators responded</h2><p>%s</p>
<h2>What happens to new capacity next</h2><p>%s</p>
<h2>Why Norwich keeps coming up</h2><p>%s</p>
<h3>Who opened the inquiry?</h3><p>The national grid regulator did.</p>
<h3>When does it report?</h3><p>March 2027.</p>
<h3>How much capacity was added?</h3><p>Operators added 2.1 GW during 2025.</p>
<a href="https://news.example.com/a" rel="nofollow">Source one</a>
<a href="https://news.example.org/b" rel="nofollow">Source two</a>
</article>
""" % tuple(["Filler sentence about the inquiry and the regional grid. " * 14] * 4)

BAD_HTML = """
<article><img src="https://cdn.example.com/b.png" />
<h1>Some news happened</h1><h1>And more news</h1>
<p>Short body with nothing much in it at all.</p>
<h2>One heading</h2><p>Thin.</p></article>
"""


def test_seo_audit() -> None:
    print("\n[seo_audit] good vs bad draft")
    good = seo_audit(GOOD_HTML, "datacentre power use",
                     secondary_keywords=["grid regulator", "meter data", "new capacity"],
                     meta_title="Datacentre power use draws a regulator inquiry",
                     meta_description=("Datacentre power use is under formal review after "
                                       "demand rose 34 percent in eighteen months, the grid "
                                       "regulator said on Tuesday."),
                     slug="datacentre-power-use-inquiry", cfg=CONFIG)
    no_h1 = seo_audit(GOOD_HTML.replace("<h1>", "<p>").replace("</h1>", "</p>"),
                      "datacentre power use",
                      headline="Datacentre power use draws a regulator inquiry",
                      meta_title="Datacentre power use draws a regulator inquiry",
                      meta_description=("Datacentre power use is under formal review after "
                                        "demand rose 34 percent in eighteen months, the grid "
                                        "regulator said on Tuesday."),
                      slug="datacentre-power-use-inquiry", cfg=CONFIG)
    bad = seo_audit(BAD_HTML, "datacentre power use", cfg=CONFIG)
    check("good draft scores above 75", good["score"] > 75, str(good["score"]))
    check("bad draft scores below 40", bad["score"] < 40, str(bad["score"]))
    check("bad draft: duplicate H1 caught",
          any("one H1" in c["check"] for c in bad["must_fix"]),
          str([c["check"] for c in bad["must_fix"]]))
    check("bad draft: missing alt text caught",
          any("alt text" in c["check"] for c in bad["must_fix"]))
    check("bad draft: missing external links caught",
          any("external source links" in c["check"] for c in bad["must_fix"]))
    check("density reported", good["stats"]["keyword_density_pct"] > 0,
          str(good["stats"]["keyword_density_pct"]))
    check("a body with no H1 audits against the supplied headline",
          not any("H1" in c["check"] for c in no_h1["must_fix"])
          and no_h1["stats"]["h1_source"].startswith("platform"),
          str([c["check"] for c in no_h1["must_fix"]]))


def test_ai_word_detection() -> None:
    print("\n[find_ai_words] banned phrase detection")
    dirty = ("This groundbreaking deal will revolutionize the realm of enterprise AI. "
             "It is important to note that the company is at the forefront of "
             "innovation. In conclusion, only time will tell.")
    clean = ("Qualcomm issued warrants covering 25 million shares. The strike price is "
             "$161.26. Vesting depends on Amazon buying up to $60 billion of chips.")
    a, b = find_ai_words(dirty), find_ai_words(clean)
    check("banned phrases detected", not a["clean"] and a["count"] >= 5, str(a["count"]))
    check("each hit carries its sentence",
          all(h["in_sentence"] for h in a["occurrences"]))
    check("plain factual prose comes back clean", b["clean"], str(b["occurrences"]))
    dashed = find_ai_words("The rollout — which began on Tuesday — reached every tier.")
    check("em dashes block clean", not dashed["clean"]
          and dashed["em_dash_count"] == 1, str(dashed))
    check("em dash hit explains the fix",
          "comma" in dashed["occurrences"][0]["fix"])
    check("score_ai_text also reports AI-word status",
          score_ai_text(clean, cfg=CONFIG)["clean_of_ai_words"] is True)


def test_setup_gate() -> None:
    """The pipeline must refuse to run until byline and voice are answered."""
    print("\n[profile] setup gate")
    import tempfile
    from pathlib import Path as _P

    original = profile_mod.PROFILE_PATH
    profile_mod.PROFILE_PATH = _P(tempfile.mkdtemp()) / "profile.json"
    try:
        prof, blocked = profile_mod.require_profile()
        check("unconfigured: pipeline is blocked",
              prof is None and blocked["error"] == "setup_required")
        check("the refusal carries every setup question",
              [q["id"] for q in blocked["questions"]]
              == ["author_name", "tone", "company_name", "site_url",
                  "company_url", "logo_url"],
              str([q["id"] for q in blocked["questions"]]))
        required = [q["id"] for q in blocked["questions"] if q.get("required")]
        check("one domain question, required; CTA site and logo optional",
              required == ["author_name", "tone", "company_name", "site_url"],
              str(required))
        free_text = [q for q in blocked["questions"] if q["type"] == "text"]
        check("every text question is free text with a placeholder, no options",
              all(q["offer_options"] is False and "options" not in q
                  for q in free_text))
        check("required text questions carry a placeholder hint",
              all(q["placeholder"] for q in free_text if q["required"]),
              str([(q["id"], q["placeholder"]) for q in free_text]))
        check("the refusal tells the client not to suggest answers",
              "not present guessed answers" in blocked["ask_as"].lower())
        check("the refusal tells the client to ask in one interaction",
              "ONE interaction" in blocked["ask_as"]
              and "prose reply" in blocked["ask_as"])
        check("the template says what each field drives",
              all(hint in blocked["answer_template"] for hint in
                  ("schema author", "publisher", "canonical URL")),
              blocked["answer_template"])
        check("a fill-in template is supplied for the text fields",
              all(line in blocked["answer_template"]
                  for line in ("Name:", "Company name:", "Blog domain:", "Voice:")),
              blocked["answer_template"])
        check("the tone question lists every voice",
              {o["value"] for o in blocked["questions"][1]["options"]}
              == set(profile_mod.TONES))
        check("the refusal names the tool to call next",
              "set_profile" in blocked["next_tool"])

        saved = profile_mod.save_profile("Test User", "witty", "Example Media", "example.com")
        check("profile round-trips", profile_mod.load_profile()["author_name"] == "Test User"
              and saved["tone_label"] == "Funny / wry")
        check("a bare domain is normalised to https",
              saved["company_url"] == "https://example.com", saved["company_url"])
        check("blog base defaults to the company site",
              saved["blog_base_url"] == "https://example.com")
        check("logo defaults under the company site",
              saved["logo_url"] == "https://example.com/logo.png")
        check("image base derived from the blog site",
              saved["image_base_url"] == "https://example.com/images")

        split = profile_mod.save_profile("Test User", "witty", "Example Media",
                                         "https://blogs.example.com/",
                                         company_url="https://example.com")
        check("a subdomain blog keeps a separate CTA site, slashes stripped",
              split["blog_base_url"] == "https://blogs.example.com"
              and split["company_url"] == "https://example.com")
        check("one domain answer fills both when no CTA site is given",
              profile_mod.save_profile("J", "neutral", "Other Site",
                                       "othersite.com")["company_url"]
              == "https://othersite.com")

        for field, args in (("company_name", ("J", "witty", "", "example.com")),
                            ("site_url", ("J", "witty", "Example Media", "")),
                            ("site_url", ("J", "witty", "Example Media", "notaurl"))):
            try:
                profile_mod.save_profile(*args)
                check(f"missing/invalid {field} rejected", False, str(args))
            except ValueError:
                check(f"missing/invalid {field} rejected", True)

        old_shape = profile_mod.PROFILE_PATH
        old_shape.write_text('{"author_name": "X", "tone": "witty"}', encoding="utf-8")
        check("a pre-company profile re-asks the questions",
              profile_mod.load_profile() is None)
        profile_mod.save_profile("Test User", "witty", "Example Media", "example.com")
        prof, blocked = profile_mod.require_profile()
        check("configured: pipeline is unblocked", blocked is None
              and prof["tone"] == "witty")

        for bad in ("sarcastic", "", "NEUTRAL-ish"):
            try:
                profile_mod.save_profile("X", bad, "Example Media", "example.com")
                check(f"invalid tone {bad!r} rejected", False)
            except ValueError:
                check(f"invalid tone {bad!r} rejected", True)
        try:
            profile_mod.save_profile("   ", "neutral", "Example Media", "example.com")
            check("empty author rejected", False)
        except ValueError:
            check("empty author rejected", True)

        guidance = profile_mod.tone_guidance("witty")
        check("voice rules carry the facts-are-untouchable guard",
              "never changes a fact" in guidance and "drop the voice" in guidance)
        check("every tone has guidance",
              all(profile_mod.tone_guidance(k) for k in profile_mod.TONES))

        # get_profile is the first tool a client calls; it must say exactly what
        # the gate says.
        gate = profile_mod.setup_required_response()
        check("get_profile and the gate refusal carry the same questions",
              [q["id"] for q in gate["questions"]]
              == [q["id"] for q in profile_mod.setup_questions()])
        check("the setup message does not claim a stale question count",
              "two questions" not in gate["message"], gate["message"])
        check("clearing the profile re-arms the gate",
              profile_mod.clear_profile()
              and profile_mod.require_profile()[1] is not None)
    finally:
        profile_mod.PROFILE_PATH = original


def test_writer_tools() -> None:
    """The brief must not write prose, and the review must not rewrite."""
    print("\n[draft_brief / review_draft] writer coaching")
    from newsblog_mcp.tools.coach import draft_brief, review_draft

    facts = [
        {"text": "Mecka AI is nearing a valuation of about $500 million in a round "
                 "led by Sequoia Capital.", "publisher": "techcrunch.com"},
        {"text": "Mecka AI announced a $60 million Series A in June 2026.",
         "publisher": "techcrunch.com"},
    ]
    brief = draft_brief("Mecka AI nears $500M valuation", facts=facts,
                        keywords={"primary_keyword": "mecka ai",
                                  "secondary_keywords": ["training data"]},
                        cfg=CONFIG)
    # Not "does the word paragraph appear" - it does, in the instructions. The
    # real test is that no key holds article body text the writer did not write.
    body_keys = {"intro", "sections", "body", "html_body", "draft", "article",
                 "paragraphs", "prose"}
    check("the brief exposes no drafted article body",
          not (body_keys & set(brief)), str(sorted(set(brief) & body_keys)))
    longest = max((v for v in brief.values() if isinstance(v, str)), key=len)
    check("no field contains a written paragraph",
          len(longest.split()) < 60, longest[:90])
    check("the brief separates facts carrying numbers",
          len(brief["facts_with_numbers"]) == 2)
    check("the brief asks for what only the writer has",
          len(brief["what_only_you_can_add"]) >= 4)
    check("the brief says to write the sentences yourself",
          any("write the sentences yourself" in r.lower() for r in brief["rules"]))

    weak = ("In this article we will look at Mecka AI. Mecka AI raised $900 million "
            "from Andreessen last week. \"We are building the largest robotics "
            "dataset the world has ever seen and we will not stop until every robot "
            "learns from it.\" This is a game-changing moment.")
    review = review_draft(weak, facts=facts, cfg=CONFIG)
    kinds = {n["type"] for n in review["must_fix"] + review["worth_fixing"]
             + review["consider"]}
    check("a figure the facts do not support is flagged", "unsupported" in kinds,
          str(sorted(kinds)))
    check("an unattributed quote is flagged", "unattributed_quote" in kinds)
    check("an over-long quote is flagged", "long_quote" in kinds)
    check("a weak opening is flagged", "weak_opening" in kinds)
    check("stock phrasing is flagged", "stock_phrase" in kinds)
    check("the review returns no rewritten text",
          not any(k in review for k in ("rewritten", "rewritten_text", "draft",
                                        "suggestion", "replacement")),
          str(sorted(review)))
    check("the review says plainly that it did not rewrite",
          "not a rewrite" in review["note"].lower())

    clean = ("Mecka AI is nearing a valuation of about $500 million, in a round led "
             "by Sequoia Capital. The company announced a $60 million Series A in "
             "June. Terms are not final.")
    ok = review_draft(clean, facts=facts, cfg=CONFIG)
    check("a sourced, plainly written draft passes", not ok["must_fix"],
          str(ok["must_fix"]))


def test_publishing_pack() -> None:
    print("\n[build_publishing_pack] title, tags, permalink, Gemini prompt")
    pack = build_publishing_pack(
        "Regulator opens inquiry into datacentre power use",
        description="The grid regulator opened a formal inquiry into datacentre demand.",
        slug="regulator-datacentre-power-inquiry",
        keywords=["datacentre power use", "grid regulator", "meter data"],
        entities=["Norwich", "EU's AI"],
        image_concepts="power lines running to a row of server racks at dusk, "
                       "seen from an Nvidia data centre",
        canonical_url="https://blog.example.com/2026/09/x.html", cfg=HOUSE)
    check("title carried through", pack["title"].startswith("Regulator opens"))
    check("labels are short and title-cased",
          all(len(l) <= 24 and l[0].isupper() for l in pack["labels"]),
          pack["labels_line"])
    check("no label is a subset of another",
          not any(a != b and a.lower() in b.lower()
                  for a in pack["labels"] for b in pack["labels"]),
          pack["labels_line"])
    check("already-capitalised words preserved",
          "EU's" in pack["labels_line"] or "EU" in pack["labels_line"],
          pack["labels_line"])
    check("permalink slug returned", pack["permalink_slug"]
          == "regulator-datacentre-power-inquiry")
    check("suggested image URL sits under the configured blog site",
          pack["suggested_image_url"]
          == "https://blog.example.com/images/regulator-datacentre-power-inquiry-banner.jpg",
          pack["suggested_image_url"])
    prompt = pack["gemini_image_prompt"]
    check("brand name stripped from the image prompt",
          "nvidia" not in prompt.lower() and "nvidia" in pack["trademarks_removed"],
          str(pack["trademarks_removed"]))
    check("prompt states size, style and hard constraints",
          "1200x630" in prompt and "Style:" in prompt
          and "no logos" in prompt and "no text" in prompt)
    check("alt text ends on a word boundary",
          not pack["image_alt_text"].rstrip(".").endswith(("certificat", "-")),
          pack["image_alt_text"])
    check("a supplied concept is marked as supplied",
          pack["image_concept_source"] == "supplied")


def test_derived_image_concept() -> None:
    """With no image_concepts, the subject must still describe a picture.

    The old fallback used the headline, which names the story rather than
    describing a scene, and dragged figures into a prompt that forbids numbers
    in the image.
    """
    print("\n[build_publishing_pack] image concept derived from the research")
    pack = build_publishing_pack(
        "Mecka AI Nears $500M Valuation in Sequoia-Led Deal Amid Rush for Robot "
        "Training Data",
        slug="mecka-ai-sequoia-valuation",
        keywords=["robot training data", "human motion data", "egocentric capture"],
        entities=["Mecka AI", "Sequoia Capital"], cfg=HOUSE)
    subject = pack["gemini_image_prompt"].split("Subject: ")[1].split("\n")[0]

    check("derivation is declared, not silent",
          pack["image_concept_source"] == "derived"
          and "derived from the researched keywords" in pack["image_concept_note"])
    check("subject is not just the headline",
          "nears" not in subject.lower() and "valuation" not in subject.lower(),
          subject)
    check("no digits in the subject, which the constraints forbid in the image",
          not any(ch.isdigit() for ch in subject), subject)
    check("subject picked the motif matching the story",
          "humanoid" in subject.lower(), subject)
    check("researched themes carried into the subject",
          "robot training data" in subject.lower(), subject)
    check("alt text describes the picture, not the direction to the illustrator",
          "evoking" not in pack["image_alt_text"].lower(), pack["image_alt_text"])

    # Keywords describe the body; the headline is one line written to be clicked.
    # When they disagree, the body wins.
    uae = build_publishing_pack(
        "UAE revises AI data center plan after Iranian attacks, sources say",
        slug="uae", keywords=["ai data center plan", "power capacity"],
        entities=["UAE"], cfg=HOUSE)
    uae_subject = uae["gemini_image_prompt"].split("Subject: ")[1].split("\n")[0]
    check("research outranks the headline when choosing the motif",
          "server cabinets" in uae_subject.lower(), uae_subject)

    # Nothing to go on at all still has to produce a usable prompt.
    bare = build_publishing_pack("Something happened somewhere", slug="bare", cfg=HOUSE)
    bare_subject = bare["gemini_image_prompt"].split("Subject: ")[1].split("\n")[0]
    check("a bare call still yields a describable scene",
          "abstract editorial composition" in bare_subject.lower(), bare_subject)


def test_install_paths() -> None:
    """Where the server writes must not depend on where its code lives.

    Computing these from __file__ works in a checkout and silently breaks once
    the package is installed: posts land inside site-packages and the identity
    profile is deleted by `pip install --upgrade`.
    """
    print("\n[paths] data locations survive being installed")
    import os
    from newsblog_mcp import paths

    check("a checkout is recognised as a checkout",
          paths._is_source_checkout(ROOT), str(ROOT))
    check("a site-packages layout is not",
          not paths._is_source_checkout(Path("/venv/Lib/site-packages")))
    check("in a checkout, files stay beside the code",
          paths.data_dir() == ROOT, str(paths.data_dir()))
    check("profile and output hang off the data dir",
          paths.profile_path().parent == paths.data_dir()
          and paths.default_output_dir().parent == paths.data_dir())

    # The override has to win in either mode, so a user can put their posts
    # wherever they like.
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "elsewhere"
        os.environ["NEWSBLOG_DATA_DIR"] = str(target)
        try:
            check("NEWSBLOG_DATA_DIR overrides the default",
                  paths.data_dir() == target, str(paths.data_dir()))
            check("the override directory is created", target.is_dir())
        finally:
            os.environ.pop("NEWSBLOG_DATA_DIR", None)
    check("removing the override restores the checkout path",
          paths.data_dir() == ROOT, str(paths.data_dir()))

    user_dir = paths.user_data_dir()
    check("the installed-package fallback is a per-user directory",
          paths.APP_NAME in str(user_dir)
          and "site-packages" not in str(user_dir), str(user_dir))


def test_schema_seo_fields() -> None:
    print("\n[build_schema] SEO fields")
    import json
    article = dict(GOOD_ARTICLE, meta_title="Datacentre inquiry opens",
                   section="Energy", language="en")
    out = build_schema(article, GOOD_FAQ, GOOD_IMAGE, GOOD_REFS,
                       keywords=["datacentre power use", "grid regulator"], cfg=HOUSE)
    ld = json.loads(out["json_ld_article"])
    check("keywords in NewsArticle as a comma string",
          ld.get("keywords") == "datacentre power use, grid regulator",
          str(ld.get("keywords")))
    check("articleSection set", ld.get("articleSection") == "Energy")
    check("wordCount is a positive int", isinstance(ld.get("wordCount"), int)
          and ld["wordCount"] > 0, str(ld.get("wordCount")))
    check("meta block returned for save_and_present",
          out["meta"]["canonical"].startswith("http") and out["meta"]["title"]
          == "Datacentre inquiry opens", str(out["meta"]))


def _report_unmeasured() -> str:
    """The report as it reads when no detector key is configured."""
    from newsblog_mcp.tools.save import _report
    return _report("T", {"human_score": {"after": 93.8, "is_real_detector": False,
                                         "detector_used": "heuristic:local-v1",
                                         "clean_of_ai_words": True,
                                         "ai_word_count": 0}})


def test_save_page_head() -> None:
    print("\n[save_and_present] page head")
    import tempfile
    from pathlib import Path as _P
    cfg = house_cfg()
    cfg.output_dir = _P(tempfile.mkdtemp())
    out = build_schema(GOOD_ARTICLE, GOOD_FAQ, GOOD_IMAGE, GOOD_REFS,
                       keywords=["datacentre power use"], cfg=cfg)
    saved = save_and_present(slug="t", html_body=out["html_body"],
                             json_ld_article=out["json_ld_article"],
                             json_ld_faq=out["json_ld_faq"], title="A title",
                             description="A description",
                             meta={**out["meta"],
                                   "verification": {"is_legit": True, "confidence": "high",
                                                    "independent_publishers": ["reuters.com"],
                                                    "reasoning": "ok"},
                                   "human_score": {"before": 42, "after": 81,
                                                   "detector_used": "gptzero",
                                                   "is_real_detector": True},
                                   "seo": {"score": 91, "passed": 20, "total_checks": 22,
                                           "primary_keyword": "datacentre power use",
                                           "secondary_keywords": ["grid regulator"],
                                           "must_fix": []},
                                   "references": GOOD_REFS},
                             cfg=cfg)
    page = _P(saved["folder"], "index.html").read_text(encoding="utf-8")
    check("canonical link written", '<link rel="canonical"' in page
          and out["meta"]["canonical"] in page)
    check("og:image written", f'property="og:image" content="{GOOD_IMAGE["url"]}"' in page)
    check("twitter card written", 'name="twitter:card"' in page)
    check("both JSON-LD blocks in head",
          page.count('application/ld+json') == 2)
    check("all package files written",
          {_P(x).name for x in saved["paths"]} == {
              "index.html", "paste-into-blogger.html", "body.html",
              "newsarticle.jsonld", "faqpage.jsonld", "meta.json", "report.md"},
          str([_P(x).name for x in saved["paths"]]))
    paste = _P(saved["paste_file"]).read_text(encoding="utf-8")
    check("paste file starts with the NewsArticle script",
          paste.startswith('<script type="application/ld+json">')
          and '"@type": "NewsArticle"' in paste[:400])
    report = _P(saved["folder"], "report.md").read_text(encoding="utf-8")
    check("report shows the before/after human score when a detector ran",
          "**42** / 100 human" in report and "**81** / 100 human" in report
          and "+39" in report, report[:300])
    check("an unmeasured report says so instead of showing a human score",
          "Not measured" in _report_unmeasured() and "human score"
          not in _report_unmeasured().split("## SEO")[0].lower().replace(
              "no ai-detection", ""),
          _report_unmeasured().split("## SEO")[0][-260:])
    check("report carries the SEO score and references",
          "**91** / 100" in report and "news.example.com/inquiry" in report)


if __name__ == "__main__":
    test_schema_valid()
    test_schema_catches_mismatch()
    test_scorer()
    test_trademark_filter()
    test_fetch_facts_local()
    test_publisher_identity()
    test_syndication_detection()
    test_bing_unwrap()
    test_find_stories_clustering()
    test_schema_rejects_aggregator_reference()
    test_seo_keywords()
    test_ai_word_detection()
    test_setup_gate()
    test_writer_tools()
    test_publishing_pack()
    test_derived_image_concept()
    test_install_paths()
    test_seo_audit()
    test_schema_seo_fields()
    test_save_page_head()
    print(f"\n{len(PASSED)} passed, {len(FAILED)} failed")
    if FAILED:
        print("Failed:", ", ".join(FAILED))
    sys.exit(1 if FAILED else 0)
