#!/usr/bin/env python3
"""
MCPB Bundle Loader

Downloads and extracts MCPB bundles from URLs.
Uses only Python stdlib for minimal dependencies.
"""
import hashlib
import json
import os
import sys
import urllib.request
import zipfile
from pathlib import Path


def compute_sha256(file_path: Path) -> str:
    """Compute SHA256 hash of a file."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256_hash.update(chunk)
    return sha256_hash.hexdigest()


def download_bundle(url: str, dest: Path, expected_sha256: str | None = None) -> Path:
    """Download bundle from URL with redirect support and optional hash verification."""
    bundle_path = dest / "bundle.mcpb"
    print(f"Downloading bundle from {url}...")

    # Create opener that follows redirects (for GitHub Releases)
    opener = urllib.request.build_opener(urllib.request.HTTPRedirectHandler())
    urllib.request.install_opener(opener)

    urllib.request.urlretrieve(url, bundle_path)
    size_mb = bundle_path.stat().st_size / 1024 / 1024
    print(f"Downloaded {size_mb:.1f}MB")

    # Verify SHA256 if expected hash is provided
    if expected_sha256:
        actual_sha256 = compute_sha256(bundle_path)
        if actual_sha256.lower() != expected_sha256.lower():
            bundle_path.unlink()  # Delete invalid bundle
            raise ValueError(
                f"SHA256 mismatch! Expected: {expected_sha256}, Got: {actual_sha256}. "
                "Bundle may be corrupted or tampered with."
            )
        print(f"SHA256 verified: {actual_sha256[:16]}...")
    else:
        print("Warning: No SHA256 hash provided, skipping integrity verification")

    return bundle_path


def extract_bundle(bundle_path: Path, dest: Path) -> dict:
    """Extract bundle and return manifest."""
    print(f"Extracting to {dest}...")

    with zipfile.ZipFile(bundle_path, 'r') as zf:
        zf.extractall(dest)

    # Clean up bundle file
    bundle_path.unlink()

    # Parse manifest
    manifest_path = dest / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"No manifest.json found in bundle")

    manifest = json.loads(manifest_path.read_text())
    print(f"Loaded: {manifest['name']} v{manifest['version']}")
    return manifest


def load_bundle(url: str, dest: str, expected_sha256: str | None = None) -> dict:
    """Download and extract bundle, return manifest."""
    dest_path = Path(dest)
    dest_path.mkdir(parents=True, exist_ok=True)

    bundle_path = download_bundle(url, dest_path, expected_sha256)
    manifest = extract_bundle(bundle_path, dest_path)

    return manifest


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: mcpb-loader <bundle_url> <dest_dir> [expected_sha256]")
        sys.exit(1)

    try:
        expected_sha256 = sys.argv[3] if len(sys.argv) > 3 else None
        manifest = load_bundle(sys.argv[1], sys.argv[2], expected_sha256)
        # Write manifest path for entrypoint to use
        print(json.dumps(manifest))
    except Exception as e:
        print(f"Error loading bundle: {e}", file=sys.stderr)
        sys.exit(1)
