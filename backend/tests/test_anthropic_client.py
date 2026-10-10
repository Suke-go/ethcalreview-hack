import asyncio
import sys
import types
import unittest
from unittest.mock import patch

# The client module imports tenacity for the existing providers.
try:
    import tenacity
except ImportError:
    fake_tenacity = types.ModuleType("tenacity")
    fake_tenacity.retry = lambda *args, **kwargs: lambda fn: fn
    fake_tenacity.stop_after_attempt = lambda *args: None
    fake_tenacity.wait_exponential = lambda **kwargs: None
    sys.modules["tenacity"] = fake_tenacity

from app.services.llm_client import AnthropicClient, create_llm_client


class FakeResponse:
    def __init__(self, data, error=None):
        self.data = data
        self.error = error

    def raise_for_status(self):
        if self.error:
            raise self.error

    def json(self):
        return self.data


class AnthropicClientTest(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.reply = FakeResponse({
            "content": [{"type": "text", "text": "review"}, {"type": "text", "text": " result"}],
            "stop_reason": "end_turn",
        })
        owner = self

        class FakeAsyncClient:
            def __init__(self, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

            async def post(self, url, **kwargs):
                owner.calls.append((url, kwargs))
                return owner.reply

        fake_httpx = types.ModuleType("httpx")
        fake_httpx.AsyncClient = FakeAsyncClient
        self.httpx_patch = patch.dict(sys.modules, {"httpx": fake_httpx})
        self.httpx_patch.start()
        self.addCleanup(self.httpx_patch.stop)

    def test_messages_and_system_instruction(self):
        client = create_llm_client("anthropic", "test-key")
        text = asyncio.run(client.generate_content_async("draft", "check consistency"))
        self.assertEqual(text, "review result")
        url, kwargs = self.calls[0]
        self.assertEqual(url, "https://api.anthropic.com/v1/messages")
        self.assertEqual(kwargs["headers"]["x-api-key"], "test-key")
        self.assertEqual(kwargs["json"]["model"], "claude-sonnet-5-5")
        self.assertEqual(kwargs["json"]["system"], "check consistency")
        self.assertEqual(kwargs["json"]["messages"], [{"role": "user", "content": "draft"}])

    def test_credit_failure_is_not_retried(self):
        self.reply = FakeResponse({}, RuntimeError("credit exhausted"))
        with self.assertRaisesRegex(RuntimeError, "credit exhausted"):
            asyncio.run(AnthropicClient("test-key").generate_content_async("draft"))
        self.assertEqual(len(self.calls), 1)

    def test_truncation_is_rejected(self):
        self.reply = FakeResponse({"content": [{"type": "text", "text": "partial"}], "stop_reason": "max_tokens"})
        with self.assertRaisesRegex(ValueError, "truncated"):
            asyncio.run(AnthropicClient("test-key").generate_content_async("draft"))


if __name__ == "__main__":
    unittest.main()
