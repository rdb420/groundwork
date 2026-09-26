# Self-hosted Supabase Storage for Groundwork

Groundwork keeps originals, converted Markdown and images, and session audio in object storage
when `GW_STORAGE_BACKEND=s3`. It only uses Supabase Storage's S3 endpoint, so the rest of the Supabase
stack (Postgres, Studio, Auth) can stay as Supabase ships it.

1. Run Supabase's self-hosted Docker stack on the office host or the inference box
   (https://supabase.com/docs/guides/self-hosting/docker). Keep it on the private network or the
   tailnet; don't publish Studio or the API to the internet.
2. In the stack's `.env`, set `S3_PROTOCOL_ACCESS_KEY_ID` and `S3_PROTOCOL_ACCESS_KEY_SECRET` to
   long random values, and note `REGION` (defaults to `stub` in some versions).
3. In Studio, create a private bucket called `groundwork`.
4. In Groundwork's `.env`:

   ```
   GW_STORAGE_BACKEND=s3
   GW_S3_ENDPOINT=http://<supabase-host>:8000/storage/v1/s3
   GW_S3_REGION=<REGION from step 2>
   GW_S3_BUCKET=groundwork
   GW_S3_ACCESS_KEY=<S3_PROTOCOL_ACCESS_KEY_ID>
   GW_S3_SECRET_KEY=<S3_PROTOCOL_ACCESS_KEY_SECRET>
   ```

   If the endpoint uses HTTPS with a private CA, also set `GW_S3_CA_FILE` to that CA's certificate.

5. Check it: `cd backend && uv run python -m scripts.check_providers`.

Groundwork's nightly backup covers its database only when files live in S3. Back up the Supabase
stack's storage volume separately, encrypted, as for Groundwork's own backups.

Files already stored locally stay readable only from local storage. Move them before switching
(copy `data/artifacts` and `data/recordings` into the bucket under the same keys), then switch.
