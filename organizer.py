"""Capture web pages and sort screenshots by configured hostname rules."""
from __future__ import annotations

import argparse
import ipaddress
import json
import re
import socket
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

DEFAULT_CONFIG = Path(__file__).with_name('config.example.json')
FOLDER_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9 _-]{0,63}$')


class ConfigError(ValueError):
    pass


def validate_hostname(hostname: str) -> str:
    hostname = hostname.lower().rstrip('.')
    if not hostname or len(hostname) > 253 or not re.fullmatch(r'[a-z0-9.-]+', hostname):
        raise ConfigError('Invalid hostname')
    if hostname == 'localhost' or hostname.endswith('.localhost'):
        raise ConfigError('Local hosts are not permitted')
    try:
        ipaddress.ip_address(hostname)
    except ValueError:
        pass
    else:
        raise ConfigError('IP literal URLs are not permitted')
    if '.' not in hostname or any(not part or part.startswith('-') or part.endswith('-') for part in hostname.split('.')):
        raise ConfigError('Use a valid public DNS hostname')
    return hostname


def validate_url(url: str) -> str:
    try:
        parts = urlsplit(url)
        if parts.scheme != 'https' or not parts.hostname or parts.username or parts.password or parts.port not in (None, 443):
            raise ConfigError('Only HTTPS URLs without credentials or custom ports are supported')
        validate_hostname(parts.hostname)
    except ValueError as exc:
        raise ConfigError(f'Invalid URL: {exc}') from exc
    return url


def check_public_dns(hostname: str) -> None:
    """Best-effort guard; not a network sandbox or DNS-rebinding defense."""
    try:
        addresses = socket.getaddrinfo(hostname, 443, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ConfigError(f'Unable to resolve {hostname}: {exc}') from exc
    if not addresses:
        raise ConfigError('Hostname did not resolve')
    for result in addresses:
        address = ipaddress.ip_address(result[4][0])
        if not address.is_global:
            raise ConfigError(f'Non-public address blocked for {hostname}')


def safe_folder(value: str) -> str:
    if not isinstance(value, str) or not FOLDER_RE.fullmatch(value) or value in ('.', '..'):
        raise ConfigError('Folder names must be simple names (letters, numbers, spaces, _ or -)')
    return value


def load_config(path: Path) -> dict:
    try:
        config = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigError(f'Cannot read configuration: {exc}') from exc
    if not isinstance(config, dict) or not isinstance(config.get('rules'), dict):
        raise ConfigError('Configuration must have a rules object')
    for domain, folder in config['rules'].items():
        validate_hostname(domain)
        safe_folder(folder)
    safe_folder(config.get('unknown_folder', 'Other'))
    urls = config.get('urls', [])
    if not isinstance(urls, list) or not all(isinstance(u, str) for u in urls):
        raise ConfigError('urls must be a list of strings')
    for url in urls:
        validate_url(url)
    return config


def folder_for(hostname: str, rules: dict, unknown: str) -> str:
    hostname = validate_hostname(hostname)
    # Exact matches win, then longest matching parent domain.
    candidates = [domain for domain in rules if hostname == domain or hostname.endswith('.' + domain)]
    return rules[max(candidates, key=len)] if candidates else unknown


def capture(url: str, output: Path, config: dict) -> Path:
    from playwright.sync_api import sync_playwright

    validate_url(url)
    check_public_dns(urlsplit(url).hostname)
    output.mkdir(parents=True, exist_ok=True)
    # Temporary file is created inside output to permit atomic replacement.
    temp_path = None
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                context = browser.new_context(viewport={'width': 1365, 'height': 900}, device_scale_factor=1,
                                              accept_downloads=False, service_workers='block')
                page = context.new_page()

                def guard(route):
                    request_url = route.request.url
                    try:
                        validate_url(request_url)
                        host = urlsplit(request_url).hostname
                        check_public_dns(host)
                    except ConfigError:
                        route.abort()
                        return
                    route.continue_()

                # Includes redirected requests and page subresources. DNS checks are best-effort.
                page.route('**/*', guard)
                response = page.goto(url, wait_until='domcontentloaded', timeout=30000)
                if response is None:
                    raise RuntimeError('No page response received')
                page.wait_for_timeout(1200)
                final_url = page.url
                validate_url(final_url)
                hostname = urlsplit(final_url).hostname
                folder = safe_folder(folder_for(hostname, config['rules'], config.get('unknown_folder', 'Other')))
                destination_dir = output / folder
                destination_dir.mkdir(parents=True, exist_ok=True)
                with tempfile.NamedTemporaryFile(prefix='.capture_', suffix='.png', dir=destination_dir, delete=False) as temp:
                    temp_path = Path(temp.name)
                page.screenshot(path=str(temp_path), full_page=True, animations='disabled', timeout=30000)
                filename = f"{hostname.replace('.', '_')}_{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}_{uuid4().hex[:8]}.png"
                destination = destination_dir / filename
                temp_path.replace(destination)
                temp_path = None
                return destination
            finally:
                browser.close()
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='Capture HTTPS web pages into website-specific folders.')
    parser.add_argument('urls', nargs='*', help='HTTPS pages to capture; defaults to config urls')
    parser.add_argument('--config', type=Path, default=DEFAULT_CONFIG)
    parser.add_argument('--output', type=Path, default=Path(__file__).with_name('screenshots'))
    args = parser.parse_args(argv)
    try:
        config = load_config(args.config)
        urls = args.urls if args.urls else config['urls']
        if not urls:
            raise ConfigError('No URLs provided in arguments or configuration')
        for url in urls:
            validate_url(url)
    except ConfigError as exc:
        print(f'Configuration error: {exc}', file=sys.stderr)
        return 2
    failures = 0
    for url in urls:
        try:
            path = capture(url, args.output, config)
            print(f'OK: {url} -> {path}')
        except Exception as exc:
            failures += 1
            print(f'FAILED: {url}: {exc}', file=sys.stderr)
    return 1 if failures else 0


if __name__ == '__main__':
    raise SystemExit(main())
