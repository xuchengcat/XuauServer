# Homepage credentials

Copy `secrets.env.example` to `secrets.env` beside it and fill in the values.
Keep `secrets.env` local; Git ignores it. Set its permissions to `600`.

The root `docker-compose.yml` loads this file using `env_file` with
`format: raw`; enter values literally, without surrounding quotes.
Homepage configuration uses `{{HOMEPAGE_VAR_...}}` references.
Variables for commented widgets are kept for future use.

After changing a credential, run from `/mnt/SDD128G`:

```sh
chmod 600 homepage/secrets.env
docker compose up -d --no-deps --force-recreate --pull never homepage
```

Existing Git history may still contain old credentials. Rotate any credentials
that were committed; this migration does not remove historical values.
