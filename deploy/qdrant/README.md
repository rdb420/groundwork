# Qdrant for Groundwork

Groundwork runs Qdrant 1.18.2, the release `rdb420/rba420-qdrant` is built on. The fork's only
change is turning TLS on, which the compose file does with environment settings, so the upstream
image is used rather than building the fork's Rust source.

1. Make a certificate for the Qdrant host (a private CA is fine, for example with `step` or
   `mkcert`), and put `cert.pem` and `key.pem` in `deploy/qdrant/tls/`. Don't commit them.
2. Copy the CA certificate to `data/qdrant-ca.pem` so Groundwork can verify it
   (`GW_QDRANT_CA_FILE=/data/qdrant-ca.pem`).
3. Set a long random `QDRANT_API_KEY` in `.env`. Groundwork sends it as `GW_QDRANT_API_KEY`.
4. `docker compose --profile pipeline up -d qdrant`

Groundwork creates the collection (`gw_chunks_v1`, alias `gw_chunks`) on first use. Everything
in Qdrant can be rebuilt from Groundwork's database with the admin "Reprocess" action, so it
doesn't need its own backup.
