#!/usr/bin/env node
'use strict';

const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const INPUT_SO = path.join(ROOT, 'byd', 'libwbsk_crypto_tool.so.mem.so');
const OUTPUT_JS = path.join(ROOT, 'wbsk_tables.js');

// Table offsets within the Frida memory dump (RX segment starts at file offset 0x0,
// vaddr 0x0, so file offsets == virtual addresses). Verified via brute-force against
// known encrypt/decrypt test vectors from Xposed hook logs.
const TABLES = Object.freeze({
  // Encrypt byte tables
  encInitXor:  { offset: 0x77b0, length: 256 },
  encRoundXor: { offset: 0x54b0, length: 256 },
  encSbox:     { offset: 0x65b0, length: 256 },
  encFinalXor: { offset: 0x78b0, length: 256 },
  // Encrypt T-tables (ROTR8 rotation group)
  encTe0:      { offset: 0x55b0, length: 1024 },
  encTe1:      { offset: 0x59b0, length: 1024 },
  encTe2:      { offset: 0x5db0, length: 1024 },
  encTe3:      { offset: 0x61b0, length: 1024 },
  // Decrypt byte tables
  decInitXor:  { offset: 0x79b0, length: 256 },
  decRoundXor: { offset: 0x76b0, length: 256 },
  decInvSbox:  { offset: 0x52b0, length: 256 },
  decFinalXor: { offset: 0x7ab0, length: 256 },
  // Decrypt T-tables (ROTR8 rotation group)
  decTd0:      { offset: 0x66b0, length: 1024 },
  decTd1:      { offset: 0x6ab0, length: 1024 },
  decTd2:      { offset: 0x6eb0, length: 1024 },
  decTd3:      { offset: 0x72b0, length: 1024 },
});

function main() {
  const so = fs.readFileSync(INPUT_SO);

  const out = {};
  for (const [name, spec] of Object.entries(TABLES)) {
    const end = spec.offset + spec.length;
    if (end > so.length) {
      throw new Error(`${name} out of range (offset=0x${spec.offset.toString(16)} len=0x${spec.length.toString(16)} filesize=0x${so.length.toString(16)})`);
    }
    out[name] = so.subarray(spec.offset, end).toString('base64');
  }

  const tableLines = Object.entries(TABLES)
    .map(([name, spec]) => ` *   ${name}=0x${spec.offset.toString(16)} len=0x${spec.length.toString(16)}`)
    .join('\n');

  const header = [
    '/**',
    ' * Generated file: embedded WBSK white-box AES table slices for wbsk.js.',
    ' *',
    ' * Generation command:',
    ' *   node scripts/generate_wbsk_tables.js',
    ' *',
    ' * Source binary:',
    ' *   byd/libwbsk_crypto_tool.so.mem.so',
    ' *',
    ' * Extracted table offsets:',
    tableLines,
    ' */',
    "'use strict';",
    '',
  ].join('\n');

  const body = `module.exports = Object.freeze(${JSON.stringify(out, null, 2)});\n`;
  fs.writeFileSync(OUTPUT_JS, header + body, 'utf8');
  console.log(`Wrote ${OUTPUT_JS}`);
}

main();
