"""
Provider-agnostic LLM client using LiteLLM.

Supports: Groq, OpenAI, Google Gemini, Ollama.
The user chooses provider + API key from the GUI.
"""

import logging
from typing import Optional, List, Dict

import litellm

logger = logging.getLogger(__name__)

litellm.suppress_debug_info = True

PROVIDERS = {
    "groq": {
        "name": "Groq (Free)",
        "default_model": "groq/qwen/qwen3.8-27b",
        "requires_key": True,
        "key_url": "https://console.groq.com/keys",
        "free_tier": True,
    },
    "deepseek": {
        "name": "DeepSeek (Cheap)",
        "default_model": "deepseek/deepseek-chat",
        "requires_key": True,
        "key_url": "https://platform.deepseek.com/api-keys",
        "free_tier": False,
    },
    "openai": {
        "name": "OpenAI",
        "default_model": "gpt-4o-mini",
        "requires_key": True,
        "key_url": "https://platform.openai.com/api-keys",
        "free_tier": False,
    },
    "gemini": {
        "name": "Google Gemini (Free)",
        "default_model": "gemini/gemini-3.6-flash",
        "requires_key": True,
        "key_url": "https://aistudio.google.com/apikey",
        "free_tier": True,
    },
    "ollama": {
        "name": "Ollama (Local)",
        "default_model": "ollama/llama3.1",
        "requires_key": False,
        "key_url": None,
        "free_tier": True,
    },
}

class LLMClient:
    """Provider-agnostic LLM client."""

    def __init__(
        self,
        provider: str = "groq",
        api_key: Optional[str] = None,
        model: Optional[str] = None,
    ) -> None:
        if provider not in PROVIDERS:
            raise ValueError(
                f"Unknown provider '{provider}'. Supported: {list(PROVIDERS.keys())}"
            )

        self.provider = provider
        self.provider_info = PROVIDERS[provider]
        self.model = model or self.provider_info["default_model"]
        self.api_key = api_key

        logger.info("LLM client: provider=%s, model=%s", provider, self.model)

    async def chat(
        self,
        user_message: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> str:
        """Send a message to the LLM and return the response text."""
        if "gemini-3" in self.model or "gemini/gemini-3" in self.model:
            temperature = 1.0

        messages: List[Dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        # Inject conversation history before the current message
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": user_message})

        try:
            response = await litellm.acompletion(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                api_key=self.api_key,
            )

            result = response.choices[0].message.content
            logger.info("LLM response received (%d chars)", len(result))
            return result

        except Exception as e:
            logger.error("LLM error (%s): %s", self.provider, e)
            raise