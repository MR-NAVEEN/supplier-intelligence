import logging
import os

from api.ai.services.extraction import MODEL_TIERS, _clean_price_value
from api.ai.services.spreadsheet_common import (
    AI_SAMPLE_ROWS,
    MAX_EMPTY_STREAK,
    ai_guess_column_map,
    build_column_map,
    _cell_text,
    detect_header_row,
    parse_user_column_map as _parse_user_column_map,
    read_rows,
)

logger = logging.getLogger(__name__)

CANONICAL_FIELDS = (
    'product_name',
    'code_or_sku',
    'price',
    'currency',
    'description',
    'series',
    'page_number',
)

HEADER_SYNONYMS = {
    'product_name': {
        'product name',
        'product',
        'item',
        'item name',
        'name',
        'model',
        'model name',
        'goods',
        'description of goods',
        'product title',
    },
    'code_or_sku': {
        'sku',
        'code',
        'item code',
        'product code',
        'model no',
        'model number',
        'model no.',
        'article',
        'article no',
        'hsn',
        'part no',
        'part number',
        'item no',
    },
    'price': {
        'price',
        'mrp',
        'rate',
        'amount',
        'unit price',
        'selling price',
        'dp',
        'dealer price',
        'price (mrp)',
        'mrp price',
    },
    'currency': {'currency', 'curr', 'ccy'},
    'description': {'description', 'details', 'spec', 'specification', 'remarks'},
    'series': {'series', 'category', 'brand', 'range', 'collection'},
    'page_number': {'page', 'page no', 'page number', 'pg'},
}

FIELD_HINTS = {
    'product_name': 'the product/item name or title',
    'code_or_sku': 'a SKU, model number, article number, or product code',
    'price': 'a price/MRP/rate — numeric, often with currency symbols',
    'currency': 'a currency code like INR, USD',
    'description': 'a free-text description or spec of the product',
    'series': 'a product series, category, brand, or collection name',
    'page_number': 'a catalogue page number this row belongs to',
}

AI_MAPPING_MODEL = os.environ.get('AI_MODEL_COLUMN_MAPPING', MODEL_TIERS['balanced'])


def parse_user_column_map(raw):
    return _parse_user_column_map(raw, CANONICAL_FIELDS)


def rows_to_products(rows, column_map=None, header_row=None, max_rows=5000):
    if not rows:
        raise ValueError('The spreadsheet is empty.')
    if header_row is None:
        header_index, _score = detect_header_row(rows, HEADER_SYNONYMS)
    else:
        header_index = max(int(header_row) - 1, 0)
        if header_index >= len(rows):
            raise ValueError('header_row is past the end of the sheet.')
    headers = [_cell_text(cell) or f'column_{i + 1}' for i, cell in enumerate(rows[header_index])]
    mapping = build_column_map(headers, HEADER_SYNONYMS, CANONICAL_FIELDS, column_map)
    mapping_source = 'user' if column_map else 'heuristic'

    if 'product_name' not in mapping and 'code_or_sku' not in mapping:
        sample_rows = rows[header_index + 1 : header_index + 1 + AI_SAMPLE_ROWS]
        try:
            ai_mapping = ai_guess_column_map(
                headers, sample_rows, CANONICAL_FIELDS, FIELD_HINTS, AI_MAPPING_MODEL
            )
        except Exception as exc:  # noqa: BLE001 - AI fallback is best-effort
            logger.warning('AI column mapping fallback failed: %s', exc)
            ai_mapping = {}
        if ai_mapping:
            for field, index in ai_mapping.items():
                mapping.setdefault(field, index)
            mapping_source = 'ai'

    if 'product_name' not in mapping and 'code_or_sku' not in mapping:
        raise ValueError(
            'Could not detect product name or SKU column. '
            'Send column_map, e.g. {"product_name":"Item Name","price":"MRP"}.'
        )

    products = []
    skipped = 0
    empty_streak = 0
    for row in rows[header_index + 1 :]:
        if len(products) >= max_rows:
            break
        values = [_cell_text(cell) for cell in row]
        if not any(values):
            empty_streak += 1
            if empty_streak >= MAX_EMPTY_STREAK:
                break
            skipped += 1
            continue
        empty_streak = 0
        product = {}
        extras = {}
        used = set(mapping.values())
        for field, index in mapping.items():
            if index >= len(values):
                continue
            product[field] = values[index]
        for index, header in enumerate(headers):
            if index in used or index >= len(values):
                continue
            text = values[index]
            if text:
                extras[header] = text
        name = (product.get('product_name') or '').strip()
        sku = (product.get('code_or_sku') or '').strip()
        price = _clean_price_value(product.get('price'))
        if not name and not sku and not price:
            skipped += 1
            continue
        if not name:
            name = sku or extras.get(headers[0], 'Untitled')
        page_raw = product.get('page_number') or '1'
        try:
            page_number = max(int(float(str(page_raw).strip() or 1)), 1)
        except (TypeError, ValueError):
            page_number = 1
        products.append(
            {
                'product_name': name,
                'code_or_sku': sku or None,
                'price': price,
                'currency': (product.get('currency') or '').strip() or None,
                'description': (product.get('description') or '').strip() or None,
                'series': (product.get('series') or '').strip() or None,
                'attributes': extras,
                'page_number': page_number,
            }
        )
    return {
        'headers': headers,
        'header_row': header_index + 1,
        'column_map': {field: headers[index] for field, index in mapping.items() if index < len(headers)},
        'column_map_source': mapping_source,
        'products': products,
        'rows_skipped': skipped,
    }


def import_spreadsheet(path, sheet=None, column_map=None, header_row=None, max_rows=5000):
    rows, sheet_name = read_rows(path, sheet=sheet)
    parsed = rows_to_products(rows, column_map=column_map, header_row=header_row, max_rows=max_rows)
    by_page = {}
    for product in parsed['products']:
        page_number = int(product.get('page_number') or 1)
        by_page.setdefault(page_number, []).append(product)
    pages = []
    for page_number in sorted(by_page):
        items = by_page[page_number]
        pages.append(
            {
                'page_number': page_number,
                'page_type': 'product_listing',
                'series_or_section_title': items[0].get('series'),
                'products': items,
                'raw_text_summary': f'{len(items)} rows from spreadsheet',
                'page_notes': f'sheet={sheet_name}',
            }
        )
    return {
        'result': {
            'source_file': os.path.basename(path),
            'source_type': 'spreadsheet',
            'sheet': sheet_name,
            'header_row': parsed['header_row'],
            'column_map': parsed['column_map'],
            'column_map_source': parsed['column_map_source'],
            'total_pages_in_pdf': len(pages) or 1,
            'pages_processed': [page['page_number'] for page in pages],
            'pages': pages,
            'rows_imported': len(parsed['products']),
            'rows_skipped': parsed['rows_skipped'],
        },
        'usage': {'prompt_tokens': 0, 'completion_tokens': 0, 'total_tokens': 0},
        'advertisement_pages_skipped': 0,
    }
