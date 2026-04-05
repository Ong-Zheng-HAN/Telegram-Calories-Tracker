import base64
import json
import logging

import anthropic

from config import ANTHROPIC_API_KEY, CLAUDE_MODEL, CLAUDE_TIMEOUT, VISION_SYSTEM_PROMPT, MANUAL_LOG_PROMPT

logger = logging.getLogger(__name__)

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def analyse_food_photos(photo_bytes_list: list[bytes]) -> dict | None:
    """Send one or more food photos to Claude Vision and return nutritional data."""
    content = []
    for photo_bytes in photo_bytes_list:
        b64 = base64.b64encode(photo_bytes).decode("utf-8")
        content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/jpeg",
                "data": b64,
            },
        })
    content.append({"type": "text", "text": "Analyse the food in these photos."})

    return _call_vision(content, VISION_SYSTEM_PROMPT)


def analyse_manual_entry(food_description: str) -> dict | None:
    """Estimate nutritional data from a text description of food."""
    prompt = MANUAL_LOG_PROMPT.format(food_description=food_description)
    content = [{"type": "text", "text": food_description}]
    return _call_vision(content, prompt)


def _call_vision(content: list, system_prompt: str) -> dict | None:
    """Call Claude API and parse JSON response with one retry on failure."""
    for attempt in range(2):
        try:
            response = client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=1024,
                timeout=CLAUDE_TIMEOUT,
                system=system_prompt if attempt == 0 else system_prompt + "\n\nIMPORTANT: You must respond with valid JSON only. No markdown, no explanation.",
                messages=[{"role": "user", "content": content}],
            )
            text = response.content[0].text.strip()
            # Strip markdown code fences if present
            if text.startswith("```"):
                text = text.split("\n", 1)[1] if "\n" in text else text[3:]
                if text.endswith("```"):
                    text = text[:-3]
                text = text.strip()
            return json.loads(text)
        except json.JSONDecodeError:
            logger.warning("Attempt %d: Claude returned invalid JSON: %s", attempt + 1, text[:200])
            if attempt == 0:
                continue
            return None
        except anthropic.APITimeoutError:
            logger.error("Claude API timed out after %ds", CLAUDE_TIMEOUT)
            return None
        except anthropic.APIError as e:
            logger.error("Claude API error: %s", e)
            return None
