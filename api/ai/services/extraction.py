import base64
import json
import os
import re
import tempfile
import time

try:
    import pymupdf as fitz
except Exception:  # wrong `fitz` package or missing PyMuPDF Windows DLL
    fitz = None

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

from api.ai.prompts import SYSTEM_PROMPT

_PYMUPDF_INSTALL_HINT = (
    'PyMuPDF is not available. Uninstall wrong packages with '
    '`pip uninstall fitz frontend -y`, install `pip install --force-reinstall PyMuPDF`, '
    'and install Microsoft Visual C++ Redistributable (x64) if Windows reports '
    'DLL load failed for _extra.'
)


def _require_fitz():
    if fitz is None:
        raise RuntimeError(_PYMUPDF_INSTALL_HINT)

MODEL_TIERS = {
    'budget': os.environ.get('AI_MODEL_BUDGET', 'gpt-5.6-sol'),
    'balanced': os.environ.get('AI_MODEL_BALANCED', 'gpt-5.4-mini'),
    'high_accuracy': os.environ.get('AI_MODEL_HIGH_ACCURACY', 'gpt-5.4'),
}


def pdf_page_count(pdf_path):
    _require_fitz()
    doc = fitz.open(pdf_path)
    try:
        return len(doc)
    finally:
        doc.close()


def image_to_data_url(path):
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


def _image_size(path):
    try:
        from PIL import Image

        with Image.open(path) as image:
            return image.size
    except Exception:
        return (0, 0)


def _clean_price_value(value):
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return value
    text = re.sub(r'(?i)^mrp\s*[:\-]?\s*', '', text).strip()
    text = text.lstrip('-').strip()
    return text or None


def sanitize_page_data(data):
    if not isinstance(data, dict):
        return data
    for prod in data.get('products') or []:
        if not isinstance(prod, dict):
            continue
        if prod.get('price') is not None:
            prod['price'] = _clean_price_value(prod.get('price'))
        attrs = prod.get('attributes')
        if isinstance(attrs, dict):
            for key in list(attrs.keys()):
                if str(key).strip().upper() in {'MRP', 'PRICE', 'PRICE (MRP)', 'MRP PRICE'}:
                    attrs[key] = _clean_price_value(attrs.get(key))
    return data


def is_listable_product(prod):
    if not isinstance(prod, dict):
        return False
    code = (prod.get('code_or_sku') or '').strip()
    price = (prod.get('price') or '').strip() if prod.get('price') is not None else ''
    if code or price:
        return True
    attrs = prod.get('attributes') or {}
    if isinstance(attrs, dict):
        for key, val in attrs.items():
            key_l = str(key).lower()
            if any(token in key_l for token in ('code', 'sku', 'model', 'article', 'mrp', 'price')) and str(
                val or ''
            ).strip():
                return True
    return False


def keep_product_page(page):
    if not isinstance(page, dict):
        return False
    products = [p for p in (page.get('products') or []) if is_listable_product(p)]
    return bool(products)


def _usage_from_response(resp):
    usage = getattr(resp, 'usage', None)
    if not usage:
        return {'prompt_tokens': 0, 'completion_tokens': 0, 'total_tokens': 0}
    prompt = int(getattr(usage, 'prompt_tokens', 0) or 0)
    completion = int(getattr(usage, 'completion_tokens', 0) or 0)
    total = int(getattr(usage, 'total_tokens', 0) or (prompt + completion))
    return {'prompt_tokens': prompt, 'completion_tokens': completion, 'total_tokens': total}


def extract_page(client, model_name, image_path, page_num, width, height, retries=3, source_kind='pdf'):
    data_url = image_to_data_url(image_path)
    rotation = (
        ' This may be a photo of a printed catalogue page; rotate mentally if the image is sideways.'
        if source_kind == 'image'
        else ''
    )
    user_text = (
        f'This is page {page_num} of the catalogue. The image is {width}x{height} pixels.{rotation} '
        f'Extract PRODUCT LISTINGS only. Skip all advertisements, lifestyle/promo content, '
        f'brand slogans, and company/marketing pages (this applies to every catalogue). '
        f"If this page is only an ad/promo, return page_type 'advertisement' and products []. "
        f"If a price is printed like 'MRP:-5990', store price as '5990' (no leading dash)."
    )
    last_error = None
    use_temperature = True
    for attempt in range(retries):
        try:
            kwargs = dict(
                model=model_name,
                response_format={'type': 'json_object'},
                messages=[
                    {'role': 'system', 'content': SYSTEM_PROMPT},
                    {
                        'role': 'user',
                        'content': [
                            {'type': 'text', 'text': user_text},
                            {'type': 'image_url', 'image_url': {'url': data_url, 'detail': 'high'}},
                        ],
                    },
                ],
            )
            if use_temperature:
                kwargs['temperature'] = 0
            resp = client.chat.completions.create(**kwargs)
            content = resp.choices[0].message.content or '{}'
            data = sanitize_page_data(json.loads(content))
            return data, _usage_from_response(resp)
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
            if use_temperature and 'temperature' in msg and 'unsupported' in msg:
                # Some model tiers (e.g. gpt-5.6-*) only allow the default temperature.
                use_temperature = False
                continue
            time.sleep(2 * (attempt + 1))
    return (
        {
            'page_type': 'error',
            'series_or_section_title': None,
            'products': [],
            'raw_text_summary': '',
            'page_notes': f'extraction_failed: {last_error}',
        },
        {'prompt_tokens': 0, 'completion_tokens': 0, 'total_tokens': 0},
    )


def extract_catalogue(pdf_path, page_numbers, model_name, dpi=200):
    """page_numbers are 1-based. Returns result dict + usage totals + skip count."""
    _require_fitz()
    if OpenAI is None:
        raise RuntimeError('openai package is not installed. Run: pip install openai')
    api_key = os.environ.get('OPENAI_API_KEY', '')
    if not api_key:
        raise RuntimeError('OPENAI_API_KEY is not set.')

    client = OpenAI(api_key=api_key)
    zoom = dpi / 72.0
    mat = fitz.Matrix(zoom, zoom)
    usage = {'prompt_tokens': 0, 'completion_tokens': 0, 'total_tokens': 0}
    skipped = 0

    doc = fitz.open(pdf_path)
    try:
        n_pages = len(doc)
        result = {
            'source_file': os.path.basename(pdf_path),
            'total_pages_in_pdf': n_pages,
            'pages_processed': [],
            'pages': [],
        }
        with tempfile.TemporaryDirectory() as tmp_dir:
            for page_num in page_numbers:
                page = doc[page_num - 1]
                pix = page.get_pixmap(matrix=mat)
                render_path = os.path.join(tmp_dir, f'page_{page_num:03d}.jpg')
                pix.save(render_path)
                data, page_usage = extract_page(
                    client, model_name, render_path, page_num, pix.width, pix.height
                )
                data['page_number'] = page_num
                usage['prompt_tokens'] += page_usage['prompt_tokens']
                usage['completion_tokens'] += page_usage['completion_tokens']
                usage['total_tokens'] += page_usage['total_tokens']
                if keep_product_page(data):
                    data['products'] = [p for p in (data.get('products') or []) if is_listable_product(p)]
                    result['pages'].append(data)
                    result['pages_processed'].append(page_num)
                else:
                    skipped += 1
                try:
                    os.remove(render_path)
                except OSError:
                    pass
    finally:
        doc.close()

    return {
        'result': result,
        'usage': usage,
        'advertisement_pages_skipped': skipped,
    }


def _require_openai():
    if OpenAI is None:
        raise RuntimeError('openai package is not installed. Run: pip install openai')
    api_key = os.environ.get('OPENAI_API_KEY', '')
    if not api_key:
        raise RuntimeError('OPENAI_API_KEY is not set.')
    return OpenAI(api_key=api_key)


def extract_catalogue_from_images(image_paths, page_numbers, model_name):
    """image_paths are filesystem paths in upload order. page_numbers are 1-based indexes into that list."""
    client = _require_openai()
    usage = {'prompt_tokens': 0, 'completion_tokens': 0, 'total_tokens': 0}
    skipped = 0
    total = len(image_paths)
    result = {
        'source_file': os.path.basename(image_paths[0]) if image_paths else 'catalogue',
        'source_type': 'images',
        'total_pages_in_pdf': total,
        'pages_processed': [],
        'pages': [],
    }
    for page_num in page_numbers:
        if page_num < 1 or page_num > total:
            continue
        path = image_paths[page_num - 1]
        width, height = _image_size(path)
        data, page_usage = extract_page(
            client, model_name, path, page_num, width, height, source_kind='image'
        )
        data['page_number'] = page_num
        usage['prompt_tokens'] += page_usage['prompt_tokens']
        usage['completion_tokens'] += page_usage['completion_tokens']
        usage['total_tokens'] += page_usage['total_tokens']
        if keep_product_page(data):
            data['products'] = [p for p in (data.get('products') or []) if is_listable_product(p)]
            result['pages'].append(data)
            result['pages_processed'].append(page_num)
        else:
            skipped += 1
    return {
        'result': result,
        'usage': usage,
        'advertisement_pages_skipped': skipped,
    }