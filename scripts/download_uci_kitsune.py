#!/usr/bin/env python3
"""
UCI Kitsune Network Attack Dataset Downloader

Downloads the official UCI Kitsune dataset (17.7 GB zip) into data/kitsune/.
Uses the official UCI source only.

Usage:
    python scripts/download_uci_kitsune.py

Output:
    data/kitsune/<attack_name>/<attack>_dataset.csv
    data/kitsune/<attack_name>/<attack>_labels.csv

Official source:
    https://archive.ics.uci.edu/dataset/516/kitsune+network+attack+dataset
    DOI: 10.24432/C5D90Q
"""

import hashlib
import os
import sys
import tempfile
import time
import urllib.request
import zipfile

DATA_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "kitsune")
UCI_URL = "https://archive.ics.uci.edu/static/public/516/kitsune+network+attack+dataset.zip"
ZIP_FILENAME = "kitsune_network_attack_dataset.zip"
ZIP_EXPECTED_SIZE_GB = 17.7
ZIP_EXPECTED_SHA256 = None  # Fill after download verification

def download_file(url, dest, chunk_size=8192):
    start = time.time()
    downloaded = 0
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=300) as resp:
        total = int(resp.headers.get("Content-Length", 0))
        print(f"  Size: {total / 1e9:.1f} GB")
        print(f"  Downloading to: {dest}")
        with open(dest, "wb") as f:
            while True:
                chunk = resp.read(chunk_size)
                if not chunk:
                    break
                f.write(chunk)
                downloaded += len(chunk)
                if total > 0:
                    pct = downloaded / total * 100
                    elapsed = time.time() - start
                    speed = downloaded / elapsed / 1e6 if elapsed > 0 else 0
                    print(f"  {downloaded/1e6:.0f}/{total/1e6:.0f} MB ({pct:.1f}%) @ {speed:.1f} MB/s", end="\r")
    print()
    return downloaded

def main():
    os.makedirs(DATA_ROOT, exist_ok=True)
    zip_path = os.path.join(DATA_ROOT, ZIP_FILENAME)

    print("=" * 60)
    print("UCI Kitsune Network Attack Dataset Downloader")
    print("=" * 60)
    print()
    print(f"Source: {UCI_URL}")
    print(f"Destination: {zip_path}")
    print(f"Expected size: ~{ZIP_EXPECTED_SIZE_GB} GB (compressed)")
    print()

    if os.path.isfile(zip_path):
        print(f"Zip already exists at: {zip_path}")
        proceed = input("Re-download? (y/N): ").strip().lower()
        if proceed != "y":
            print("Skipping download. Extracting or using existing...")
        else:
            os.remove(zip_path)
            download_file(UCI_URL, zip_path)
    else:
        print("Starting download (this may take a very long time)...")
        print("Note: If download fails, try manually downloading from:")
        print(f"  {UCI_URL}")
        print()
        try:
            download_file(UCI_URL, zip_path)
        except Exception as e:
            print(f"\nERROR: Download failed: {e}")
            print()
            print("Manual download instructions:")
            print(f"  1. Visit: https://archive.ics.uci.edu/dataset/516/kitsune+network+attack+dataset")
            print(f"  2. Click 'Download' button (or use direct link below)")
            print(f"  3. Save the zip file to: {zip_path}")
            print(f"  4. Re-run this script to extract")
            sys.exit(1)

    # Verify SHA-256 (if we have it)
    if ZIP_EXPECTED_SHA256:
        print("Verifying checksum...")
        h = hashlib.sha256()
        with open(zip_path, "rb") as f:
            while True:
                chunk = f.read(65536)
                if not chunk:
                    break
                h.update(chunk)
        actual = h.hexdigest().upper()
        if actual == ZIP_EXPECTED_SHA256:
            print("  SHA-256 match!")
        else:
            print(f"  WARNING: SHA-256 mismatch!")
            print(f"  Expected: {ZIP_EXPECTED_SHA256}")
            print(f"  Actual:   {actual}")
            proceed = input("Continue anyway? (y/N): ").strip().lower()
            if proceed != "y":
                sys.exit(1)

    # Extract zip
    print(f"Extracting to: {DATA_ROOT}")
    with zipfile.ZipFile(zip_path, "r") as zf:
        # Zip contents expected to have directory structure:
        # <attack_name>/<attack>_dataset.csv
        # <attack_name>/<attack>_labels.csv
        # <attack_name>/<attack>_pcap.pcapng
        for name in zf.namelist():
            zf.extract(name, DATA_ROOT)

    print()
    print("Extraction complete!")
    print(f"Files extracted to: {DATA_ROOT}")

    # List attacks found
    attacks = sorted(os.listdir(DATA_ROOT))
    attacks = [a for a in attacks if os.path.isdir(os.path.join(DATA_ROOT, a)) and a != "__MACOSX"]
    if attacks:
        print(f"Attack directories found: {len(attacks)}")
        for a in attacks:
            files = os.listdir(os.path.join(DATA_ROOT, a))
            csv_files = [f for f in files if f.endswith(".csv")]
            print(f"  {a}/: {len(csv_files)} CSV files")
    else:
        print("No attack directories found. Check zip contents manually.")

    print()
    print("Done! You can now run the experiment:")
    print("  python scripts/run_experiment.py")

if __name__ == "__main__":
    main()
