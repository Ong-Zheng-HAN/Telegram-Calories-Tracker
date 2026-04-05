import json
import logging

import anthropic

from config import ANTHROPIC_API_KEY, CLAUDE_MODEL, CLAUDE_TIMEOUT, ANALYTICS_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def answer_question(question: str, sheet_data: list[dict]) -> str:
    """Answer a user's nutrition question using their food log data."""
    data_str = json.dumps(sheet_data, indent=2) if sheet_data else "No data logged yet."
    system = ANALYTICS_SYSTEM_PROMPT.format(sheet_data=data_str)

    try:
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=1024,
            timeout=CLAUDE_TIMEOUT,
            system=system,
            messages=[{"role": "user", "content": question}],
        )
        return response.content[0].text
    except anthropic.APITimeoutError:
        return "Sorry, the request timed out. Please try again."
    except anthropic.APIError as e:
        logger.error("Claude API error in analytics: %s", e)
        return "Sorry, something went wrong. Please try again later."
