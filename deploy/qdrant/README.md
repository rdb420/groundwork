# Qdrant for Groundwork

Groundwork runs Qdrant 1.18.2, the release `rdb420/rba420-qdrant` is built on. The fork's only
change is turning TLS on, which the compose file does with environment settings, so the upstream
image is used rather than building the fork's Rust source.

1. Make a certificate for the Qdrant host (a private CA is fine, for example with `step` or
   `mkcert`), and put `cert.pem` and `key.pem` in `deploy/qdrant/tls/`. The certificate must name
   the host Groundwork connects to (`qdrant` inside compose). Don't commit them; the folder's
   `.gitignore` keeps everything but itself out.
2. Copy the CA certificate to `data/qdrant-ca.pem` so Groundwork can verify it
   (`GW_QDRANT_CA_FILE=/data/qdrant-ca.pem`).
3. Set a long random `QDRANT_API_KEY` in `.env` for the container, and the same value in
   `GW_QDRANT_API_KEY` for Groundwork, with `GW_QDRANT_URL=https://qdrant:6333`. Groundwork refuses
   to use Qdrant without a key. The container publishes no ports; Groundwork reaches it inside
   compose.
4. `docker compose --profile pipeline up -d qdrant`

Groundwork creates the collection on first use: `gw_chunks_v1` behind the alias `gw_chunks`
(`GW_QDRANT_COLLECTION`; the `_v1` is the layout version, so a new layout can be built alongside and
switched over). Everything in Qdrant can be rebuilt from Groundwork's database with **Index again**
on the Pipeline page, so it doesn't need its own backup.
