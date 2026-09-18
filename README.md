<div align="center">

<img src="mascot-600.png" width="300" alt="NewsBlog Composer">

# NewsBlog Composer MCP

**Headline in, publishable post out.**

[![PyPI](https://img.shields.io/pypi/v/newsblog-composer-mcp)](https://pypi.org/project/newsblog-composer-mcp/)
[![Python](https://img.shields.io/pypi/pyversions/newsblog-composer-mcp)](https://pypi.org/project/newsblog-composer-mcp/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-272%20passing-brightgreen)](tests/smoke_test.py)

</div>

<!-- mcp-name: io.github.Mohammed-Jameal-J/newsblog-composer -->

Give it a news headline or a topic and it verifies the story is real, downloads
the sources, extracts the facts with attribution, mines the keywords, writes the
article, and builds the SEO, schema, banner prompt and publishing pack around it.

```
"Write me a blog post about <a headline from today>"

  verify_news          8 independent publishers, corroborated
  fetch_article_facts  facts, quotes and figures, each with its source URL
  seo_keywords         mined from the fetched text, not invented
  draft_brief          structure + facts -> the article gets written
  find_ai_words        stock phrasing flagged with the sentence it sits in
  build_publishing_pack   asks YOU which of 8 banner styles you want
  build_schema         NewsArticle + FAQPage JSON-LD, validated
  seo_audit            93/100, nothing must-fix
  save_and_present     the post, the checks, the image prompt, the files
```

## What it actually guarantees

**Two independent publishers, or it will not draft.** Wire reprints are detected,
so six outlets running one Reuters story are not mistaken for six sources, and a
wide date spread downgrades confidence rather than passing silently.

**Every fact traces to a source it fetched**, not to a model's memory. Facts,
quotes and figures carry their `source_url`, and `build_schema` rejects reference
links that are aggregator redirects rather than real publisher URLs.

**You choose the banner.** With no style picked there is no image prompt in the
result at all, and `save_and_present` refuses the package. The tool asks; it does
not decide for you.

**It will not hand you a post without the numbers.** `save_and_present` refuses
unless the SEO audit and the AI-word check have both run, so the finished post
always arrives with its scores attached.

**The prose is machine-written and the tool says so.** Without a detector API key
`score_ai_text` reports `Not measured` rather than inventing a reassuring number
— a local style score measures cliche density and sentence rhythm, which is not a
prediction of what a detector will say. If the byline is going to claim a person
wrote it, that is your call to make with your eyes open; `review_draft` exists so
the draft gets edited rather than published raw.

**It runs with zero API keys.** Every credential is an upgrade, not a
requirement. See [No keys? Start here](#no-keys-start-here).

---

## Install

### Claude Desktop — one click, no Python

1. Download `newsblog-composer-<version>.mcpb` from
   [Releases](https://github.com/Mohammed-Jameal-J/newsblog-composer-mcp/releases/latest).
2. Claude Desktop → **Settings → Extensions → Advanced settings → Install
   Extension**.
3. **Toggle the extension off and on.** On Windows the X button only minimises to
   the tray, so without this the old server keeps running.
4. **Add this line** to a Claude project's instructions, or to **Customize** so it
   applies to every chat:

   > When I ask for a blog post, an article, or a news write-up, always use the
   > NewsBlog Composer tools. Start with `write_blog_post`. Never search the web
   > and draft the article yourself.

5. Ask for a post. It asks for your byline, company and blog domain once.

**Step 4 is not optional.** A host's system prompt reads "write me a blog post"
as "search the web and make an artifact", and an MCP server's `instructions`
field cannot outrank that — there is no API for a server to claim priority.
Without the line the client answers from web search and never mentions the
extension. Naming the server in the request works for one-offs.

Extensions are **desktop only**. On mobile or the web app there is nothing to
call, and the client answers from web search without saying so.

### From PyPI

```bash
pip install newsblog-composer-mcp
```

That gives you the `newsblog-mcp` command, which speaks MCP over stdio.

### From source

```bash
git clone https://github.com/Mohammed-Jameal-J/newsblog-composer-mcp.git
cd newsblog-composer-mcp
python3 -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .
cp .env.example .env        # optional: every value in it is optional too
```

Check it reaches the network before wiring it into a client — if search is
blocked by a proxy or VPN, this is where you find out:

```bash
python -m newsblog_mcp.diagnose "a headline you saw in the news today"
```

## Connect it

### VS Code

Create `.vscode/mcp.json` in your workspace:

```json
{
  "servers": {
    "newsblog": {
      "type": "stdio",
      "command": "newsblog-mcp"
    }
  }
}
```

Reload the window, then open Chat in Agent mode — the tools appear under the
tools picker. Use the full path to `newsblog-mcp` (or to the venv's Python with
`"args": ["-m", "newsblog_mcp.server"]`) if the command is not on your PATH.

### Claude Code

`.mcp.json` in your project:

```json
{
  "mcpServers": {
    "newsblog": {
      "command": "newsblog-mcp"
    }
  }
}
```

### Claude Desktop, configured by hand

`%APPDATA%\Claude\claude_desktop_config.json` on Windows,
`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS:

```json
{
  "mcpServers": {
    "newsblog": {
      "command": "newsblog-mcp"
    }
  }
}
```

The `.mcpb` above does this for you and is the easier route.

### Anything else

Launch `newsblog-mcp` (or `python -m newsblog_mcp.server`) and speak MCP over
stdio. For a remote client, `newsblog-mcp --http` serves a streamable HTTP
endpoint — see [Publishing and connecting](#publishing-and-connecting).

### Where it keeps your files

Installed from PyPI, the server writes to your user data directory, so nothing is
lost when you upgrade:

| | |
|---|---|
| Windows | `%LOCALAPPDATA%\newsblog-composer-mcp` |
| macOS | `~/Library/Application Support/newsblog-composer-mcp` |
| Linux | `~/.local/share/newsblog-composer-mcp` |

That folder holds `profile.json` (the identity you set at first run), `output/`
(every generated post) and an optional `.env`. Set `NEWSBLOG_DATA_DIR` to put
them somewhere else. Run from a cloned checkout instead and everything stays in
the project folder, beside the code.

`python -m newsblog_mcp.diagnose` prints the exact paths for your install.

---

## Publishing and connecting

**Claude Desktop / Claude Code** run it over stdio, which is what the install
section above sets up.

**ChatGPT cannot spawn a local process**, so stdio will never reach it. Run the
same server over HTTP and deploy it behind HTTPS:

```powershell
newsblog-composer-mcp --http --host 0.0.0.0 --port 8000
```

Then in ChatGPT: Settings → Connectors → Advanced → Developer mode, then **Add
custom connector** pointing at `https://your-host/mcp`. Custom connectors need a
Pro, Team, Enterprise or Edu plan.

**Publishing to the MCP Registry** needs the package on PyPI first, then the
`mcp-publisher` CLI with `server.json` in this repo. Four things must line up or
the publish is rejected:

- `name` must match the authenticated GitHub account: `io.github.<username>/newsblog-composer`
- `description` must be 100 characters or fewer
- `packages[].version` must be a release that already exists on PyPI
- the README must carry `mcp-name: <that same name>` on its own line. The
  registry proves package ownership by reading the description PyPI serves for
  that exact version, so the marker has to be in the release you uploaded, not
  just in the repo. It is the HTML comment at the top of this file.

## How to test it

Three levels, cheapest first.

**1. Offline, no network — proves the logic.**

```powershell
python tests\smoke_test.py
```

272 checks covering schema parity, the SEO audit, AI-word detection, publisher
identity behind aggregator links, clustering, the publishing pack, the derived
image concept, the trademark filter and the install paths. All should pass in
about two seconds.

**2. Network — proves search reaches you.**

```powershell
python -m newsblog_mcp.diagnose "a headline you saw in the news today"
```

One line per provider with timings, then the verdict. What you want to see is
`independent_publishers` naming several real outlets and `reference_candidates`
holding real publisher URLs.

**3. A whole post, end to end.**

```powershell
python examples\build_today_example.py
```

Builds a complete package from a real story using facts already in the file, and
prints the keywords, schema validation, AI-word check, human score and SEO score
before writing the output folder. Use it as the reference for what a good run
looks like. `examples\build_mistral_example.py` does the same for the
hand-written reference post.

**4. In Claude Desktop**, after restarting it. Say it the way you normally
would — you should not have to name the tools:

> Write me a blog post about "<a real headline from today>"

The server should answer by calling `write_blog_post`, then `verify_news`, and
work through to the finished package, ending with the post rendered in an
artifact and the publishing details printed in the chat.

**If the client searches the web and writes its own markdown file instead**, the
extension did not trigger. Two things to check, in order:

1. Settings → Extensions shows it enabled. Note that closing the window on
   Windows only minimises to the tray — toggle the extension off and on to
   respawn the server.
2. **Tell the client to prefer it.** A host's own system prompt tends to treat
   "write me a blog post" as "search the web and make an artifact", and an MCP
   server's `instructions` cannot reliably outrank that. The fix is client-side:
   put a line like this in a Claude project's instructions, or in your global
   preferences, and work inside it —

   > When I ask for a blog post, an article, or a news write-up, always use the
   > NewsBlog Composer tools. Start with `write_blog_post`. Never search the web
   > and draft the article yourself.

   This is normal for local MCP servers; naming the server in the request works
   just as well for one-offs.

Extensions are **desktop only**. On the phone or the web app there is no
extension to call, and the client will answer from web search without saying
so.

## Privacy

The server runs on your own machine. Nothing is sent to the author of this
package, and there is no telemetry of any kind.

What leaves your machine, and only while a tool is running:

- **The headline or topic you give it** goes to whichever news search provider is
  active. With no keys configured that is GDELT and the Bing and Google News RSS
  feeds. If you set a provider key, it goes to that provider instead.
- **Article URLs** are fetched directly from the publishers that host them, the
  same request your browser would make.
- **Your draft text** goes to an AI detector only if you set `GPTZERO_API_KEY` or
  `SAPLING_API_KEY`, and to an image generator only if you call `generate_image`.
  Without those keys, no text leaves your machine for either purpose.

What stays on your machine: the publishing identity you set at first run
(`profile.json`), every generated post (`output/`), and any keys you configure.
See [Where it keeps your files](#where-it-keeps-your-files) for the exact paths.
Nothing in that folder is uploaded anywhere.

Optional API keys are read from the environment or from the extension's settings
panel. They are used only to authenticate with the provider they belong to.

## The tools

| Tool | What it does | Needs a key? |
|---|---|---|
| `capabilities` | Reports which providers are live and which fallbacks are in use | no |
| `write_blog_post` | The front door. Call it whenever someone asks for a blog post; returns the ordered plan | no |
| `find_stories` | Turns a topic into today's actual stories, grouped and ranked by corroboration and freshness | no |
| `verify_news` | Searches news providers, keeps matching results, counts independent publishers | no (keyless RSS) |
| `fetch_article_facts` | Downloads sources, extracts facts, short attributed quotes and figures | never |
| `draft_brief` | Returns the writing order: structure, sourced facts, keywords and FAQ candidates | never |
| `review_draft` | Reads the finished draft and says where it is weak, before publishing | never |
| `humanize_text` | Optional rewrite pass. Prefer `review_draft` | optional |
| `find_ai_words` | Finds every stock AI phrase with the sentence it sits in | never |
| `score_ai_text` | Local style score. `Not measured` unless a detector key is set | optional |
| `generate_image` | Concept banner, trademark filter applied first | no (watermarked) |
| `seo_keywords` | Mines keywords from the fetched sources; long-tail and FAQ queries from Google autocomplete | no |
| `seo_audit` | Scores the finished body against on-page rules, returns fixes | never |
| `build_publishing_pack` | Title, labels, permalink, alt text and a paste-ready Gemini image prompt | never |
| `build_schema` | Renders HTML body + both JSON-LD blocks, then validates them | never |
| `save_and_present` | Writes the package to `output/`, with canonical/OG/Twitter tags | never |

Resources: `newsblog://house-style` (structure and sourcing rules for the
drafting step) and `newsblog://humanizer-rules` (the rewrite rule set).

## The flow

There are two entry points, depending on what you type.

**A topic** — "today's AI news", "electric vehicles", "Indian fintech". There is
no claim to verify yet, so start by finding out what happened:

```
find_stories("AI", days=1)
  ↓  stories grouped by event, ranked by publisher count then freshness
     pick one from ready_to_write, check its age_hours
verify_news(story.headline)
  ↓  … and continue as below
```

**A specific headline** — start at `verify_news` directly. Note that an old
headline correctly returns old sources; `days` limits how far back to look.

```
verify_news(title)
  ↓  stop here if is_legit is false
fetch_article_facts(result.fetchable_urls)   # or story.fetchable_urls
  ↓
seo_keywords(title, [fact.text for fact in facts])
  ↓  primary + secondary keywords, slug, meta title/description,
     and FAQ questions taken from real autocomplete data
draft_brief(headline, facts, keywords)
  ↓  the writer writes the draft themselves
review_draft(draft, facts)      → must_fix / worth_fixing / consider
  ↓  the writer revises; repeat until must_fix is empty
find_ai_words(draft)            → until `clean` is true
  ↓
build_publishing_pack(...)      → title, labels, permalink, Gemini image prompt
  paste the prompt into Gemini, upload the image, take the public URL
  ↓
build_schema(article, faq, image, references, keywords)
  ↓  fix anything in validation.issues, then call again
seo_audit(html_body, primary_keyword, ...)
  ↓  fix everything in must_fix, then call again
save_and_present(..., meta=schema.meta, pack=pack)
```

Output lands in a timestamped folder under `output/`:

| File | What it is |
|---|---|
| `publish-pack.md` | Title, labels, custom permalink, search description, alt text, Gemini image prompt |
| `paste-into-blogger.html` | Both JSON-LD blocks then the styled body — the file you paste |
| `report.md` | Verification verdict, human score, AI-word status, SEO score, references |
| `index.html` | Standalone preview with meta, canonical, OG and Twitter tags |
| `body.html`, `*.jsonld`, `meta.json` | The pieces, separately |

Three guardrails are enforced in code, not left to the model:

- `verify_news` returns `is_legit: false` unless at least two independent
  publishers match the headline, or one primary/official source does.
- `build_schema` returns `validation.issues` listing every mismatch: an FAQ
  question that differs between the HTML and the FAQPage schema, an image URL
  that differs between the `<img>` tag and `NewsArticle.image`, a reference that
  is not a real fetched URL. A non-empty list means don't publish.
- `seo_audit` returns `must_fix` for the things that actually cost rankings —
  a duplicate H1, a missing keyword in the opening, images with no alt text, a
  meta description of the wrong length, fewer than two external source links.

Everything `fetch_article_facts` returns carries a `source_url`, so any claim in
the finished post can be traced back to the page it came from.

---

## No keys? Start here

With an empty `.env` the pipeline still runs end to end. Here is what you get,
and what each key would change.

| Step | With no key | With a key |
|---|---|---|
| Search | GDELT DOC 2.0 — official, free, no signup, news-specific — then Bing/Google News RSS as backup | Tavily / Brave / Serper / Google CSE: cleaner snippets, higher limits |
| Article extraction | Full quality. trafilatura runs locally. | — no key exists |
| Keywords | Full quality. Mined from your fetched sources, plus keyless Google autocomplete. | — a paid keyword API would add search-volume data |
| Humanise | Returns the rule set and asks the calling model to rewrite. Works well in Claude; varies elsewhere. | Rewrite happens server-side, identical everywhere |
| Human score | Local heuristic, labelled `is_real_detector: false` | A real detector's score |
| Image | Pollinations anonymous: ~1 request/15s, and **may watermark** | Cloudflare/OpenAI/Stability: clean, fast |
| Schema, audit, files | Full quality. | — no key exists |

### Search: what changed in 2026

**Brave is no longer the free recommendation.** In February 2026 Brave removed
its free tier and moved every plan to credit-based billing — a card is required,
a $5 monthly credit covers roughly 1,000 requests, and you are billed past that.

Free options that still hold up, best first:

- **GDELT** — no key, no signup, no limit to speak of. Already the default.
  It is a global news index, so it is genuinely good at "is anyone reporting
  this", which is exactly what `verify_news` asks. Start here and only add a key
  if snippet quality or freshness becomes a problem.
- **Tavily** — 1,000 credits/month, renews monthly, no card. The best keyed
  option for this pipeline. Set `TAVILY_API_KEY`.
- **Google Custom Search** — 100 queries/day, no card. Needs both
  `GOOGLE_CSE_KEY` and `GOOGLE_CSE_ID` from
  programmablesearchengine.google.com.
- **Serper** — 2,500 credits, no card, but one-time only. Fine for evaluating,
  not for an ongoing blog.
- **NewsAPI** — free tier is non-commercial only and delays recent articles,
  which is the wrong trade for breaking news.

Free tiers move around; check each provider's own pricing page before committing.

### Images: what you actually need

`generate_image` runs with no key, but read this before publishing anything.

Pollinations still allows anonymous requests — about one every 15 seconds, basic
models — but **the free anonymous tier may watermark the image**, which makes it
unusable as a published banner. Three ways out, cheapest first:

1. **Free Pollinations token** — register at auth.pollinations.ai, no card. This
   removes the watermark and raises the rate limit. Set `POLLINATIONS_TOKEN`.
   Smallest change, keeps the existing provider.
2. **Cloudflare Workers AI** (recommended) — FLUX schnell, a free daily
   allowance, no watermark, and it is a real production API. Set
   `IMAGE_PROVIDER=cloudflare`, `CLOUDFLARE_ACCOUNT_ID` and
   `CLOUDFLARE_API_TOKEN`. Note the model returns 1024x1024, so crop to your
   banner ratio.
3. **OpenAI Images or Stability** — paid per image, best quality.

Whichever you use, the file lands locally. Upload it and pass the public https
URL into `build_schema`, or `NewsArticle.image` points at a path no crawler can
reach.

### If you only add one key

Add **Cloudflare** (or the free Pollinations token) for images. Search already
works properly with no key; images are the step where the keyless output is not
publishable.

## Honest limitations

- **The human score is not proof of anything.** Public AI detectors have real
  false-positive and false-negative rates, especially on short text and on
  non-native English phrasing. The keyless fallback is not a detector at all —
  it measures the structural tells the rewrite rules target. Present it as a
  directional signal and say so wherever a reader sees the number.
- **The trademark filter is a safety net, not a legal opinion.** It rewrites
  known brand terms into generic descriptors and strips logo requests before the
  prompt leaves your machine. Extend `TRADEMARKS` in
  `src/newsblog_mcp/providers/imagegen.py` as you hit new names, and still look
  at what comes back.
- **Freshness is yours to set.** `find_stories(days=1)` is same-day; `days=2` is
  the default. `verify_news` searches a 14-day window unless you pass `days`.
  Feeding it a three-week-old headline returns three-week-old sources, correctly.
- **GDELT is an index, not an editor.** It indexes a very wide range of
  publishers, including low-quality ones, so two GDELT "publishers" agreeing is
  weaker evidence than two known outlets agreeing. Look at the domains in
  `sources` before trusting a `medium` confidence. The RSS backups are
  unofficial endpoints that can change shape without warning; `diagnose` tells
  you when one has stopped working.
- **The SEO tools cover on-page only.** Keyword relevance, structure, meta
  lengths, alt text, internal consistency. They say nothing about search volume,
  competition, or backlinks — that needs a paid keyword API, and no free tier
  gives real volume data.
- **Generated images are local files.** Upload the file and pass a public https
  URL into `build_schema`, or `NewsArticle.image` will point at a path no crawler
  can reach.
- **Corroboration is counted, not judged.** The server counts independent
  publishers and flags date conflicts. Whether those publishers are all repeating
  one wire story is a judgement the calling model still has to make.

## Layout

```
src/newsblog_mcp/
  server.py         MCP entrypoint: 10 tools, 2 resources
  diagnose.py       standalone connectivity check
  config.py         env loading, capability report
  textutil.py       tokenising, domains, sentence splitting, slugs
  providers/
    search.py       Tavily, Brave, Serper, Google CSE, NewsAPI, GDELT, RSS
    suggest.py      keyless Google autocomplete, for long-tail and FAQ queries
    llm.py          Anthropic / OpenAI, used only by humanize_text
    detector.py     GPTZero / Sapling
    imagegen.py     OpenAI / Stability / Cloudflare / Pollinations + trademark filter
  tools/            one module per MCP tool
  templates/        article.html.j2
  resources/        house_style.md, humanizer_patterns.md
tests/smoke_test.py offline test suite
output/             generated packages land here
```
