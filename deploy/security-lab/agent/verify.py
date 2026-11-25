import socket
import time
import urllib.error
import urllib.request

PROXY = "http://envoy:10000"


def request(method: str, url: str, data: bytes | None = None) -> int:
    req = urllib.request.Request(url, data=data, method=method)
    try:
        with urllib.request.urlopen(req, timeout=2) as response:
            return response.status
    except urllib.error.HTTPError as error:
        return error.code


def direct_route_is_blocked(url: str) -> bool:
    try:
        urllib.request.urlopen(url, timeout=2)
        return False
    except (urllib.error.URLError, TimeoutError, OSError):
        return True


def direct_tcp_is_blocked(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=2):
            return False
    except OSError:
        return True


deadline = time.monotonic() + 45
while True:
    try:
        allowed_get = request("GET", f"{PROXY}/health")
        if allowed_get == 200:
            break
    except (urllib.error.URLError, TimeoutError, OSError):
        pass
    if time.monotonic() >= deadline:
        raise SystemExit("Envoy/OPA did not become ready")
    time.sleep(1)

assert request("POST", f"{PROXY}/mutate", b'{"idempotency_key":"lab-1"}') == 200
assert request("DELETE", f"{PROXY}/health") == 403
assert request("GET", f"{PROXY}/blocked") == 403

# The agent is not attached to either network containing these services.
assert direct_route_is_blocked("http://echo:8080/health")
assert direct_route_is_blocked("http://opa:8181/health")
assert direct_tcp_is_blocked("1.1.1.1", 443)

print("PASS: allowlist enforced; denied requests blocked; direct upstream, policy, and internet egress unavailable")
