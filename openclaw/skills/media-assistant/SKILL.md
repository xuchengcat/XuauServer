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
4. Prefer `search.torrents` with the exact `media_source`, `media_id`, and explicit `mtype` (`movie` / `tv` / `music`). Preserve all three plus the site restriction on every retry. A numeric TMDB ID alone cannot identify movie versus TV. Use `search.title` only when canonical media resolution is unavailable or the user explicitly wants a raw title search.
5. Present at most eight numbered results using the fields required by the behavior rules. A recommendation is advisory and never authorizes a download.
6. When the user explicitly selects an item such as “下载 2”, submit exactly that candidate through `download.add`. Preserve the complete `torrent_in`, its source-native media identity, and use `/downloads/incoming/moviepilot` unless MoviePilot reports a different configured download path.
7. Preserve MoviePilot's destination classification: animated movies belong in `Movies`; Chinese, Japanese, and other animated series belong in `Cartoon`. Never classify an animated movie as an animated series merely because it is animation.
8. Create a subscription through `subscription.add` only when the user explicitly says “订阅” or “追更”. Restrict `sites` to M-Team and use the matching quality profile.
9. Check the tool response before reporting success. If a write outcome is unknown, inspect download or subscription state rather than repeating the write.
10. Use `download.tasks.active` and `download.history.list` for download status; `download.list` does not exist. Check completed history/library as well as active tasks before submitting an already requested resource. Never re-add a resource the user says is completed.
11. A search timeout, `operation_unavailable`, or media-recognition failure is not proof of zero resources. Long searches may continue after the tool returns. Wait before one read-only retry with the same identity/type/site; if canonical lookup remains unavailable, try `search.title` with that title and `mtype`, and clearly label results as title-search candidates. Never retry `download.add` automatically.
12. Follow the published input contract exactly: GET search `sites` is a string such as `"1"`; exact-search `media_id` is a string; paginated `search.torrents` uses one-based `page` (start at 1). Do not copy `search.title` pagination conventions into exact search. On `invalid_input`, correct the reported field types/required fields before retrying.
13. Start exact-search pages with `count=2`. If `tool_result_truncated=true`, repeat that read with `count=1` and the same identity/type/site/page, then collect further pages as needed. A truncated preview is not a failure or an empty result. Never construct `torrent_in` or an enclosure from `content_preview`; obtain the complete candidate on a smaller page. Use `collection.total_count` for the total and `result_count` for the current page size.

Do not use arbitrary HTTP, expose credentials or private enclosure URLs, or bypass MoviePilot by talking directly to Transmission.
