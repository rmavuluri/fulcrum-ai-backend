"""
Ally sandbox API: OAuth2 client_credentials token and curated prompt endpoint.
Used for chat when USE_ALLY_SANDBOX=1. Token expires in one hour and should be refreshed.
"""
import os
import requests
from requests.auth import HTTPBasicAuth

TOKEN_ENDPOINT = os.getenv(
    "ALLY_TOKEN_ENDPOINT",
    "https://dev.api.ally.com/v1/access/token",
)
SANDBOX_PROMPT_URL = os.getenv(
    "ALLY_SANDBOX_PROMPT_URL",
    "https://dev.api.ally.com/amh-gpt-sandbox/shared/curated/prompt",
)
# Timeouts (seconds) to avoid hanging on slow or unreachable Ally API
TOKEN_REQUEST_TIMEOUT = int(os.getenv("ALLY_TOKEN_TIMEOUT", "30"))
SANDBOX_REQUEST_TIMEOUT = int(os.getenv("ALLY_SANDBOX_TIMEOUT", "120"))


def generate_bearer_token() -> str | None:
    """
    Generate the bearer token used to communicate with the Ally API.
    After generation, the token expires in one hour and needs to be replaced.
    """
    api_client_key = os.environ.get("SANDBOX_CLIENT_KEY")
    api_client_secret = os.environ.get("SANDBOX_CLIENT_SECRET")

    if not api_client_key or not api_client_secret:
        return None

    data = {"grant_type": "client_credentials"}
    auth = HTTPBasicAuth(api_client_key, api_client_secret)

    try:
        response = requests.post(
            TOKEN_ENDPOINT, data=data, auth=auth, timeout=TOKEN_REQUEST_TIMEOUT
        )
    except requests.RequestException as e:
        print(f"Token request failed: {e}")
        return None

    if response.status_code != 200:
        print(f"Failed to get access token. Status code: {response.status_code}, body: {response.text[:500]}")
        return None

    try:
        body = response.json()
    except ValueError:
        print(f"Token response is not JSON: {response.text[:200]}")
        return None

    token = body.get("access_token")
    if not token:
        print(f"Token response missing access_token. Keys: {list(body.keys())}")
        return None
    return token


def call_sandbox(
    bearer_token: str,
    prompt: str,
    *,
    prompt_template: str | None = None,
    prompt_kwargs: dict | None = None,
    model_id: str | None = None,
    max_tokens: int = 1024,
    temperature: float = 0,
    top_p: float = 1,
) -> str:
    """
    Call the sandbox curated prompt endpoint with the given bearer token.
    Returns the generated text. Raises on non-200 or missing token.
    """
    if not bearer_token:
        raise ValueError("Bearer token is required")

    url = SANDBOX_PROMPT_URL
    headers = {
        "Authorization": f"Bearer {bearer_token}",
        "Content-Type": "application/json",
    }

    template = prompt_template if prompt_template is not None else "{prompt}"
    kwargs = dict(prompt_kwargs or {})
    if "prompt" not in kwargs:
        kwargs["prompt"] = prompt

    data = {
        "prompt_template": template,
        "prompt_kwargs": kwargs,
        "model_id": model_id or os.getenv("ALLY_SANDBOX_MODEL_ID", "openai.gpt-35-turbo-16k"),
        "model_kwargs": {
            "max_tokens": max_tokens,
            "temperature": temperature,
            "top_p": top_p,
        },
    }

    try:
        response = requests.post(
            url, headers=headers, json=data, timeout=SANDBOX_REQUEST_TIMEOUT
        )
    except requests.RequestException as e:
        raise RuntimeError(f"Sandbox request failed: {e}") from e

    if response.status_code != 200:
        raise RuntimeError(
            f"Sandbox API error: status {response.status_code}, body={response.text[:1000]}"
        )

    try:
        payload = response.json()
    except ValueError:
        raise RuntimeError(f"Sandbox response is not JSON: {response.text[:500]}")

    # 200 but API may return an error in the body (e.g. {"error": "..."})
    if isinstance(payload, dict) and isinstance(payload.get("error"), str):
        raise RuntimeError(f"Sandbox API: {payload['error']}")

    return _extract_response_text(payload)


def _extract_response_text(payload: dict) -> str:
    """Extract assistant text from sandbox response. Handles common response shapes."""
    if not payload or not isinstance(payload, dict):
        return ""

    for key in ("result", "content", "output", "text", "response", "reply", "answer"):
        if key in payload and isinstance(payload[key], str):
            return payload[key]
    if "choices" in payload and isinstance(payload["choices"], list) and payload["choices"]:
        first = payload["choices"][0]
        if isinstance(first, dict):
            inner = first.get("message", first)
            if isinstance(inner, dict) and isinstance(inner.get("content"), str):
                return inner["content"]
            if isinstance(first.get("content"), str):
                return first["content"]
    # Nested: e.g. data.content, result.text
    for outer in ("data", "result", "body"):
        if outer in payload and isinstance(payload[outer], dict):
            for key in ("content", "text", "output", "response"):
                if key in payload[outer] and isinstance(payload[outer][key], str):
                    return payload[outer][key]
    return str(payload)
