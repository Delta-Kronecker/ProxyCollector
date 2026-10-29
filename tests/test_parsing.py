#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Round-trip tests for proxy string parsing/formatting."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.collector import (  # noqa: E402
    parse_proxy_str, proxies_to_txt, proxies_to_uri, categorize_proxies,
    deduplicate_proxies,
)

CASES = [
    # input, protocol(bucket), scheme(kept), host, port, user, password
    ("socks://Og@127.0.0.1:9050", "socks5", "socks", "127.0.0.1", 9050, "Og", ""),
    ("socks://127.0.0.1:9050", "socks5", "socks", "127.0.0.1", 9050, None, None),
    ("socks5://u:p@1.2.3.4:1080", "socks5", "socks5", "1.2.3.4", 1080, "u", "p"),
    ("socks5h://1.2.3.4:1080", "socks5", "socks5h", "1.2.3.4", 1080, None, None),
    ("socks4://1.2.3.4:4145", "socks4", "socks4", "1.2.3.4", 4145, None, None),
    ("http://1.2.3.4:8080", "http", "http", "1.2.3.4", 8080, None, None),
    ("https://a:b@1.2.3.4:443", "https", "https", "1.2.3.4", 443, "a", "b"),
    ("1.2.3.4:3128", "http", "http", "1.2.3.4", 3128, None, None),
    ("socks://[::1]:9050", "socks5", "socks", "::1", 9050, None, None),
    ("ftp://1.2.3.4:21", None, None, None, None, None, None),
    ("", None, None, None, None, None, None),
]


def main() -> int:
    failures = 0

    for raw, bucket, scheme, host, port, user, password in CASES:
        p = parse_proxy_str(raw)
        if bucket is None:
            if p is not None:
                print(f"FAIL {raw!r}: expected rejection, got {p}")
                failures += 1
            continue

        if p is None:
            print(f"FAIL {raw!r}: expected a proxy, got None")
            failures += 1
            continue

        checks = [
            ("protocol", p.protocol, bucket),
            ("scheme", p.scheme, scheme),
            ("host", p.host, host),
            ("port", p.port, port),
            ("username", (p.auth or {}).get("username"), user),
            ("password", (p.auth or {}).get("password"), password),
        ]
        bad = [f"{k}: {got!r} != {want!r}" for k, got, want in checks if got != want]
        if bad:
            print(f"FAIL {raw!r}: " + "; ".join(bad))
            failures += 1
        else:
            print(f"ok   {raw!r} -> {p.protocol} ({p.scheme})")

    # socks:// must round-trip through the TXT writer unchanged
    p = parse_proxy_str("socks://Og@127.0.0.1:9050")
    out = proxies_to_txt([p]).strip()
    if out != "socks://Og@127.0.0.1:9050":
        print(f"FAIL round-trip: {out!r}")
        failures += 1
    else:
        print(f"ok   round-trip: {out}")

    # socks:// lands in socks5 bucket, and dedup treats it as one proxy
    socks = parse_proxy_str("socks://127.0.0.1:9050")
    socks5 = parse_proxy_str("socks5://127.0.0.1:9050")
    cats = categorize_proxies([socks, socks5])
    if len(cats["socks5"]) != 2 or len(deduplicate_proxies([socks, socks5])) != 1:
        print("FAIL category/dedup handling of socks://")
        failures += 1
    else:
        print("ok   category: socks:// -> socks5 bucket, deduped with socks5://")

    # URI export: socks proxies use the generic socks:// scheme,
    # single-token credential when there is no password
    uri_socks_user = proxies_to_uri([parse_proxy_str("socks://Og@127.0.0.1:9050")]).strip()
    uri_socks_plain = proxies_to_uri([parse_proxy_str("socks5://1.2.3.4:1080")]).strip()
    uri_socks_pass = proxies_to_uri([parse_proxy_str("socks5://u:p@1.2.3.4:1080")]).strip()
    uri_http = proxies_to_uri([parse_proxy_str("http://1.2.3.4:8080")]).strip()
    expected = [
        (uri_socks_user, "socks://Og@127.0.0.1:9050"),
        (uri_socks_plain, "socks://1.2.3.4:1080"),
        (uri_socks_pass, "socks://u:p@1.2.3.4:1080"),
        (uri_http, "http://1.2.3.4:8080"),
    ]
    for got, want in expected:
        if got != want:
            print(f"FAIL uri: {got!r} != {want!r}")
            failures += 1
        else:
            print(f"ok   uri: {got}")

    print(f"\n{'FAILED' if failures else 'PASSED'} ({failures} failure(s))")
    return 1 if failures else 0

if __name__ == "__main__":
    raise SystemExit(main())
