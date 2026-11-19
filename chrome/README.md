# Server Chrome

- Image: `lscr.io/linuxserver/chrome:latest` (LinuxServer Selkies)
- URL: https://chrome.speedtest.xuchengcat.cn:444
- Start/update: `docker compose pull && docker compose up -d` from this directory.
- Fixed desktop: 2560 × 1440. Automatic client resize disabled.
- Browser settings, extensions and sessions: `./config` (private, Git ignored).
- Host media `/mnt/HDD14T/Media_Data_HDD` mounted read/write at `/media`.
- Downloads prompt for location; choose `/media` and the desired subfolder.
- Cat Catch official Chrome Web Store ID: `jfedfbgedapdagkghmgibemcoggfppbb`.
- Managed policy auto-installs/updates Cat Catch and pins its toolbar icon.
- Policy file: `policies/managed/chrome.json`, mounted read-only.
- Browser policy checks: `chrome://policy`; installed extensions: `chrome://extensions`.
- Access via shared Nginx Proxy Manager and existing TLS certificate; no host ports published.
- Does not mount Docker socket or host root. Media permissions are not modified.

Open the URL in a local browser, then use the Chrome address bar inside the remote desktop to browse. Click the Cat Catch toolbar icon to open the extension. Browser data is private and must never be committed to Git.

Network access uses the existing host proxy through the private `chrome-proxy` relay. Its upstream credential is stored only in `private/upstream` (mode 600, Git ignored); the relay runs as UID 1000 without capabilities and exposes no host ports. Browser policy routes public traffic through this relay and bypasses local addresses. No user account is logged in automatically.
