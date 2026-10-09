#!/usr/bin/env node
'use strict';

const fs = require('node:fs/promises');
const { execFile } = require('node:child_process');
const { promisify } = require('node:util');

const execFileAsync = promisify(execFile);
const dataPath = '/data/status.json';
const pollMinutes = Number(process.env.BYD_POLL_MINUTES || '60');

if (!Number.isInteger(pollMinutes) || pollMinutes < 15) {
  console.error('BYD_POLL_MINUTES must be an integer of at least 15');
  process.exit(1);
}

let stopping = false;
process.on('SIGTERM', () => { stopping = true; });
process.on('SIGINT', () => { stopping = true; });

async function wait(ms) {
  const deadline = Date.now() + ms;
  while (!stopping && Date.now() < deadline) {
    await new Promise((resolve) => setTimeout(resolve, Math.min(1000, deadline - Date.now())));
  }
}

async function main() {
  await fs.mkdir('/data', { recursive: true, mode: 0o700 });
  while (!stopping) {
    if (!process.env.BYD_USERNAME || !process.env.BYD_PASSWORD) {
      console.log('BYD credentials are not configured; waiting for container recreation');
      await wait(60_000);
      continue;
    }
    try {
      const { stdout } = await execFileAsync(process.execPath, ['/app/client.js', '--safe-json'], {
        cwd: '/app',
        env: { ...process.env, BYD_SAFE_OUTPUT: '1' },
        timeout: 120_000,
        maxBuffer: 4 * 1024 * 1024,
      });
      const data = JSON.parse(stdout);
      if (!data.vehicleInfo || !data.vin) throw new Error('missing vehicle data');
      const tempPath = `${dataPath}.tmp`;
      await fs.writeFile(tempPath, JSON.stringify(data), { mode: 0o600 });
      await fs.rename(tempPath, dataPath);
      console.log(`Vehicle status saved at ${data.fetchedAt}`);
    } catch (error) {
      // Upstream stderr can contain account identifiers or decrypted responses.
      console.error(`Vehicle status fetch failed (${error.code || error.name || 'invalid response'})`);
    }
    await wait(pollMinutes * 60_000);
  }
}

main().catch((error) => {
  console.error(`Runner failed: ${error.message}`);
  process.exit(1);
});
