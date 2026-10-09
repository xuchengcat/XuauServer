# 🚗 BYD Reverse Engineering

Reverse engineering of the BYD app HTTP crypto path used in the Android apps.

Base hosts:
- Overseas app (`com.byd.bydautolink`): `https://dilinkappoversea-eu.byd.auto`
- CN app (`com.byd.aeri.caranywhere`): `https://dilinksuperappserver-cn.byd.auto`

## 🔗 Related Projects

- [`pyBYD`](https://github.com/jkaberg/pyBYD): full Python library built from these reverse-engineering findings.
- [`hass-byd-vehicle`](https://github.com/jkaberg/hass-byd-vehicle): Home Assistant integration for BYD vehicles.

## 🚀 Quickstart

`client.js` is the main entrypoint. Prerequisite: Node.js 20+.

> **Warning:** Do not commit real credentials, raw personal logs, or decrypted personal data. `.env` and hook logs can contain plaintext identifiers and passwords.

### Overseas

Create `.env`:

```dotenv
BYD_USERNAME=you@example.com
BYD_PASSWORD=your-password
```

Run:

```bash
node client.js
```

### CN (China)

```dotenv
BYD_BASE_URL=https://dilinksuperappserver-cn.byd.auto
BYD_USERNAME=13100000000
BYD_PASSWORD=YourPassword
```

```bash
node client.js
```

CN mode is auto-detected from the `BYD_BASE_URL` hostname (`cn.byd.auto`).

### Output

The client performs login, resolves the MQTT broker and prints ready-to-use `mosquitto_sub` commands, fetches your vehicle list, polls real-time vehicle status, and retrieves GPS info. It also writes a self-contained dashboard to `status.html`.

![Status dashboard screenshot](screenshot.png)

The client accepts many `BYD_*` environment variable overrides (`BYD_COUNTRY_CODE`, `BYD_LANGUAGE`, `BYD_VIN`, `BYD_BASE_URL`, `BYD_TARGET_BRAND`, etc.) — see the top of `client.js` for the full list and defaults.

## 🗺️ Project Map

- `client.js`: login + vehicle list + realtime poll + GPS + MQTT info (overseas & CN).
- `bangcle.js`: Bangcle envelope encode/decode (overseas app).
- `bangcle_auth_tables.js`: embedded Bangcle auth tables.
- `wbsk.js`: WBSK white-box AES-256 encrypt/decrypt (CN app).
- `wbsk_tables.js`: embedded WBC lookup tables for `wbsk.js`.
- `decompile.js`: decoder/encoder CLI (debugging/analysis; supports both bangcle and WBSK envelopes).
- `mqtt_decode.js`: streaming MQTT payload decoder (AES-128-CBC, hex input → JSON output).
- `URLs.md`: discovered API URL inventory (observed in logs + static `class.dex` candidates).
- `scripts/generate_bangcle_auth_tables.js`: Bangcle table generator from `byd/libencrypt.so.mem.so`.
- `scripts/generate_wbsk_tables.js`: WBSK table generator from `byd/libwbsk_crypto_tool.so.mem.so`.
- `scripts/test_wbsk.js`: WBSK test harness (encrypt, decrypt, envelope roundtrip tests).
- `xposed/http.sh`: decode helper for `HTTP method=` log lines.
- `xposed/log.sh`: Xposed capture loop.
- `xposed/src/*`: Xposed hook module source (Java hooks, resources, manifest).

## 📱 App & Transport Snapshot

- Apps: BYD overseas Android app (`com.byd.bydautolink`) and CN app (`com.byd.aeri.caranywhere`).
- Hooking compatibility: `2.9.1` is the latest overseas APK version that can be reliably hooked in this setup. Newer versions add Magisk/Zygote/LSPosed/root detection.
- Hookable APK (`2.9.1`): [APKPure download](https://apkpure.com/byd/com.byd.bydautolink/download/2.9.1)
- Client stack: Android + OkHttp (`user-agent: okhttp/4.12.0`).
- API pattern: JSON-over-HTTP POST with encrypted payload wrapper.

Common request characteristics observed in hooks and mirrored by `client.js`:
- `content-type: application/json; charset=UTF-8`
- `accept-encoding: identity`
- `user-agent: okhttp/4.12.0`
- cookie-backed session reuse across calls (client stores and replays returned cookies)
- CN mode adds headers: `version`, `platform: ANDROID`, `BrandFlag: dynasty`

## 🔐 Crypto Pipeline

Both apps share the same HTTP wrapper and inner AES-128-CBC business payload, but differ in the outer envelope crypto layer.

### 1. HTTP wrapper

Request body: `{"request":"<envelope>"}`. Response body: `{"response":"<envelope>"}`.

### 2a. Bangcle envelope (`bangcle.js`, overseas app)

- Format: `F` + Base64 ciphertext.
- Table-driven Bangcle white-box AES using embedded auth tables from `bangcle_auth_tables.js`.
- CBC mode, zero IV, PKCS#7 padding.
- Decoding strips the `F` prefix, Base64-decodes, decrypts, and removes PKCS#7.

After decoding, the outer JSON payload typically looks like:

```json
{
  "countryCode": "NL",
  "identifier": "<username-or-userId>",
  "imeiMD5": "<md5-hex>",
  "language": "en",
  "reqTimestamp": "<millis>",
  "sign": "<sha1Mixed>",
  "encryData": "<AES-CBC hex>",
  "checkcode": "<md5-reordered>"
}
```

Response-side decoded outer payload:

```json
{
  "code": "0",
  "message": "SUCCESS",
  "identifier": "<userId-or-countryCode>",
  "respondData": "<AES-CBC hex>"
}
```

For a full field-level description and mapping reference, see [`pyBYD/API_MAPPING.md`](https://github.com/jkaberg/pyBYD/blob/main/API_MAPPING.md).

### 2b. WBSK envelope (`wbsk.js`, CN app)

The CN app uses a two-layer white-box AES-256 envelope instead of Bangcle.

- Format: Base64 of `version_byte(0x93) + IV(16 bytes) + ciphertext`.
- Two nested layers (outer wraps inner), each using WBC AES-256 in CBC mode.
- Nibble-encoding layer: per-byte nibble substitution between plaintext and WBC domain.
- All WBC keys are static (device-bound, not per-session). Hardcoded in `wbsk.js` as `WBSK_KEYS`.
- `decompile.js` automatically attempts WBSK decryption for non-bangcle, non-JSON payloads.
- `client.js` uses `wbsk.encryptEnvelope()` / `wbsk.decryptEnvelope()` for CN mode.

After decoding, the CN outer JSON payload looks like:

```json
{
  "appChannel": "99",
  "identifier": "<superId-or-phone>",
  "identifierType": 0,
  "imeiMD5": "<md5-hex>",
  "reqTimestamp": "<millis>",
  "sign": "<sha1Mixed>",
  "encryData": "<AES-CBC hex>",
  "targetBrand": "1",
  "vehicleBrand": "1",
  "checkcode": "<sha256-hex>"
}
```

### 3. Inner business payload (`encryData` / `respondData`)

- Fields are uppercase hex AES-128-CBC (zero IV).
- Config endpoints (e.g. `/app/config/getAllBrandCommonConfig`) use static `CONFIG_KEY`.
- `/app/account/getAccountState` uses `MD5(identifier)`.
- Login key: `MD5(MD5(password).toUpperCase())`.
- Remote control command password (`commandPwd`) uses uppercase `MD5(<operation PIN>)` (e.g. `123456` → `E10ADC3949BA59ABBE56E057F20F883E`), used by `/vehicle/vehicleswitch/verifyControlPassword` and `/control/remoteControl`.
- Token field naming differs by app build:
  - overseas app responses use `token.encryToken`
  - CN responses can use `token.encryptToken`
- Post-login payloads use token-derived keys from `respondData.token`:
  - content key: `MD5(contentToken)` for `encryData` / `respondData` (`contentToken` = `encryToken` or `encryptToken`)
  - sign key: `MD5(signToken)` for `sign`

### 4. Signature and checkcode

- Password-login style flows use raw password-derived sign input (`sha1Mixed(buildSignString(..., md5(password)))`).
- Post-login sign uses token-derived sign key.
- Overseas app `checkcode` is computed from `MD5(JSON.stringify(outerPayload))` with reordered chunks:
  `[24:32] + [8:16] + [16:24] + [0:8]`
- CN app `checkcode` uses `SHA-256(JSON.stringify(outerPayload))` over the augmented request JSON before envelope encryption.

### 5. CN vs Overseas endpoint differences

| Function | Overseas endpoint | CN endpoint |
|----------|------------------|-------------|
| Login | `/app/account/login` | `/app/auth/login` |
| Vehicle list | `/app/account/getAllListByUserId` | `/app/auth/getAllListByUserId` |
| Vehicle realtime | `/vehicleInfo/vehicle/vehicleRealTimeRequest` | same |
| GPS | `/control/getGpsInfo` + `/control/getGpsInfoResult` (poll) | `/vehicleInfo/gps/locationRequestService` (single request) |
| MQTT broker | `/app/emqAuth/getEmqBrokerIp` | same |

CN login returns `token.superId` and `superBindRelationDtoMap` for brand-specific user IDs. Vehicle list response is wrapped in `{diLinkAutoInfoList: [...]}`.

## 📡 MQTT Real-Time Vehicle Telemetry

BYD uses an [EMQ](https://www.emqx.io/)-based MQTT broker to push real-time vehicle data to connected clients via MQTTv5 over TLS (port 8883). The broker hostname is fetched after login via `POST /app/emqAuth/getEmqBrokerIp`.

| Parameter | Overseas | CN |
|-----------|----------|----|
| **Broker field** | `emqBroker` (or `emqBorker`) | `dynastyEmqBroker` / `oceanEmqBroker` / etc. (by brand) |
| **Client ID** | `oversea_<IMEI_MD5>` | `dynasty_<IMEI_MD5>` |
| **Username** | `userId` | `superId` (or brand `userId`) |
| **Password** | `<tsSeconds>` + `MD5(signToken + clientId + userId + tsSeconds)` | same formula |
| **Topic** | `/oversea/res/<userId>` | `/dynasty/res/<superId>` |

All MQTT payloads use the same encryption as `encryData`/`respondData`: hex-encoded AES-128-CBC, zero IV, key = `MD5(contentToken)`.

`client.js` prints ready-to-use `mosquitto_sub` commands after login. Example:

```bash
mosquitto_sub -V mqttv5 \
  -L 'mqtts://<userId>:<password>@<broker>/oversea/res/<userId>' \
  -i 'oversea_<IMEI_MD5>' \
  -F '%p' \
  | node ./mqtt_decode.js '<MD5(contentToken)>'
```

## 🧪 Debugging / Offline Decode (`decompile.js`)

Decode one payload:

```bash
node decompile.js http-dec '<payload>'
```

Accepted input:
- raw Bangcle envelope ciphertext (`F` + Base64/Base64URL payload, overseas format)
- WBSK envelope ciphertext (Base64, CN format — auto-detected)
- full JSON body such as `{"request":"..."}` or `{"response":"..."}`
- raw inner hex ciphertext

Common options:

```bash
node decompile.js http-dec '<payload>' --debug
node decompile.js http-dec '<payload>' --state-file /tmp/byd_state.json
```

Encrypt inner JSON with `md5(identifier)` key:

```bash
node decompile.js http-enc '{"k":"v"}' --identifier <id>
```

Decode full hook flow:

```bash
./xposed/http.sh /path/to/raw_hooks.log
```

`xposed/http.sh` sources `.env` for `BYD_PASSWORD` (used to derive the CN login bootstrap key) and creates a temporary per-run decode-state file so keys learned from login are reused for later calls in the same flow.

## 🧩 Internals

### Decoder Key Strategy

`http-dec` inner-field decryption order:
1. static AES keys (`CONFIG_KEY`, `CN_GUEST_KEY`)
2. CN password bootstrap key (`md5(MD5(password).toUpperCase())`) when `BYD_PASSWORD` is set
3. learned state keys
4. `md5(identifier)` when identifier is known from parsed outer payload

State behavior:
- default file: `/tmp/byd_http_dec_state.json`
- override: `BYD_DECODE_STATE_FILE` or `--state-file`
- auto-learns `contentKey = MD5(token.encryToken)` or `MD5(token.encryptToken)` from decoded login `respondData`

### Bangcle Tables

Runtime uses embedded tables only — `bangcle.js` does not read `.so` files at runtime.

`bangcle_auth_tables.js` is generated from `byd/libencrypt.so.mem.so`:

```bash
node scripts/generate_bangcle_auth_tables.js
```

### WBSK Tables

Runtime uses embedded tables only — `wbsk.js` does not read `.so` files at runtime.

`wbsk_tables.js` is generated from `byd/libwbsk_crypto_tool.so.mem.so`:

```bash
node scripts/generate_wbsk_tables.js
```

Run WBSK tests:

```bash
node scripts/test_wbsk.js
```
