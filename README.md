# Proxy Collector

Automated proxy aggregation, deduplication, and export pipeline.

## Features

- 🔄 **Multi-source collection** from proven sources (Ercin, Monosans)
- 🧹 **Deduplication** based on (protocol, host, port)
- 📁 **Categorization** by protocol (HTTP, HTTPS, SOCKS4, SOCKS5)
- 📊 **Multiple formats**: JSON, TXT, CSV
- ✨ **Async fetcher** with configurable timeout & retries
- 🎯 **Protocol flexibility**: supports `socks://` format (aliased to `socks5://`)

## Supported Sources

| Source | Description |
|--------|-------------|
| `lercin-http` | HTTP proxies (~65k) |
| `lercin-https` | HTTPS proxies (~3k) |
| `lercin-socks5` | SOCKS5 proxies (~99k) |
| `lercin-socks4` | SOCKS4 proxies (~22k) |
| `monosans-txt` | All protocols (~605) |
| `monosans-json` | All protocols with metadata (~1k) |

**Notes**:
- For total count: 65,829 unique proxies (after deduplication)
- Extracted protocols: HTTP (65,224), SOCKS4 (147), SOCKS5 (458)
- Source pipelines are ideal for bulk scraping and verify

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run collection (fetches from all configured sources)
python main.py
```

## Output Files

All outputs are stored in `output/` folder, categorized by protocol:

```
output/
├── all/     # All protocols combined: all.json, all.txt, all.csv
├── http/    # HTTP only
├── https/   # HTTPS only
├── socks4/  # SOCKS4 only
├── socks5/  # SOCKS5 only
└── uri/     # plain proxy URIs, one per line
    ├── all.txt
    ├── http.txt
    ├── https.txt
    ├── socks4.txt
    └── socks5.txt
```

### URI format (`output/uri/`)

Every SOCKS proxy is written with the generic `socks://` scheme, and the
credential is a single token when no password is present:

```
socks://Og@127.0.0.1:9050
socks://1.2.3.4:1080
socks://user:pass@10.0.0.1:1080
http://1.2.3.4:8080
```

Adjust it in `config.json`:

```json
"uri_output": { "enabled": true, "dir": "uri", "socks_scheme": "socks" }
```

### Format Details

#### JSON
```json
[
  {
    "protocol": "http",
    "host": "1.2.3.4",
    "port": 8080,
    "auth": null,
    "timeout": 0.45,
    "exit_ip": null,
    "response_time": null,
    "country": null
  }
]
```

#### TXT
```
http://1.2.3.4:8080
socks://user:pass@5.6.7.8:1080  # Aliased to socks5
socks5://user:pass@5.6.7.8:1080
```

#### CSV
| protocol | host | port | username | password | timeout | exit_ip | response_time | country |
|----------|------|------|----------|----------|---------|---------|---------------|---------|

## Configuration

Edit `config.json` to change sources, protocols, or output formats:

```json
{
  "sources": [...],
  "output_formats": ["json", "txt", "csv"],
  "output_dir": "output",
  "dedup_strategy": "content",
  "min_response_time": 0.1,
  "protocols_to_include": ["http", "https", "socks4", "socks5"]
}
```

## Architecture

```
main.py
  ├── collector.py          # Core logic
  │   ├── fetch_proxies_from_urls()
  │   ├── deduplicate_proxies()
  │   ├── categorize_proxies()
  │   ├── proxies_to_json()
  │   ├── proxies_to_txt()
  │   └── proxies_to_csv()
  └── src/collector.py      ──►
  └── config.json           # Source URL patterns
```

## Dependencies

- `httpx` - Async HTTP client
- `orjson` - High-performance JSON
- `aiohttp` - (optional fallback)

## License

MIT

## Disclaimer

For educational purposes only. Use responsibly and in compliance with applicable laws.