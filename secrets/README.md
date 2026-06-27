# Local secrets (not committed)

Place exported yt-dlp **Netscape format** cookies here:

```
secrets/yt-dlp-cookies.txt
```

## One-time export (recommended)

Avoids macOS repeatedly asking to access Chrome keychain when using `YT_DLP_COOKIES_FROM_BROWSER=chrome`.

1. Install a browser extension such as [Get cookies.txt LOCALLY](https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc) (Chrome / Edge).
2. In the browser, log in and open the sites you need (e.g. [bilibili.com](https://www.bilibili.com), [youtube.com](https://www.youtube.com)).
3. Use the extension to export **all cookies** (or site-specific) as `cookies.txt`.
4. Save the file as `secrets/yt-dlp-cookies.txt` in this repo (this path is gitignored).
5. In the repo root `.env`:

   ```bash
   YT_DLP_COOKIES=secrets/yt-dlp-cookies.txt
   ```

6. Restart the Node server. Integration tests read the same variable from your environment.

**Do not commit** `cookies.txt` — it contains session tokens.

## Refresh

Cookies expire. If B站 returns HTTP 412 or YouTube shows bot checks, re-export and replace the file.

## Fallback

If you prefer not to use a file, you can set `YT_DLP_COOKIES_FROM_BROWSER=chrome` instead (macOS may prompt for keychain access each time).
