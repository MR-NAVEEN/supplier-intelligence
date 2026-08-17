import base64
import json
import os
import tempfile
import time

from api.ai.services.extraction import OpenAI, _require_fitz, _usage_from_response, fitz

CARD_SYSTEM_PROMPT = """You extract contact details from a business card.
You may receive one or more images: front, back, extra photos, or PDF pages of the SAME card.
The photos may be rotated or held vertically even if the card is landscape — mentally rotate so text is upright.

Read ONLY what is visible. Never invent emails, phones, names, or brands.

Return ONLY a JSON object:
{
  "full_name": "<person name or null>",
  "job_title": "<title/designation or null>",
  "company": "<company/organization that issued the card or null>",
  "emails": ["<emails as printed>"],
  "phones": ["<phone/mobile/whatsapp/fax numbers as printed>"],
  "website": "<website/url or null>",
  "address": "<full address as printed or null>",
  "linkedin": "<linkedin url or handle or null>",
  "brands": ["<brand/logo names printed on the card>"],
  "extras": { "<any other labelled field, e.g. gst, department, since>": "<value>" },
  "extra_text": "<leftover visible text not already captured>"
}

Rules:
- Merge ALL sides into ONE contact record (person details + company/brands).
- Use empty list [] when no emails/phones/brands.
- Use null for missing scalar fields.
- Keep values as printed (do not reformat country codes unless clearly printed).
- brands = logos/distributed brands (e.g. Columbia, Woodland), not the person's name.
- If two company names appear, put the card issuer in company and the other in extras.trading_as or extra_text.
- Valid JSON only, no markdown.
"""

MAX_CARD_IMAGES = 6


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
        'brands': _as_list(data.get('brands')),
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
        '.bmp': 'image/bmp',
        '.tif': 'image/tiff',
        '.tiff': 'image/tiff',
    }.get(ext, 'image/jpeg')
    with open(path, 'rb') as handle:
        b64 = base64.b64encode(handle.read()).decode('utf-8')
    return f'data:{mime};base64,{b64}'


def _pdf_pages_to_jpegs(pdf_path, tmp_dir, dpi=200):
    _require_fitz()
    zoom = dpi / 72.0
    mat = fitz.Matrix(zoom, zoom)
    paths = []
    doc = fitz.open(pdf_path)
    try:
        for index, page in enumerate(doc, start=1):
            pix = page.get_pixmap(matrix=mat)
            out = os.path.join(tmp_dir, f'{os.path.splitext(os.path.basename(pdf_path))[0]}_{index}.jpg')
            pix.save(out)
            paths.append(out)
            if len(paths) >= MAX_CARD_IMAGES:
                break
    finally:
        doc.close()
    return paths


def collect_card_image_paths(file_paths, tmp_dir, dpi=200):
    if isinstance(file_paths, str):
        file_paths = [file_paths]
    image_paths = []
    for path in file_paths:
        ext = os.path.splitext(path)[1].lower()
        if ext == '.pdf':
            image_paths.extend(_pdf_pages_to_jpegs(path, tmp_dir, dpi=dpi))
        else:
            image_paths.append(path)
        if len(image_paths) >= MAX_CARD_IMAGES:
            break
    return image_paths[:MAX_CARD_IMAGES]


def extract_business_card(file_paths, model_name, retries=3):
    if OpenAI is None:
        raise RuntimeError('openai package is not installed. Run: pip install openai')
    api_key = os.environ.get('OPENAI_API_KEY', '')
    if not api_key:
        raise RuntimeError('OPENAI_API_KEY is not set.')

    client = OpenAI(api_key=api_key)
    last_error = None
    with tempfile.TemporaryDirectory() as tmp_dir:
        image_paths = collect_card_image_paths(file_paths, tmp_dir)
        if not image_paths:
            raise RuntimeError('No readable card image or PDF page was found.')
        content = [
            {
                'type': 'text',
                'text': (
                    f'These {len(image_paths)} image(s) are sides/pages of one business card. '
                    'Rotate mentally if needed. Merge every visible contact field into one JSON object.'
                ),
            }
        ]
        for data_url in (_file_to_data_url(path) for path in image_paths):
            content.append({'type': 'image_url', 'image_url': {'url': data_url, 'detail': 'high'}})

        for attempt in range(retries):
            try:
                resp = client.chat.completions.create(
                    model=model_name,
                    response_format={'type': 'json_object'},
                    messages=[
                        {'role': 'system', 'content': CARD_SYSTEM_PROMPT},
                        {'role': 'user', 'content': content},
                    ],
                    temperature=0,
                )
                payload = resp.choices[0].message.content or '{}'
                data = normalize_card_data(json.loads(payload))
                return {'result': data, 'usage': _usage_from_response(resp), 'sides': len(image_paths)}
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
