import logging
import os
import re

from api.ai.services.extraction import MODEL_TIERS
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
    'full_name',
    'job_title',
    'company',
    'emails',
    'phones',
    'website',
    'address',
    'linkedin',
)

LIST_FIELDS = ('emails', 'phones')

HEADER_SYNONYMS = {
    'full_name': {
        'full name',
        'name',
        'contact name',
        'contact person',
        'person',
        'person name',
        'customer name',
    },
    'job_title': {
        'job title',
        'title',
        'designation',
        'position',
        'role',
    },
    'company': {
        'company',
        'company name',
        'organisation',
        'organization',
        'firm',
        'business name',
        'vendor',
        'employer',
        'organisation name',
        'organization name',
    },
    'emails': {
        'email',
        'emails',
        'email id',
        'email address',
        'e mail',
        'mail',
        'mail id',
    },
    'phones': {
        'phone',
        'phones',
        'mobile',
        'mobile number',
        'contact number',
        'contact no',
        'phone number',
        'tel',
        'telephone',
        'cell',
    },
    'website': {'website', 'web', 'url', 'site', 'web site'},
    'address': {'address', 'location', 'full address'},
    'linkedin': {'linkedin', 'linkedin url', 'linkedin profile'},
}

FIELD_HINTS = {
    'full_name': "a person's full name",
    'job_title': 'a job title or designation, e.g. Sales Manager',
    'company': 'a company/organisation name',
    'emails': 'one or more email addresses',
    'phones': 'one or more phone numbers',
    'website': 'a company or personal website URL',
    'address': 'a postal address',
    'linkedin': 'a LinkedIn profile URL',
}

AI_MAPPING_MODEL = os.environ.get('AI_MODEL_COLUMN_MAPPING', MODEL_TIERS['balanced'])

_LIST_SPLIT_RE = re.compile(r'[;,]')


def parse_user_column_map(raw):
    return _parse_user_column_map(raw, CANONICAL_FIELDS)


def _split_list_field(value):
    if not value:
        return []
    parts = [p.strip() for p in _LIST_SPLIT_RE.split(str(value))]
    seen = set()
    result = []
    for part in parts:
        if part and part.lower() not in seen:
            seen.add(part.lower())
            result.append(part)
    return result


def rows_to_cards(rows, column_map=None, header_row=None, max_rows=5000):
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

    if 'full_name' not in mapping and 'company' not in mapping:
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

    if 'full_name' not in mapping and 'company' not in mapping:
        raise ValueError(
            'Could not detect a name or company column. '
            'Send column_map, e.g. {"full_name":"Contact Person","company":"Organisation"}.'
        )

    cards = []
    skipped = 0
    empty_streak = 0
    for row in rows[header_index + 1 :]:
        if len(cards) >= max_rows:
            break
        values = [_cell_text(cell) for cell in row]
        if not any(values):
            empty_streak += 1
            if empty_streak >= MAX_EMPTY_STREAK:
                break
            skipped += 1
            continue
        empty_streak = 0
        card = {}
        extras = {}
        used = set(mapping.values())
        for field, index in mapping.items():
            if index >= len(values):
                continue
            card[field] = values[index]
        for index, header in enumerate(headers):
            if index in used or index >= len(values):
                continue
            text = values[index]
            if text:
                extras[header] = text

        full_name = (card.get('full_name') or '').strip()
        company = (card.get('company') or '').strip()
        if not full_name and not company:
            skipped += 1
            continue

        cards.append(
            {
                'full_name': full_name,
                'job_title': (card.get('job_title') or '').strip(),
                'company': company,
                'emails': _split_list_field(card.get('emails')),
                'phones': _split_list_field(card.get('phones')),
                'website': (card.get('website') or '').strip(),
                'address': (card.get('address') or '').strip(),
                'linkedin': (card.get('linkedin') or '').strip(),
                'extras': extras,
            }
        )
    return {
        'headers': headers,
        'header_row': header_index + 1,
        'column_map': {field: headers[index] for field, index in mapping.items() if index < len(headers)},
        'column_map_source': mapping_source,
        'cards': cards,
        'rows_skipped': skipped,
    }


def import_card_spreadsheet(path, sheet=None, column_map=None, header_row=None, max_rows=5000):
    rows, sheet_name = read_rows(path, sheet=sheet)
    parsed = rows_to_cards(rows, column_map=column_map, header_row=header_row, max_rows=max_rows)
    return {
        'source_file': os.path.basename(path),
        'sheet': sheet_name,
        'header_row': parsed['header_row'],
        'column_map': parsed['column_map'],
        'column_map_source': parsed['column_map_source'],
        'cards': parsed['cards'],
        'rows_imported': len(parsed['cards']),
        'rows_skipped': parsed['rows_skipped'],
    }
