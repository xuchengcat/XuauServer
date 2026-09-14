---
name: media-assistant
description: Search M-Team through MoviePilot, present numbered media choices, download an explicitly selected result, or create an explicitly requested TV/anime/variety subscription.
---

# Media Assistant

Use the configured MoviePilot MCP `moviepilot_api` tool for media discovery, M-Team torrent search, explicit downloads, subscriptions, and status checks.

Read [references/behavior-rules.md](references/behavior-rules.md) before searching, downloading, or subscribing. Read [references/quality-profiles.md](references/quality-profiles.md) when ranking results or creating a subscription.

## Workflow

1. Treat “想看”, “帮我找”, and “搜一下” as search-only intent.
2. Resolve the media identity with `media.search`; ask for title/year/season clarification only when multiple plausible media identities remain.
3. Obtain the active M-Team site ID with `site.list` or `site.searchable` and restrict torrent searches to that exact site. Do not search every configured site by default.
4. Prefer `search.torrents` with the exact `media_source` and `media_id`; use `search.title` only when canonical media resolution is unavailable or the user explicitly wants a raw title search.
5. Present at most eight numbered results using the fields required by the behavior rules. A recommendation is advisory and never authorizes a download.
6. When the user explicitly selects an item such as “下载 2”, submit exactly that candidate through `download.add`. Preserve the complete `torrent_in`, its source-native media identity, and use `/downloads/incoming/moviepilot` unless MoviePilot reports a different configured download path.
7. Preserve MoviePilot's destination classification: animated movies belong in `Movies`; Chinese, Japanese, and other animated series belong in `Cartoon`. Never classify an animated movie as an animated series merely because it is animation.
8. Create a subscription through `subscription.add` only when the user explicitly says “订阅” or “追更”. Restrict `sites` to M-Team and use the matching quality profile.
9. Check the tool response before reporting success. If a write outcome is unknown, inspect download or subscription state rather than repeating the write.

Do not use arbitrary HTTP, expose credentials or private enclosure URLs, or bypass MoviePilot by talking directly to Transmission.
