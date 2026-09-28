"""Public HTTP observations. No candidate database or implementation access."""

import base64
import hashlib
import hmac
import json
import time
import uuid
from urllib.error import HTTPError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from .checks import equal, require


def token(secret, tenant_id=None, role="admin", customer_id=None):
    payload = json.dumps(dict(tenant_id=tenant_id, role=role, customer_id=customer_id),
                         separators=(",", ":")).encode()
    encoded = base64.urlsafe_b64encode(payload).rstrip(b"=")
    signature = hmac.new(secret.encode(), encoded, hashlib.sha256).digest()
    return (encoded + b"." + base64.urlsafe_b64encode(signature).rstrip(b"=")).decode()


def identifier(value):
    return quote(str(value), safe="")


class API:
    def __init__(self, base_url, secret, tenant=None, role="admin", customer=None,
                 trace=None, clock="2028-01-01T12:00:00Z", timeout=60):
        self.base_url, self.secret, self.tenant = base_url.rstrip("/"), secret, tenant
        self.role, self.customer, self.clock = role, customer, clock
        self.trace = trace if trace is not None else []
        self.timeout = timeout

    def actor(self, role="admin", customer=None, tenant=None):
        return API(self.base_url, self.secret, tenant or self.tenant, role, customer,
                   self.trace, self.clock, self.timeout)

    def at(self, day):
        self.clock = day if "T" in day else day + "T12:00:00Z"
        return self

    def request(self, method, path, body=None, status=None, key=None, version=None,
                headers=None, authenticated=True):
        # Version 0.2 specifies completion in the envelope, not 200 versus 201.
        if method in ("POST", "PUT") and status in (200, 201) and not path.endswith(("preview", "previews")):
            status = (200, 201)
        elif method in ("POST", "PUT") and isinstance(status, tuple) and 200 in status and 201 not in status:
            status = (*status, 201)
        route = path if path.startswith("/api/") or path == "/health" else (
            f"/api/tenants/{identifier(self.tenant)}" + path)
        hdr = {"Accept": "application/json"}
        if authenticated:
            hdr["Authorization"] = "Bearer " + token(self.secret, self.tenant, self.role, self.customer)
        if method != "GET":
            hdr.update({"Content-Type": "application/json", "X-Business-Time": self.clock})
            if not path.endswith(("preview", "previews")):
                hdr["Idempotency-Key"] = key or str(uuid.uuid4())
        if version is not None:
            hdr["If-Match"] = str(version)
        hdr.update(headers or {})
        data = None if body is None else json.dumps(body, separators=(",", ":")).encode()
        start = time.monotonic()
        req = Request(self.base_url + route, data=data, headers=hdr, method=method)
        try:
            response = urlopen(req, timeout=self.timeout)
        except HTTPError as exc:
            response = exc
        raw = response.read()
        code = response.status
        try:
            result = json.loads(raw)
        except (ValueError, UnicodeDecodeError):
            result = {"_invalid_json": raw[:2000].decode(errors="replace")}
        self.trace.append({"method": method, "path": route, "body": body,
                           "business_time": self.clock, "idempotency_key": hdr.get("Idempotency-Key"),
                           "if_match": hdr.get("If-Match"), "actor": self.role,
                           "status": code, "response": result,
                           "seconds": round(time.monotonic() - start, 4)})
        if status is not None:
            operation = result.get("operation") if isinstance(result, dict) else None
            detail = ""
            if isinstance(operation, dict):
                detail = f"; operation={operation.get('status')!r}, issues={operation.get('issues')!r}"
            if isinstance(status, tuple):
                require(code in status, f"{method} {path}: expected HTTP {status}, observed {code}{detail}")
            else:
                require(code == status, f"{method} {path} HTTP status: expected {status}, observed {code}{detail}")
        require(isinstance(result, dict) and "_invalid_json" not in result,
                f"{method} {path}: expected JSON object, got {result!r}")
        return result

    def get(self, path):
        response = self.request("GET", path, status=200)
        require("data" in response, f"GET {path}: missing data")
        return response["data"]

    def create(self, path, body, key=None):
        response = self.request("POST", path, body, status=201, key=key)
        self.completed(response, path)
        return self.resource(response, path)

    @staticmethod
    def resource(response, label):
        value = response.get("data")
        require(isinstance(value, dict), f"{label}: missing resource")
        require(isinstance(value.get("id"), str) and bool(value["id"]), f"{label}: missing opaque ID")
        require(type(value.get("version")) is int and value["version"] >= 1,
                f"{label}: missing resource version")
        return value

    @staticmethod
    def completed(response, label):
        operation = response.get("operation", {})
        equal(operation.get("status"), "completed", f"{label} operation")
        require(isinstance(operation.get("id"), str), f"{label}: missing operation ID")
        require(isinstance(operation.get("issues"), list), f"{label}: missing issues")
        require(isinstance(operation.get("effects"), list), f"{label}: missing effects")

    def action(self, path, body=None, complete=True, key=None, version=None, status=200):
        if version is None:
            resource_path = path.rsplit("/", 1)[0]
            version = self.get(resource_path)["version"]
        response = self.request("POST", path, body or {}, status=status, key=key, version=version)
        if complete:
            self.completed(response, path)
        return response

    def all(self, path, **filters):
        result, cursor, seen = [], None, set()
        while True:
            query = dict(filters)
            # These are computed views with their own filter lists in the 0.2 contract.
            if path not in ("/revenue-units", "/rated-charges"):
                query["limit"] = 200
            if cursor is not None:
                query["cursor"] = cursor
            response = self.request("GET", path + "?" + urlencode(query), status=200)
            data = response.get("data")
            computed = path in ("/revenue-units", "/rated-charges")
            if computed and isinstance(data, dict):
                data = data.get("rows")
            require(isinstance(data, list), f"{path}: expected collection")
            if not computed:
                require("next_cursor" in response, f"{path}: missing next_cursor")
            result.extend(data)
            cursor = response.get("next_cursor")
            if cursor is None:
                if path == '/position-transfers':
                    from .scopes import current_transfers
                    return current_transfers(result)
                return result
            require(isinstance(cursor, str) and cursor and cursor not in seen,
                    f"{path}: invalid or repeated pagination cursor")
            seen.add(cursor)

    def error(self, method, path, body, status, code, **kwargs):
        response = self.request(method, path, body, status=status, **kwargs)
        equal(response.get("error", {}).get("code"), code, f"{path} error code")
        require(isinstance(response["error"].get("issues"), list), f"{path}: missing error issues")
        return response

    def preview(self, path, body):
        response = self.request("POST", path, body, status=200)
        require("operation" not in response, f"{path}: preview created operation")
        data = response.get("data", {})
        require(isinstance(data.get("basis_token"), str) and data["basis_token"], f"{path}: missing basis token")
        require(isinstance(data.get("issues"), list), f"{path}: missing preview issues")
        require("result" in data, f"{path}: missing preview result")
        if path in ('/correction-previews', '/reclassification-previews'):
            from .impacts import validate_impacts
            validate_impacts(data['result'])
        return data

    def hidden_collection(self, path):
        before = len(self.trace)
        response = self.request("GET", path, status=(403, 404))
        status = self.trace[before]["status"]
        equal(response.get("error", {}).get("code"),
              {403: "forbidden", 404: "not_found"}[status], "hidden collection rejection")
        require("data" not in response, "hidden collection leaked data")
        require(isinstance(response["error"].get("issues"), list), "hidden collection missing issues")
        return response
