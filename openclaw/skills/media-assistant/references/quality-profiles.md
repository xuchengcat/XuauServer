# NAS media quality profiles

Use these as defaults only. A user's explicit request overrides the corresponding preference.

## Shared rules

- Default site: M-Team only.
- Prefer freeleech, then discounted, then normal download-volume factor when quality and completeness are comparable.
- Prefer releases with Chinese audio or Chinese subtitles as appropriate.
- Exclude samples, trailers, pure extras, obvious upscales, and AI frame-interpolated releases by default.
- Download path: `/downloads/incoming/moviepilot`.

## Chinese TV drama

Rank in this order:

1. 2160p WEB-DL HEVC/H.265.
2. 2160p WEB-DL H.264.
3. 1080p WEB-DL HEVC/H.265.
4. 1080p WEB-DL H.264.

Prefer Mandarin and Chinese subtitles. Exclude Blu-ray folders and REMUX by default. Target category: `/downloads/Teleplay`.

## Variety shows

Prefer 2160p WEB-DL, then 1080p WEB-DL. Prefer per-episode releases for active shows. Do not enable automatic season-pack upgrades initially. Exclude previews, highlight-only edits, and standalone extras. Target category: `/downloads/Merry`.

## Animated series

- Chinese animation: prefer 2160p WEB-DL, then 1080p WEB-DL.
- Japanese and other animation: prefer 1080p BluRay or WEB-DL unless the user requests 2160p.
- Prefer Simplified/Traditional Chinese subtitles; exclude raw releases and AI 60fps by default.
- Preserve season, absolute-episode, and special-episode identity returned by MoviePilot.
- Animated series target category: `/downloads/Cartoon`.

## Animated movies

- Apply the user's requested resolution, codec, subtitle, and compatibility preferences as for other movies.
- Animated movies are movies, not animated series. Target category: `/downloads/Movies`.

## Compatibility

Do not prefer Dolby Vision-only releases unless the user explicitly asks for Dolby Vision or the known playback profile supports it. HDR10 fallback is preferable for broad Jellyfin client compatibility.
