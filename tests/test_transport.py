import json
import threading
import unittest
from urllib.request import Request, urlopen

from agent.transport import BrowserBridgeServer, LocalBrowserTransport


def valid_plan():
    return {
        "schema_version": "1.0",
        "action_plan_id": "AP_transport_001",
        "source_sanitized_state_id": "SPS_transport_001",
        "created_at": "2026-09-15T00:00:00Z",
        "intent": "Open transactions",
        "actions": [{
            "action_id": "ACT_transport01",
            "action_type": "CLICK",
            "target_element_id": "EL_001",
            "reason": "Open transactions",
            "risk_level": "LOW",
        }],
    }


def valid_result():
    return {
        "schema_version": "1.0",
        "action_plan_id": "AP_transport_001",
        "action_id": "ACT_transport01",
        "completed_at": "2026-09-15T00:00:01Z",
        "status": "SUCCESS",
        "observed_change": "Click executed successfully.",
        "needs_fresh_page_state": True,
    }


class TransportTests(unittest.TestCase):
    def test_action_plan_and_result_round_trip_over_http(self):
        bridge = BrowserBridgeServer(port=0)
        transport = LocalBrowserTransport(bridge)
        transport.start()
        try:
            host, port = bridge.address
            def service_worker():
                with urlopen(f"http://{host}:{port}/next-action", timeout=3) as response:
                    envelope = json.loads(response.read())
                self.assertEqual(envelope["action_plan"], valid_plan())
                body = json.dumps({
                    "request_id": envelope["request_id"],
                    "action_results": [valid_result()],
                }).encode("utf-8")
                request = Request(
                    f"http://{host}:{port}/action-result",
                    data=body,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urlopen(request, timeout=3):
                    pass

            worker = threading.Thread(target=service_worker)
            worker.start()
            results = transport.execute_action_plan(valid_plan(), timeout=3)
            worker.join(timeout=3)
            self.assertEqual(results, [valid_result()])
        finally:
            transport.close()


if __name__ == "__main__":
    unittest.main()
