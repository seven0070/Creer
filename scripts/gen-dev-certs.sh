#!/usr/bin/env bash
# Generate local CA + server/client certs for Creer mTLS experiments.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CERT_DIR="${CREER_CERT_DIR:-$ROOT/certs}"
mkdir -p "$CERT_DIR"

CN_SERVER="${CREER_CERT_SERVER_CN:-localhost}"
CN_CLIENT="${CREER_CERT_CLIENT_CN:-creer-client}"

echo "Writing certs to $CERT_DIR"

openssl req -x509 -newkey rsa:2048 -nodes -days 3650 \
  -keyout "$CERT_DIR/ca-key.pem" \
  -out "$CERT_DIR/ca.pem" \
  -subj "/CN=Creer Dev CA"

openssl req -newkey rsa:2048 -nodes \
  -keyout "$CERT_DIR/server-key.pem" \
  -out "$CERT_DIR/server.csr" \
  -subj "/CN=$CN_SERVER"

openssl x509 -req -in "$CERT_DIR/server.csr" -days 825 \
  -CA "$CERT_DIR/ca.pem" -CAkey "$CERT_DIR/ca-key.pem" -CAcreateserial \
  -out "$CERT_DIR/server.pem" \
  -extfile <(printf "subjectAltName=DNS:localhost,DNS:creer-a,DNS:creer-b,IP:127.0.0.1")

openssl req -newkey rsa:2048 -nodes \
  -keyout "$CERT_DIR/client-key.pem" \
  -out "$CERT_DIR/client.csr" \
  -subj "/CN=$CN_CLIENT"

openssl x509 -req -in "$CERT_DIR/client.csr" -days 825 \
  -CA "$CERT_DIR/ca.pem" -CAkey "$CERT_DIR/ca-key.pem" -CAcreateserial \
  -out "$CERT_DIR/client.pem"

rm -f "$CERT_DIR"/*.csr "$CERT_DIR"/*.srl
chmod 600 "$CERT_DIR"/*-key.pem

echo "Done."
echo "  CA:     $CERT_DIR/ca.pem"
echo "  Server: $CERT_DIR/server.pem + server-key.pem"
echo "  Client: $CERT_DIR/client.pem + client-key.pem"
echo "See docs/MTLS.md for wiring into uvicorn / peer clients."
