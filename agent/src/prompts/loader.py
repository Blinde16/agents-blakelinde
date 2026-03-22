from functools import lru_cache
from pathlib import Path


PROMPTS_DIR = Path(__file__).resolve().parents[2] / "prompts"


@lru_cache(maxsize=None)
def load_prompt(prompt_name: str) -> str:
    prompt_path = PROMPTS_DIR / prompt_name
    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt file not found: {prompt_path}")
    return prompt_path.read_text(encoding="utf-8").strip()
