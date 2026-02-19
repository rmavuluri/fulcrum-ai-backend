import os
from anthropic import Anthropic
from anthropic.types import Message


class Claude:
    def __init__(self, model: str | None = None):
        self.client = Anthropic()  # uses ANTHROPIC_API_KEY from env
        self.model = model or os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5")

    def add_user_message(self, messages: list, message):
        user_message = {
            "role": "user",
            "content": message.content
            if isinstance(message, Message)
            else message,
        }
        messages.append(user_message)

    def add_assistant_message(self, messages: list, message):
        assistant_message = {
            "role": "assistant",
            "content": message.content
            if isinstance(message, Message)
            else message,
        }
        messages.append(assistant_message)

    def text_from_message(self, message: Message):
        return "\n".join(
            [block.text for block in message.content if block.type == "text"]
        )

    def chat(
        self,
        messages,
        system=None,
        temperature=1.0,
        stop_sequences=[],
        tools=None,
        thinking=False,
        thinking_budget=1024,
    ) -> Message:
        params = {
            "model": self.model,
            "max_tokens": 8000,
            "messages": messages,
            "temperature": temperature,
            "stop_sequences": stop_sequences,
        }

        if thinking:
            params["thinking"] = {
                "type": "enabled",
                "budget_tokens": thinking_budget,
            }

        if tools:
            tools_clone = [t.copy() if isinstance(t, dict) else t for t in tools]
            if tools_clone:
                last_tool = tools_clone[-1]
                if isinstance(last_tool, dict):
                    last_tool = last_tool.copy()
                    last_tool["cache_control"] = {"type": "ephemeral"}
                    tools_clone[-1] = last_tool
            params["tools"] = tools_clone

        if system:
            params["system"] = [
                {
                    "type": "text",
                    "text": system,
                    "cache_control": {"type": "ephemeral"},
                }
            ]

        message = self.client.messages.create(**params)
        return message
