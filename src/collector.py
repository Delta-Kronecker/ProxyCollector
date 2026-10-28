#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Proxy Collector - Aggregates proxies from multiple sources,
removes duplicates, and outputs categorized files.
"""

import asyncio
import asyncio
import json
import re
from typing import List, Dict, Any, Set, Optional
from dataclasses import dataclass, asdict
from pathlib import Path
import csv
from io import StringIO

try:
    import httpx
    import orjson
except ImportError:
    raise ImportError(
        "Missing dependencies. Install with: pip install -r requirements.txt"
    )


@dataclass
class Proxy:
    protocol: str
    host: str
    port: int
    auth: Optional[Dict[str, str]] = None
    timeout: Optional[float] = None
    exit_ip: Optional[str] = None
    response_time: Optional[float] = None
    country: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "protocol": self.protocol,
            "host": self.host,
            "port": self.port,
            "auth": self.auth,
            "timeout": self.timeout,
            "exit_ip": self.exit_ip,
            "response_time": self.response_time,
            "country": self.country
        }

    def as_tuple(self) -> tuple:
        return (self.protocol, self.host, self.port)


def parse_proxy_str(proxy_str: str) -> Optional[Proxy]:
    """Parse HTTP/SOCKS proxy string including auth"""
    proxy_str = proxy_str.strip()
    if not proxy_str:
        return None

    # Detect protocol (http, https, socks4, socks5)
    protocol = "http"
    if proxy_str.startswith(("socks5://", "socks4://", "socks5h://", "socks4h://", "socks5:", "socks4:")):
        proto_match = re.match(r'(?:https?://|socks4://|socks5://|socks4h://|socks5h://)?(.+)', proxy_str)
        if proto_match:
            protocol = proxy_str.split("://")[0].lower() if "://" in proxy_str else "http"
    else:
        protocol = "http"
        proxy_str = f"http://{proxy_str}"

    content = proxy_str.split("://", 1)[1]

    # Extract auth if present
    auth_info = None
    if "@" in content:
        auth_part, rest_part = content.rsplit("@", maxsplit=1)
        if ":" in auth_part:
            user, password = auth_part.split(":", 1)
            auth_info = {"username": user, "password": password}
        content = rest_part
    else:
        content = content

    # Extract host and port
    m = re.search(r'^([^:]+):(\d+)$', content.strip())
    if not m:
        return None

    host = m.group(1)
    port = int(m.group(2))

    if not host or not re.match(r'^[\da-fA-F.:]+$', host):
        return None

    return Proxy(protocol=protocol, host=host, port=port, auth=auth_info)


async def fetch_proxies_from_urls(urls: List[str], source_type: str = "mixed") -> List[Proxy]:
    """
    Fetch proxies from multiple URLs concurrently.
    Automatically detects JSON or TXT source.
    """
    all_proxies: List[Proxy] = []

    async def _fetch_single(url: str):
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(30),
                follow_redirects=True
            ) as client:
                resp = await client.get(url)
                content = resp.text

                if url.endswith(".json"):
                    proxies = await _parse_json_proxies(content)
                else:
                    proxies = await _parse_txt_proxies(content)

                return proxies
        except Exception as e:
            print(f"     ! Error fetching {url}: {e}")
            return []

    tasks = [_fetch_single(url) for url in urls]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for i, result in enumerate(results):
        if isinstance(result, Exception):
            print(f"     ! Result {i} had exception: {result}")
            continue
        all_proxies.extend(result)

    return all_proxies


async def _parse_json_proxies(content: str) -> List[Proxy]:
    proxies = []

    try:
        data = orjson.loads(content)
    except Exception as e:
        print(f"    ! Failed to parse JSON: {e}")
        return proxies

    if isinstance(data, list):
        for item in data:
            if not isinstance(item, dict):
                continue

            try:
                proxy = Proxy(
                    protocol=item.get("protocol", "http"),
                    host=item.get("host"),
                    port=item.get("port")
                )

                auth = item.get("auth")
                if auth and isinstance(auth, dict):
                    proxy.auth = {
                        k: str(v) for k, v in auth.items() if v
                    }

                proxy.timeout = item.get("timeout")
                proxy.exit_ip = item.get("exit_ip")
                proxy.response_time = item.get("response_time")
                proxy.country = item.get("country")

                proxies.append(proxy)
            except Exception:
                continue
    elif isinstance(data, dict):
        # GitHub content sometimes returns repo info as dict with "content" field
        content_base64 = data.get("content", "")
        if content_base64:
            try:
                import base64
                decoded = base64.b64decode(content_base64).decode("utf-8")
                return await _parse_json_proxies(decoded)
            except Exception:
                pass

    return proxies


async def _parse_txt_proxies(content: str) -> List[Proxy]:
    proxies = []
    for line in content.splitlines():
        if line.strip():
            proxy = parse_proxy_str(line)
            if proxy:
                proxies.append(proxy)
    return proxies


def deduplicate_proxies(proxies: List[Proxy]) -> List[Proxy]:
    """Remove duplicate proxies based on (protocol, host, port)"""
    seen: Set[tuple] = set()
    unique: List[Proxy] = []

    for proxy in proxies:
        key = proxy.as_tuple()
        if key not in seen:
            seen.add(key)
            unique.append(proxy)

    return unique


def categorize_proxies(proxies: List[Proxy]) -> Dict[str, List[Proxy]]:
    """Categorize proxies by protocol."""
    protocols = ["all", "http", "https", "socks4", "socks5"]
    categories: Dict[str, List[Proxy]] = {p: [] for p in protocols}
    categories["all"] = proxies

    for proxy in proxies:
        protocol = proxy.protocol.lower()
        if protocol in categories:
            categories[protocol].append(proxy)
        elif protocol in {"http", "https", "socks4", "socks5"}:
            categories[protocol].append(proxy)

    return categories


def proxies_to_txt(proxies: List[Proxy]) -> str:
    """Convert proxies to plain text format."""
    lines = []
    for proxy in proxies:
        if proxy.auth:
            lines.append(f"{proxy.protocol}://{proxy.auth['username']}:{proxy.auth['password']}@{proxy.host}:{proxy.port}")
        else:
            lines.append(f"{proxy.protocol}://{proxy.host}:{proxy.port}")
    return "\n".join(lines) + "\n"


def proxies_to_json(proxies: List[Proxy]) -> str:
    """Convert proxies to JSON format."""
    data = [proxy.to_dict() for proxy in proxies]
    return orjson.dumps(data, option=orjson.OPT_INDENT_2).decode("utf-8")


def proxies_to_csv(proxies: List[Proxy]) -> str:
    """Convert proxies to CSV format."""
    output = StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)

    header = ["protocol", "host", "port", "username", "password",
              "timeout", "exit_ip", "response_time", "country"]
    writer.writerow(header)

    for proxy in proxies:
        auth_user = proxy.auth["username"] if proxy.auth else ""
        auth_pass = proxy.auth["password"] if proxy.auth else ""

        writer.writerow([
            proxy.protocol,
            proxy.host,
            proxy.port,
            auth_user,
            auth_pass,
            proxy.timeout or "",
            proxy.exit_ip or "",
            proxy.response_time or "",
            proxy.country or ""
        ])

    return output.getvalue() + "\n"


async def main():
    """Main collection pipeline."""
    import pathlib
    config_path = pathlib.Path(__file__).parent.parent / "config.json"

    if not config_path.exists():
        print(f"❌ config.json not found: {config_path}")
        return

    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    sources = config.get("sources", [])
    output_formats = config.get("output_formats", ["json", "txt", "csv"])
    output_dir_str = config.get("output_dir", "output")

    proxy_dir = pathlib.Path(__file__).parent.parent

    output_dir = proxy_dir / output_dir_str
    output_dir.mkdir(exist_ok=True)

    print("🎯 Starting proxy collection...")
    print(f"   Sources: {len(sources)}")

    all_proxies: List[Proxy] = []

    for i, source in enumerate(sources, 1):
        source_name = source.get("name", "unknown")
        source_url = source.get("url")
        protocols = source.get("protocols")

        print(f"\n📥 Source {i}/{len(sources)}: {source_name}")

        if not source_url:
            print("   ✗ No URL provided")
            continue

        try:
            fetched = await fetch_proxies_from_urls([source_url])
            print(f"   ✓ Fetched {len(fetched)} proxies")

            protocols_set = set(protocols) if protocols else None
            filtered = [
                p for p in fetched
                if protocols_set is None or p.protocol in protocols_set
            ]

            all_proxies.extend(filtered)
            print(f"   ✓ After protocol filter: {len(filtered)}")
        except Exception as e:
            print(f"   ✗ Error: {e}")

    print(f"\n📊 Total proxies collected: {len(all_proxies)}")

    if not all_proxies:
        print("❌ No proxies collected. Aborting.")
        return

    # Deduplicate
    print("\n🔄 Deduplicating...")
    unique_proxies = deduplicate_proxies(all_proxies)
    print(f"   ✓ After deduplication: {len(unique_proxies)}")

    # Categorize
    print("\n📁 Categorizing...")
    categorized = categorize_proxies(unique_proxies)

    for protocol_name in ["http", "https", "socks4", "socks5"]:
        count = len(categorized[protocol_name])
        print(f"   ✓ {protocol_name.upper()}: {count}")

    print(f"   ✓ ALL: {len(categorized['all'])}")

    print(f"\n💾 Saving files to {output_dir}/")

    # Save files grouped by protocol
    protocol_names = ["all", "http", "https", "socks4", "socks5"]

    for protocol_name in protocol_names:
        proxies = categorized[protocol_name]

        # each protocol gets its own subfolder: output/all/, output/http/, ...
        protocol_dir = output_dir / protocol_name
        protocol_dir.mkdir(exist_ok=True)

        for fmt in output_formats:
            content = ""
            if fmt == "json":
                content = proxies_to_json(proxies)
            elif fmt == "txt":
                content = proxies_to_txt(proxies)
            elif fmt == "csv":
                content = proxies_to_csv(proxies)

            if content:
                out_path = protocol_dir / f"{protocol_name}.{fmt}"
                out_path.write_text(content, encoding="utf-8")
                print(f"   ✓ {fmt.upper()}: {protocol_name}/{protocol_name}.{fmt}")

    print(f"\n✅ Pipeline completed!")


if __name__ == "__main__":
    asyncio.run(main())