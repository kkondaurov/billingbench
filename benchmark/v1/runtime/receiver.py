#!/usr/bin/env python3
"""The published local GL receiver, with externally selected one-shot transport faults."""

import argparse
import hashlib
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import socket
import threading
from urllib.parse import unquote
import uuid


class Store:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()
        self.path = self.root / "accepted.json"
        self.accepted = json.loads(self.path.read_text()) if self.path.exists() else {}
        self.fault = self.root / "next-fault"
        self.requests = []

    def accept(self, tenant, batch, body):
        with self.lock:
            fault = self.fault.read_text().strip() if self.fault.exists() else None
            if fault:
                self.fault.unlink()
            self.requests.append(dict(tenant=tenant, batch=batch, fault=fault))
            if fault == "before_accept":
                return None, None
            if fault == "unavailable":
                return 503, {"error": "unavailable"}
            try:
                payload, digest = body["payload"], body["digest"]
                assert isinstance(payload, str) and isinstance(digest, str)
                assert hashlib.sha256(payload.encode()).hexdigest() == digest
                data = json.loads(payload)
                assert data["tenant_key"] == tenant and data["batch_key"] == batch
                assert data["currency"] in ("USD", "EUR") and isinstance(data["entries"], list)
                assert data["entries"]
                for entry in data["entries"]:
                    assert all(k in entry for k in ("key", "posting_date", "economic_date", "effect_key", "scope_key", "configuration_key", "lines"))
                    assert isinstance(entry["lines"], list) and entry["lines"]
                    for line in entry["lines"]:
                        assert all(k in line for k in ("key", "configuration_key", "account_key", "segments", "debit_minor", "credit_minor"))
                        assert isinstance(line["segments"], dict)
                        debit, credit = line["debit_minor"], line["credit_minor"]
                        assert type(debit) is int and type(credit) is int and debit >= 0 and credit >= 0
                        assert not (debit and credit)
            except (KeyError, ValueError, TypeError, AssertionError):
                return 422, {"error": "invalid_payload"}
            key = json.dumps([tenant, batch])
            previous = self.accepted.get(key)
            if previous and (previous["payload"] != payload or previous["digest"] != digest):
                return 409, {"error": "conflict"}
            if not previous:
                previous = dict(status="accepted", acknowledgement_id=uuid.uuid4().hex, digest=digest, payload=payload)
                self.accepted[key] = previous
                self.path.write_text(json.dumps(self.accepted, indent=2) + "\n")
                status = 201
            else:
                status = 200
            if fault == "after_accept":
                return None, None
            return status, {k: v for k, v in previous.items() if k != "payload"}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def target(self):
        parts = self.path.split("/")
        if len(parts) == 5 and parts[1] == "tenants" and parts[3] == "batches":
            return unquote(parts[2]), unquote(parts[4])
        return None

    def reply(self, status, body):
        if status is None:
            self.close_connection = True
            self.connection.shutdown(socket.SHUT_RDWR)
            return
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/health":
            return self.reply(200, {"status": "ok"})
        target = self.target()
        if target:
            record = self.server.store.accepted.get(json.dumps(list(target)))
            if record:
                return self.reply(200, {k: v for k, v in record.items() if k != "payload"})
        self.reply(404, {"error": "not_found"})

    def do_PUT(self):
        target = self.target()
        if target is None:
            return self.reply(404, {"error": "not_found"})
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))))
        except (ValueError, TypeError):
            return self.reply(422, {"error": "invalid_payload"})
        self.reply(*self.server.store.accept(*target, body))


def server(root, host="127.0.0.1", port=0):
    service = ThreadingHTTPServer((host, port), Handler)
    service.store = Store(root)
    return service


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", required=True)
    parser.add_argument("--port", type=int, default=4100)
    args = parser.parse_args()
    server(args.state, "0.0.0.0", args.port).serve_forever()
