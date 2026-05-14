import asyncio
import os
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import agent  # noqa: E402


class _DummyTrace:
    def update(self, output):  # noqa: ANN001
        return None


class _DummyModels:
    def generate_content(self, **kwargs):  # noqa: ANN003
        raise AssertionError("LLM call should not run in deterministic search test.")


class _DummyClient:
    def __init__(self):
        self.models = _DummyModels()


async def _collect_events(session_id: str, user_message: str):
    events = []
    async for event in agent.run_agent_turn(session_id=session_id, user_message=user_message):
        events.append(event)
    return events


class AgentGuardrailsTests(unittest.TestCase):
    def setUp(self) -> None:
        os.environ.setdefault("DEMO_USER_ID", "demo-user")

    def test_extract_slots_parses_day_month_without_amount_collision(self):
        slots = agent._extract_transaction_search_slots(
            "Fue el 25/5",
            now_utc=datetime(2026, 6, 1, tzinfo=timezone.utc),
        )
        self.assertEqual(slots.get("date_from"), "2026-05-25")
        self.assertEqual(slots.get("date_to"), "2026-05-25")
        self.assertNotIn("amount_value", slots)

    def test_extract_slots_distinguishes_approximate_and_exact_amount(self):
        approx_slots = agent._extract_transaction_search_slots("Aprox 60")
        self.assertEqual(approx_slots.get("amount_value"), 60.0)
        self.assertTrue(approx_slots.get("amount_is_approximate"))
        self.assertNotIn("currency", approx_slots)

        exact_slots = agent._extract_transaction_search_slots("58.45 fue el monto exacto")
        self.assertEqual(exact_slots.get("amount_value"), 58.45)
        self.assertFalse(exact_slots.get("amount_is_approximate"))

    def test_exact_amount_retry_triggers_second_real_search_call(self):
        session_id = "guardrails-retry-test"
        agent.reset_session(session_id)
        state = agent._get_session_state(session_id)
        state["search_slots"] = {"date_from": "2026-05-25", "date_to": "2026-05-25"}

        recorded_calls: list[tuple[str, dict]] = []

        def fake_execute(tool_name, args, history, sid):  # noqa: ANN001
            recorded_calls.append((tool_name, dict(args)))
            if len(recorded_calls) == 1:
                return {"result": {"results": [], "total_results": 0}}
            return {
                "result": {
                    "results": [
                        {
                            "id": "11111111-1111-1111-1111-111111111111",
                            "transaction_at": "2026-05-25T12:00:00+00:00",
                            "merchant_name": "MERCHANT INTERNACIONAL",
                            "total_amount": 58.45,
                            "currency": "USD",
                            "card_last4": "1234",
                            "entry_mode": "online",
                        }
                    ],
                    "total_results": 1,
                }
            }

        with (
            patch.object(agent, "_ensure_runtime_ready", return_value=(_DummyClient(), "dummy", object())),
            patch.object(agent, "_execute_tool_call", side_effect=fake_execute),
            patch.object(agent, "start_trace", return_value=_DummyTrace()),
            patch.object(agent, "log_user_turn", return_value=None),
            patch.object(agent, "log_tool_call", return_value=None),
            patch.object(agent, "log_llm_call", return_value=None),
            patch.object(agent, "flush_traces", return_value=None),
        ):
            first_events = asyncio.run(_collect_events(session_id, "Aprox 60"))
            second_events = asyncio.run(_collect_events(session_id, "58.45 fue el monto exacto"))

        tool_calls = [event for event in first_events + second_events if event.get("event") == "tool_call"]
        self.assertEqual(len(tool_calls), 2)

        first_args = tool_calls[0]["data"]["args"]
        self.assertEqual(tool_calls[0]["data"]["name"], "search_transactions")
        self.assertEqual(first_args.get("date_from"), "2026-05-25")
        self.assertEqual(first_args.get("date_to"), "2026-05-25")
        self.assertEqual(first_args.get("approximate_amount"), 60.0)
        self.assertNotIn("min_amount", first_args)
        self.assertNotIn("max_amount", first_args)

        second_args = tool_calls[1]["data"]["args"]
        self.assertEqual(tool_calls[1]["data"]["name"], "search_transactions")
        self.assertEqual(second_args.get("date_from"), "2026-05-25")
        self.assertEqual(second_args.get("date_to"), "2026-05-25")
        self.assertEqual(second_args.get("min_amount"), 58.45)
        self.assertEqual(second_args.get("max_amount"), 58.45)
        self.assertNotIn("approximate_amount", second_args)

    def test_transaction_confirmation_text_uses_user_friendly_context(self):
        tool_result = {
            "result": {
                "transaction": {
                    "merchant_name": "Netflix",
                    "merchant_display_name": "NETFLIX.COM",
                    "currency": "USD",
                    "transaction_at": "2026-05-25T12:00:00+00:00",
                    "total_amount": 11.99,
                    "location_hint": "Montevideo, Uruguay",
                    "business_type": "servicio digital o streaming",
                    "card_used": "tarjeta terminada en 1234",
                    "purchase_channel": "online",
                    "mcc": "5815",
                    "ip_address": "192.168.1.10",
                },
                "same_merchant_count_6m": 2,
            }
        }

        text = agent._build_transaction_confirmation_text(tool_result)

        self.assertIn("NETFLIX.COM", text)
        self.assertIn("Montevideo, Uruguay", text)
        self.assertIn("servicio digital o streaming", text)
        self.assertIn("tarjeta terminada en 1234", text)
        self.assertIn("compra online", text)
        self.assertIn("2 compra(s) previa(s)", text)
        self.assertNotIn("5815", text)
        self.assertNotIn("192.168.1.10", text)


if __name__ == "__main__":
    unittest.main()
