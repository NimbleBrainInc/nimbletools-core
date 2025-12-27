#!/usr/bin/env node
/**
 * MCPB Bundle Loader
 *
 * Downloads and extracts MCPB bundles from URLs.
 * Supports SHA256 hash verification for bundle integrity.
 */
const crypto = require('crypto');
const https = require('https');
const http = require('http');
const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

function computeSha256(filePath) {
  const fileBuffer = fs.readFileSync(filePath);
  const hashSum = crypto.createHash('sha256');
  hashSum.update(fileBuffer);
  return hashSum.digest('hex');
}

function download(url, dest) {
  return new Promise((resolve, reject) => {
    const file = fs.createWriteStream(dest);
    const client = url.startsWith('https') ? https : http;

    const request = (requestUrl) => {
      const protocol = requestUrl.startsWith('https') ? https : http;
      protocol.get(requestUrl, (response) => {
        // Handle redirects (GitHub Releases)
        if (response.statusCode === 302 || response.statusCode === 301) {
          request(response.headers.location);
          return;
        }

        if (response.statusCode !== 200) {
          reject(new Error(`HTTP ${response.statusCode}`));
          return;
        }

        response.pipe(file);
        file.on('finish', () => {
          file.close();
          resolve();
        });
      }).on('error', reject);
    };

    request(url);
  });
}

async function loadBundle(url, dest, expectedSha256) {
  fs.mkdirSync(dest, { recursive: true });

  const bundlePath = path.join(dest, 'bundle.mcpb');

  console.log(`Downloading bundle from ${url}...`);
  await download(url, bundlePath);

  const stats = fs.statSync(bundlePath);
  console.log(`Downloaded ${(stats.size / 1024 / 1024).toFixed(1)}MB`);

  // Verify SHA256 if expected hash is provided
  if (expectedSha256) {
    const actualSha256 = computeSha256(bundlePath);
    if (actualSha256.toLowerCase() !== expectedSha256.toLowerCase()) {
      fs.unlinkSync(bundlePath); // Delete invalid bundle
      throw new Error(
        `SHA256 mismatch! Expected: ${expectedSha256}, Got: ${actualSha256}. ` +
        'Bundle may be corrupted or tampered with.'
      );
    }
    console.log(`SHA256 verified: ${actualSha256.substring(0, 16)}...`);
  } else {
    console.log('Warning: No SHA256 hash provided, skipping integrity verification');
  }

  console.log(`Extracting to ${dest}...`);
  execSync(`unzip -o "${bundlePath}" -d "${dest}"`, { stdio: 'inherit' });

  // Clean up
  fs.unlinkSync(bundlePath);

  // Parse manifest
  const manifestPath = path.join(dest, 'manifest.json');
  const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
  console.log(`Loaded: ${manifest.name} v${manifest.version}`);

  return manifest;
}

// Main
const [,, url, dest, expectedSha256] = process.argv;

if (!url || !dest) {
  console.error('Usage: mcpb-loader <bundle_url> <dest_dir> [expected_sha256]');
  process.exit(1);
}

loadBundle(url, dest, expectedSha256 || null)
  .then(manifest => console.log(JSON.stringify(manifest)))
  .catch(err => {
    console.error(`Error loading bundle: ${err.message}`);
    process.exit(1);
  });
