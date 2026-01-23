#!/usr/bin/env python3
"""
🔒 SRI Hash Generator - Bybit Strategy Tester v2

Generates Subresource Integrity (SRI) hashes for CDN resources.
Used to ensure CDN resources haven't been tampered with.

Usage:
    python generate_sri_hashes.py

@version 1.0.0
@date 2025-12-21
"""

import base64
import hashlib
import json
import ssl
import urllib.request
from pathlib import Path

# CDN Resources to hash
CDN_RESOURCES = {
    "chart.js": "https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js",
    "chartjs-adapter-date-fns": "https://cdn.jsdelivr.net/npm/chartjs-adapter-date-fns@3.0.0/dist/chartjs-adapter-date-fns.bundle.min.js",
    "bootstrap-icons": "https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.1/font/bootstrap-icons.css",
    "bootstrap-css": "https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css",
    "bootstrap-js": "https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js",
    "lightweight-charts": "https://unpkg.com/lightweight-charts@4.1.0/dist/lightweight-charts.standalone.production.js",
}


def generate_sri_hash(content: bytes, algorithm: str = "sha384") -> str:
    """
    Generate SRI hash for content.

    Args:
        content: Raw bytes of the resource
        algorithm: Hash algorithm (sha256, sha384, sha512)

    Returns:
        SRI hash string (e.g., "sha384-xxxxx")
    """
    if algorithm == "sha256":
        hash_obj = hashlib.sha256(content)
    elif algorithm == "sha384":
        hash_obj = hashlib.sha384(content)
    elif algorithm == "sha512":
        hash_obj = hashlib.sha512(content)
    else:
        raise ValueError(f"Unsupported algorithm: {algorithm}")

    hash_bytes = hash_obj.digest()
    hash_b64 = base64.b64encode(hash_bytes).decode("ascii")

    return f"{algorithm}-{hash_b64}"


def fetch_resource(url: str) -> bytes:
    """
    Fetch resource from URL.

    Args:
        url: URL to fetch

    Returns:
        Raw bytes of the resource
    """
    # Create SSL context that doesn't verify (for development)
    ctx = ssl.create_default_context()

    print(f"  Fetching: {url}")

    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        },
    )

    with urllib.request.urlopen(req, context=ctx, timeout=30) as response:
        return response.read()


def generate_all_hashes():
    """Generate SRI hashes for all CDN resources."""
    print("=" * 60)
    print("🔒 SRI Hash Generator")
    print("=" * 60)
    print()

    results = {}

    for name, url in CDN_RESOURCES.items():
        print(f"📦 {name}")
        try:
            content = fetch_resource(url)
            sri_hash = generate_sri_hash(content)
            results[name] = {"url": url, "integrity": sri_hash, "size": len(content)}
            print(f"  ✅ Hash: {sri_hash[:50]}...")
            print(f"  📊 Size: {len(content):,} bytes")
        except Exception as e:
            print(f"  ❌ Error: {e}")
            results[name] = {"url": url, "integrity": None, "error": str(e)}
        print()

    return results


def save_results(results: dict, output_path: Path):
    """Save results to JSON file."""
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"💾 Results saved to: {output_path}")


def generate_html_snippets(results: dict):
    """Generate ready-to-use HTML snippets."""
    print("\n" + "=" * 60)
    print("📋 HTML Snippets (copy-paste ready)")
    print("=" * 60 + "\n")

    # CSS links
    print("<!-- CSS Resources with SRI -->")
    for name, data in results.items():
        if data.get("integrity") and data["url"].endswith(".css"):
            print(f'<link rel="stylesheet" href="{data["url"]}"')
            print(f'      integrity="{data["integrity"]}"')
            print('      crossorigin="anonymous">')
            print()

    # JS scripts
    print("<!-- JavaScript Resources with SRI -->")
    for name, data in results.items():
        if data.get("integrity") and data["url"].endswith(".js"):
            print(f'<script src="{data["url"]}"')
            print(f'        integrity="{data["integrity"]}"')
            print('        crossorigin="anonymous"></script>')
            print()


def generate_csp_meta_tag():
    """Generate CSP meta tag."""
    print("\n" + "=" * 60)
    print("🛡️ Content Security Policy Meta Tag")
    print("=" * 60 + "\n")

    csp = """<meta http-equiv="Content-Security-Policy" content="
    default-src 'self';
    script-src 'self' https://cdn.jsdelivr.net https://unpkg.com;
    style-src 'self' https://cdn.jsdelivr.net https://fonts.googleapis.com 'unsafe-inline';
    img-src 'self' data: https:;
    font-src 'self' https://cdn.jsdelivr.net https://fonts.gstatic.com;
    connect-src 'self' https://api.bybit.com wss://stream.bybit.com ws://localhost:* http://localhost:*;
    frame-src 'none';
    object-src 'none';
    base-uri 'self';
    form-action 'self';
    frame-ancestors 'none';
">"""

    print(csp)
    print()

    # Single-line version
    print("<!-- Single-line version: -->")
    csp_single = csp.replace("\n", " ").replace("    ", " ")
    while "  " in csp_single:
        csp_single = csp_single.replace("  ", " ")
    print(csp_single)


def main():
    """Main entry point."""
    # Generate hashes
    results = generate_all_hashes()

    # Save to JSON
    output_path = Path(__file__).parent / "sri_hashes.json"
    save_results(results, output_path)

    # Generate HTML snippets
    generate_html_snippets(results)

    # Generate CSP
    generate_csp_meta_tag()

    print("\n" + "=" * 60)
    print("✅ Done!")
    print("=" * 60)


if __name__ == "__main__":
    main()
