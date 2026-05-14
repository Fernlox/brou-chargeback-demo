import sys
import unittest
from pathlib import Path
from unittest.mock import patch


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import tools  # noqa: E402


class SearchTransactionsTests(unittest.TestCase):
    def _base_rows(self) -> list[dict]:
        return [
            {
                "id": "11111111-1111-1111-1111-111111111111",
                "transaction_at": "2026-05-25T12:00:00+00:00",
                "merchant_name": "MERCHANT EXACT",
                "total_amount": 58.45,
                "currency": "USD",
                "card_last4": "1234",
                "entry_mode": "online",
            },
            {
                "id": "22222222-2222-2222-2222-222222222222",
                "transaction_at": "2026-05-25T11:00:00+00:00",
                "merchant_name": "MERCHANT CLOSE",
                "total_amount": 58.40,
                "currency": "USD",
                "card_last4": "1234",
                "entry_mode": "online",
            },
            {
                "id": "33333333-3333-3333-3333-333333333333",
                "transaction_at": "2026-05-25T10:00:00+00:00",
                "merchant_name": "MERCHANT FARTHER",
                "total_amount": 57.90,
                "currency": "USD",
                "card_last4": "1234",
                "entry_mode": "online",
            },
        ]

    def test_approximate_amount_returns_only_exact_matches_when_present(self):
        rows = self._base_rows()
        with patch.object(tools, "_query_transactions", return_value=rows):
            payload = tools.search_transactions(
                user_id="demo-user",
                approximate_amount=58.45,
                amount_tolerance_pct=20.0,
                last_n=5,
            )

        self.assertEqual(payload["total_results"], 1)
        self.assertEqual(len(payload["results"]), 1)
        self.assertEqual(payload["results"][0]["id"], "11111111-1111-1111-1111-111111111111")

    def test_approximate_amount_keeps_similar_matches_when_no_exact_match(self):
        rows = self._base_rows()[1:]
        with patch.object(tools, "_query_transactions", return_value=rows):
            payload = tools.search_transactions(
                user_id="demo-user",
                approximate_amount=58.45,
                amount_tolerance_pct=20.0,
                last_n=5,
            )

        self.assertEqual(payload["total_results"], 2)
        self.assertEqual(len(payload["results"]), 2)
        self.assertEqual(payload["results"][0]["id"], "22222222-2222-2222-2222-222222222222")
        self.assertEqual(payload["results"][1]["id"], "33333333-3333-3333-3333-333333333333")


class TransactionContextFormattingTests(unittest.TestCase):
    def test_build_user_friendly_context_omits_technical_fields(self):
        transaction = {
            "id": "tx-1",
            "transaction_at": "2026-05-25T12:00:00+00:00",
            "merchant_name": "Netflix",
            "merchant_dba": "NETFLIX.COM",
            "total_amount": 11.99,
            "currency": "USD",
            "merchant_city": "Montevideo",
            "merchant_country": "UY",
            "mcc": "5815",
            "card_last4": "1234",
            "entry_mode": "online",
            "card_present": False,
            "ip_address": "192.168.1.10",
            "terminal_id": "TERM-01",
            "customer_reference": "ABC-123",
        }

        payload = tools._build_user_friendly_transaction_context(transaction)

        self.assertEqual(payload["merchant_name"], "Netflix")
        self.assertEqual(payload["merchant_display_name"], "NETFLIX.COM")
        self.assertEqual(payload["location_hint"], "Montevideo, Uruguay")
        self.assertEqual(payload["business_type"], "servicio digital o streaming")
        self.assertEqual(payload["card_used"], "tarjeta terminada en 1234")
        self.assertEqual(payload["purchase_channel"], "online")

        self.assertNotIn("mcc", payload)
        self.assertNotIn("ip_address", payload)
        self.assertNotIn("terminal_id", payload)
        self.assertNotIn("customer_reference", payload)

    def test_build_user_friendly_context_detects_physical_channel(self):
        transaction = {
            "id": "tx-2",
            "transaction_at": "2026-05-25T12:00:00+00:00",
            "merchant_name": "Tienda Inglesa",
            "total_amount": 1200.0,
            "currency": "UYU",
            "mcc": "5411",
            "card_last4": "5678",
            "entry_mode": "chip",
            "card_present": True,
        }

        payload = tools._build_user_friendly_transaction_context(transaction)

        self.assertEqual(payload["business_type"], "supermercado")
        self.assertEqual(payload["purchase_channel"], "presencial (tarjeta física)")


if __name__ == "__main__":
    unittest.main()
