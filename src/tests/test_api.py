import os
import sys
import time
from unittest import TestCase, main

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient
from src.api.main import app

client = TestClient(app)

TIMEOUT = 75


class TestAskEndpoint(TestCase):
    def _ask(self, question: str):
        start = time.time()
        response = client.post("/ask", json={"question": question}, timeout=TIMEOUT)
        elapsed = time.time() - start
        print(f"\n=== RESPONSE ({elapsed:.1f}s) ===")
        print(f"status: {response.status_code}")
        data = response.json()
        for k, v in data.items():
            print(f"  {k}: {v}")
        print("=== END ===\n")
        return response, data

    def test_sparkclean_mumbai_spike(self):
        q = "Why did SparkClean 1kg primary sales spike in Mumbai in the week of 16 Sep 2025?"
        response, data = self._ask(q)
        self.assertEqual(response.status_code, 200)
        self.assertIn(data["status"], ("OK", "ABSTAINED", "ERROR"))

    def test_glucojoy_stockout(self):
        q = "what is glucojoy?"
        response, data = self._ask(q)
        self.assertEqual(response.status_code, 200)
        self.assertIn(data["status"], ("OK", "ABSTAINED", "ERROR"))


if __name__ == "__main__":
    main()