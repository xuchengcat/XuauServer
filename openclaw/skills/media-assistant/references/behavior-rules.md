# Media interaction rules

## Search result presentation

Return no more than eight numbered candidates. For each candidate show, when available:

- release title;
- episode or season coverage;
- resolution and source;
- video codec and HDR/Dolby Vision status;
- size;
- seeders;
- publication time;
- download-volume factor/freeleech status.

Never display `enclosure`, site cookies, access tokens, API keys, private tracker credentials, or a credential-bearing URL.

Rank compatible freeleech releases ahead of charged releases, but keep charged candidates visible with an explicit label. Prefer a healthy seeder count and a complete episode range over a marginal quality difference.

## Authorization boundary

- Search language alone never authorizes a download or subscription.
- An unambiguous reply such as “下载 2”, “下第二个”, or “就要 2” authorizes exactly item 2 from the latest search in the same direct-chat session. Do not ask for an additional confirmation.
- Do not resolve a bare number across another user, group chat, session, intervening search, or media title.
- Treat a numbered selection as stale after 30 minutes. Re-run the search and explain any changed availability, size, or promotion before downloading.
- If the selected candidate disappeared or changed, do not silently substitute another release.
- An explicit “订阅/追更 + media identity” request authorizes creation of that subscription. Clarify only genuinely ambiguous title, year, season, or media type.

## Mutation rules

Use MoviePilot for all downloads so that history, organization, and media-server refresh stay coherent. Unless the user separately and explicitly requests the exact operation, never invoke operations that:

- delete a download, subscription, history record, file, directory, cache, site, plugin, workflow, rule, or backup;
- move or rename an existing Transmission task;
- change a tracker, site credential, MoviePilot configuration, or classification policy;
- run system updates, restarts, schedulers, plugins, workflows, database operations, or storage management.

If MoviePilot reports `requires_confirmation` because a release is unrecognized, show the recognition problem and ask whether to continue. Do not set `allow_unrecognized=true` from the original numbered selection alone.

## Status reporting

After a successful download submission, report the release title, size, downloader, and save path. After a successful subscription write, report media title, season, resolution profile, M-Team scope, and target category. Never claim completion based only on a pending or unknown execution outcome.
