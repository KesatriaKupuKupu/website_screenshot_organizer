# Website Screenshot Organizer

A Python CLI that **captures website screenshots itself** (using Playwright Chromium) and saves each screenshot into a folder selected by the final page's hostname. This evolves an earlier `watchdog` experiment that only printed newly created screenshot file paths; the folder watcher is intentionally replaced because browser capture gives the program a reliable source URL.

## Features

- Capture full-page PNG screenshots from HTTPS websites.
- Sort into folders using exact-domain or subdomain rules; longest matching domain wins.
- Put unrecognized public domains in `Other` (configurable).
- Unique UTC timestamp + random suffix to avoid overwriting existing screenshots.
- Temporary files cleaned up after failures; batch mode continues after individual failures.
- URL and folder-name validation; best-effort blocking of private/local network targets.
- No API keys, cookies, or credentials required.

## Installation (Windows PowerShell, Python 3.10+)

```powershell
cd website_screenshot_organizer
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m playwright install chromium
```

## Usage

Edit `config.example.json` to add domains, folders, and URLs. Then run:

```powershell
python organizer.py
python organizer.py https://docs.github.com/ https://www.wikipedia.org/
python organizer.py --config config.example.json --output "C:\Users\YourName\Pictures\WebScreenshots"
```

Example output:

```text
screenshots/
  GitHub/
    docs_github_com_20261107T120000Z_a1b2c3d4.png
  Wikipedia/
    www_wikipedia_org_20261107T120001Z_e5f6a7b8.png
  Other/
    example_com_20261107T120002Z_1234abcd.png
```

If a website redirects to a different domain, the **final domain** determines its folder. A domain rule such as `github.com` also matches `docs.github.com`, but not `notgithub.com`. More specific rules take precedence.

## Tests

```powershell
python -m unittest discover -s tests -v
```

The tests cover configuration, URL validation, and folder matching. They do **not** test real browser capture; that requires Playwright Chromium and network access.

## Security and limitations

- Only HTTPS pages on public-looking hostnames are accepted; custom ports, IP literals, and credentials in URLs are rejected.
- DNS resolution is checked for public IP addresses for requests, including redirected/subresource requests. **This is a best-effort protection, not a hardened SSRF sandbox**: DNS rebinding, proxy configuration, browser internals, and complex network behaviors can bypass application-level checks. Do not use against untrusted URLs in a privileged or sensitive network. Run with an unprivileged account, ideally in an isolated environment.
- Pages may load remote scripts, show cookie banners, or block automated browsers. Some sites need login, consent, or custom rendering logic; these are not supported.
- Screenshots can contain personal information. Only capture pages you are authorized to access and keep output folders private.
- Captures run **on demand**, not continuously or on a schedule. A scheduler can be added later.
- This does not identify the website from an existing image; it captures a known URL and therefore knows the source.
- Network calls are performed during capture, and a slow site may delay a batch. Some pages are extremely tall, causing screenshot failures or large PNG files.

## Architecture

1. CLI loads and validates JSON configuration.
2. Playwright launches Chromium and navigates to each HTTPS URL.
3. A request route validates each requested URL and performs a best-effort public-DNS check.
4. After loading, the program reads the final page hostname.
5. Longest-domain rule selects a folder; unmatched domains use `Other`.
6. PNG is written to a temporary file and renamed to a unique final filename.

## Ideas for independent improvements

- Add a scheduled capture mode or Windows Task Scheduler instructions.
- Add structured logging and configurable viewport sizes.
- Add screenshot comparison/change detection.
- Add integration tests using a controlled HTTPS test website.
- Consider an isolated browser container and stricter network egress controls for a security-hardened version.

## CV description (only after you personally understand and can explain the implementation)

> Developed a Python website screenshot organizer using Playwright to capture web pages and automatically categorize images by configurable domain rules; added URL validation, collision-resistant filenames, and error handling.

If using this project for university applications, be transparent about any AI assistance and describe your own contributions accurately.
