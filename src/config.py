from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
try:
    from dotenv import load_dotenv
except ImportError:  # The deterministic/offline lab remains dependency-light.
    def load_dotenv(*args, **kwargs):
        return False

from model_provider import ProviderConfig


@dataclass
class LabConfig:
    """Student TODO: define the shared configuration for the lab.

    Hints:
    - Keep paths for the repo root, dataset directory, and state directory.
    - Add compact-memory settings such as threshold and number of messages to keep.
    - Add provider settings for `openai`, `custom`, `gemini`, `anthropic`, `ollama`, and `openrouter`.
    """

    base_dir: Path
    data_dir: Path
    state_dir: Path
    compact_threshold_tokens: int
    compact_keep_messages: int
    model: ProviderConfig
    judge_model: ProviderConfig


def load_config(base_dir: Path | None = None) -> LabConfig:
    """Student TODO: load environment variables and return a LabConfig.

    Pseudocode:
    1. Resolve the repo root or default to the current file parent.
    2. Optionally load values from `.env`.
    3. Create `state/` if it does not exist.
    4. Return a populated LabConfig instance.
    """

    root = (base_dir or Path(__file__).resolve().parent.parent).resolve()

    # Load environment variables
    env_path = root / ".env"
    if env_path.exists():
        load_dotenv(env_path)
    else:
        load_dotenv()

    state_dir = root / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    
    data_dir = root / "data"

    provider_name = os.getenv("LLM_PROVIDER", "openai").lower()
    model_name = os.getenv("LLM_MODEL", "gpt-4o-mini")
    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_API_BASE") or os.getenv("OPENAI_BASE_URL")

    if provider_name == "gemini":
        api_key = api_key or os.getenv("GEMINI_API_KEY")
        model_name = os.getenv("LLM_MODEL", "gemini-3.1-flash-lite")
    elif provider_name == "anthropic":
        api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        model_name = os.getenv("LLM_MODEL", "claude-3-5-sonnet-20240620")
    elif provider_name == "ollama":
        base_url = base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        model_name = os.getenv("LLM_MODEL", "llama3")
    elif provider_name == "openrouter":
        api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        model_name = os.getenv("LLM_MODEL", "meta-llama/llama-3-8b-instruct:free")
    elif provider_name == "custom":
        api_key = api_key or os.getenv("CUSTOM_API_KEY")
        base_url = base_url or os.getenv("CUSTOM_BASE_URL")
        model_name = os.getenv("LLM_MODEL", "custom-model")

    judge_provider = os.getenv("JUDGE_PROVIDER", provider_name).lower()
    judge_model_name = os.getenv("JUDGE_MODEL", model_name)
    judge_api_key = os.getenv("JUDGE_API_KEY") or api_key
    judge_base_url = os.getenv("JUDGE_BASE_URL") or base_url

    compact_threshold = max(1, int(os.getenv("COMPACT_THRESHOLD_TOKENS", "1000")))
    compact_keep = max(1, int(os.getenv("COMPACT_KEEP_MESSAGES", "6")))

    model_config = ProviderConfig(
        provider=provider_name,
        model_name=model_name,
        temperature=float(os.getenv("LLM_TEMPERATURE", "0.0")),
        api_key=api_key,
        base_url=base_url,
    )

    judge_config = ProviderConfig(
        provider=judge_provider,
        model_name=judge_model_name,
        temperature=float(os.getenv("JUDGE_TEMPERATURE", "0.0")),
        api_key=judge_api_key,
        base_url=judge_base_url,
    )

    return LabConfig(
        base_dir=root,
        data_dir=data_dir,
        state_dir=state_dir,
        compact_threshold_tokens=compact_threshold,
        compact_keep_messages=compact_keep,
        model=model_config,
        judge_model=judge_config,
    )
