import json
import os
import time

from api.ai.services.extraction import OpenAI, _usage_from_response

CARD_SYSTEM_PROMPT = """You extract contact details from a business card image.
Read ONLY what is visible. Never invent emails, phones, or names.

Return ONLY a JSON object:
{
  "full_name": "<person name or null>",
  "job_title": "<title/designation or null>",
  "company": "<company/organization or null>",
  "emails": ["<emails as printed>"],
  "phones": ["<phone/mobile/whatsapp numbers as printed>"],
  "website": "<website/url or null>",
  "address": "<address as printed or null>",
  "linkedin": "<linkedin url or handle or null>",
  "extras": { "<any other labelled field, e.g. fax, gst, department>": "<value>" },
  "extra_text": "<any leftover visible text not already captured>"
}

Rules:
- Use empty list [] when no emails/phones.
- Use null for missing scalar fields.
- Keep values as printed (do not reformat country codes unless clearly printed).
- Valid JSON only, no markdown.
"""


def _as_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    text = str(value).strip()
    return [text] if text else []


def _as_text(value):
    if value is None:
        return ''
    return str(value).strip()


def normalize_card_data(data):
    if not isinstance(data, dict):
        data = {}
    extras = data.get('extras') if isinstance(data.get('extras'), dict) else {}
    return {
        'full_name': _as_text(data.get('full_name')),
        'job_title': _as_text(data.get('job_title')),
        'company': _as_text(data.get('company')),
        'emails': _as_list(data.get('emails')),
        'phones': _as_list(data.get('phones')),
        'website': _as_text(data.get('website')),
        'address': _as_text(data.get('address')),
        'linkedin': _as_text(data.get('linkedin')),
        'extras': extras,
        'extra_text': _as_text(data.get('extra_text')),
    }


def _file_to_data_url(path):
    ext = os.path.splitext(path)[1].lower()
    mime = {
        '.png': 'image/png',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.webp': 'image/webp',
        '.gif': 'image/gif',
    }.get(ext, 'image/jpeg')
    import base64

    with open(path, 'rb') as handle:
        b64 = base64.b64encode(handle.read()).decode('utf-8')
    return f'data:{mime};base64,{b64}'


def extract_business_card(image_path, model_name, retries=3):
    if OpenAI is None:
        raise RuntimeError('openai package is not installed. Run: pip install openai')
    api_key = os.environ.get('OPENAI_API_KEY', '')
    if not api_key:
        raise RuntimeError('OPENAI_API_KEY is not set.')

    client = OpenAI(api_key=api_key)
    data_url = _file_to_data_url(image_path)
    last_error = None
    for attempt in range(retries):
        try:
            resp = client.chat.completions.create(
                model=model_name,
                response_format={'type': 'json_object'},
                messages=[
                    {'role': 'system', 'content': CARD_SYSTEM_PROMPT},
                    {
                        'role': 'user',
                        'content': [
                            {
                                'type': 'text',
                                'text': 'Extract every contact field visible on this business card.',
                            },
                            {'type': 'image_url', 'image_url': {'url': data_url, 'detail': 'high'}},
                        ],
                    },
                ],
                temperature=0,
            )
            content = resp.choices[0].message.content or '{}'
            data = normalize_card_data(json.loads(content))
            return {'result': data, 'usage': _usage_from_response(resp)}
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            msg = str(exc).lower()
            if any(
                token in msg
                for token in (
                    'insufficient_quota',
                    'credit_balance_exhausted',
                    'invalid_api_key',
                    'incorrect api key',
                )
            ):
                raise
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f'Business card extraction failed: {last_error}')