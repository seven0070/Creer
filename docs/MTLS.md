# Mutual TLS (optional transport trust)

HMAC peer trust (v1.2) signs JSON payloads. **mTLS (v1.3)** secures the HTTP transport between Creer registries. Use both when you want signed payloads *and* encrypted peer channels.

## Generate local certs

```bash
chmod +x scripts/gen-dev-certs.sh scripts/run_backend.sh
./scripts/gen-dev-certs.sh
# → certs/ca.pem, server.pem, server-key.pem, client.pem, client-key.pem
```

`certs/*.pem` are gitignored.

## Run a TLS server

```bash
cd backend
export CREER_SSL_CERTFILE=../certs/server.pem
export CREER_SSL_KEYFILE=../certs/server-key.pem
export CREER_OFFLINE=1
../scripts/run_backend.sh
# listens on https://127.0.0.1:8000
```

## Outbound mTLS to peers

On the caller:

```bash
export CREER_SSL_CA_CERTS=../certs/ca.pem
export CREER_SSL_CLIENT_CERT=../certs/client.pem
export CREER_SSL_CLIENT_KEY=../certs/client-key.pem
export CREER_SSL_VERIFY=true
export CREER_REGISTRY_PEERS=https://peer.example:8443
export CREER_ALLOW_PRIVATE_PEERS=1   # only if peers are on localhost/private nets
```

Federation uses `app/http_client.peer_httpx_client()` so all peer probe/registry/discover calls pick up these settings.

## Docker Compose

Default `docker compose up --build` is **HTTP** for easy demos (two peers on 8000/8001 with shared HMAC secret).

For mTLS in containers, mount `./certs` and set the `CREER_SSL_*` variables on each service (and point peers at `https://…`). Uvicorn needs cert/key paths inside the container; prefer a custom command:

```yaml
command: >
  uvicorn main:app --host 0.0.0.0 --port 8000
  --ssl-certfile /certs/server.pem
  --ssl-keyfile /certs/server-key.pem
```

## Notes

- Marketplace/Open VSX publishing is unrelated — see `RELEASE.md`.
- Disabling `CREER_SSL_VERIFY` is for broken local experiments only.
- Production: use a real CA, short-lived certs, and pin peer allowlists.
