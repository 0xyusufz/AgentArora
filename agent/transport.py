"""Local Member 3 -> MV3 browser transport.

The bridge carries only validated ActionPlans and ActionResults. PageState and
SanitizedPageState remain outside this transport boundary.
"""

from __future__ import annotations

import json
import queue
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator, FormatChecker, RefResolver

from .validator import ActionPlanValidator


class _BridgeHandler(BaseHTTPRequestHandler):
    server: "BrowserBridgeServer"

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _write(self, status: int, body: bytes = b"", content_type: str = "application/json") -> None:
        self.send_response(status)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        if body:
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if body:
            self.wfile.write(body)

    def do_OPTIONS(self) -> None:
        self._write(204)

    def do_GET(self) -> None:
        if self.path == "/health":
            self._write(200, b'{"status":"ok"}')
            return
        if self.path != "/next-action":
            self._write(404)
            return
        try:
            request_id, plan = self.server.pending.get(timeout=20)
        except queue.Empty:
            self._write(204)
            return
        body = json.dumps({"request_id": request_id, "action_plan": plan}).encode("utf-8")
        self._write(200, body)

    def do_POST(self) -> None:
        if self.path != "/action-result":
            self._write(404)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length))
            request_id = payload["request_id"]
            action_results = payload["action_results"]
            self.server.bridge.complete(request_id, action_results)
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            self._write(400)
            return
        self._write(204)


class BrowserBridgeServer:
    """Small stdlib HTTP bridge used by the MV3 service worker."""

    def __init__(self, host: str = "127.0.0.1", port: int = 8765):
        self._http = ThreadingHTTPServer((host, port), _BridgeHandler)
        self._http.pending = queue.Queue()
        self._http.bridge = self
        self._http.results: dict[str, tuple[threading.Event, list[dict[str, Any]]]] = {}
        self._http.results_lock = threading.Lock()
        self._thread: threading.Thread | None = None

    @property
    def address(self) -> tuple[str, int]:
        return self._http.server_address

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._http.serve_forever, daemon=True)
        self._thread.start()

    def close(self) -> None:
        self._http.shutdown()
        self._http.server_close()
        if self._thread:
            self._thread.join(timeout=2)

    def submit(self, plan: Mapping[str, Any], timeout: float = 30.0) -> list[dict[str, Any]]:
        request_id = "REQ_" + uuid.uuid4().hex
        event = threading.Event()
        with self._http.results_lock:
            self._http.results[request_id] = (event, [])
        self._http.pending.put((request_id, dict(plan)))
        if not event.wait(timeout):
            with self._http.results_lock:
                self._http.results.pop(request_id, None)
            raise TimeoutError("Timed out waiting for the browser ActionResult.")
        with self._http.results_lock:
            _, results = self._http.results.pop(request_id)
        return results

    def complete(self, request_id: str, results: list[dict[str, Any]]) -> None:
        with self._http.results_lock:
            pending = self._http.results.get(request_id)
            if pending is None:
                return
            event, _ = pending
            self._http.results[request_id] = (event, results)
            event.set()


class LocalBrowserTransport:
    """Member 3 transport for the localhost MV3 bridge."""

    def __init__(self, bridge: BrowserBridgeServer | None = None):
        self.bridge = bridge or BrowserBridgeServer()
        self._plan_validator = ActionPlanValidator()
        self._result_validator = self._load_result_validator()

    @staticmethod
    def _load_result_validator() -> Draft202012Validator:
        contracts_dir = Path(__file__).resolve().parent.parent / "contracts"
        schemas = {
            schema.name: json.loads(schema.read_text(encoding="utf-8"))
            for schema in contracts_dir.glob("*.schema.json")
        }
        schema = schemas["action-result.schema.json"]
        return Draft202012Validator(
            schema,
            resolver=RefResolver.from_schema(schema, store=schemas),
            format_checker=FormatChecker(),
        )

    def start(self) -> None:
        self.bridge.start()

    def close(self) -> None:
        self.bridge.close()

    def execute_action_plan(self, plan: Mapping[str, Any], timeout: float = 30.0) -> list[dict[str, Any]]:
        validated_plan = self._plan_validator.validate(plan)
        results = self.bridge.submit(validated_plan, timeout)
        for result in results:
            errors = list(self._result_validator.iter_errors(result))
            if errors:
                raise ValueError("Browser returned an invalid ActionResult.")
        return results
