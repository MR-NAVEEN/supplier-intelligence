import re
from decimal import Decimal, InvalidOperation

from django.db.models import Q

from api.ai.models import AICatalogue, AIExtractedProduct

STOPWORDS = {
    'a',
    'an',
    'and',
    'the',
    'of',
    'for',
    'in',
    'on',
    'at',
    'to',
    'is',
    'are',
    'was',
    'what',
    'whats',
    'which',
    'who',
    'how',
    'much',
    'many',
    'please',
    'tell',
    'me',
    'show',
    'list',
    'give',
    'from',
    'with',
    'catalogue',
    'catalog',
    'pdf',
    'product',
    'products',
    'item',
    'items',
    'price',
    'prices',
    'mrp',
    'cost',
    'costs',
    'rupees',
    'rs',
    'inr',
    'page',
    'pages',
    'w',
    'watt',
    'watts',
}

BRAND_HINTS = ('finger', 'jbl')


def normalize_text(text):
    text = (text or '').lower().replace('&', ' and ')
    text = re.sub(r'(\d+)\s*watts?\b', r'\1 w', text)
    text = re.sub(r'([a-z])(\d)', r'\1 \2', text)
    text = re.sub(r'(\d)([a-z])', r'\1 \2', text)
    text = re.sub(r'[^a-z0-9]+', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()


def tokens(text, drop_brands=False):
    words = [w for w in normalize_text(text).split() if w and w not in STOPWORDS]
    if drop_brands:
        words = [w for w in words if w not in BRAND_HINTS]
    return words


def _parse_decimal(raw):
    try:
        return Decimal(str(raw))
    except (InvalidOperation, TypeError, ValueError):
        return None


def detect_catalogue(question, catalogue_id=None):
    if catalogue_id:
        return AICatalogue.objects.filter(pk=catalogue_id).first()
    blob = normalize_text(question)
    for cat in AICatalogue.objects.all():
        hay = normalize_text(f'{cat.title} {cat.brand} {cat.source_filename}')
        hints = [h for h in hay.split() if len(h) >= 3]
        if any(h in blob for h in hints):
            return cat
    return None


def detect_intent(question):
    q = normalize_text(question)
    if re.search(r'\b(cheapest|lowest|least expensive|min price)\b', q):
        return 'cheapest'
    if re.search(r'\b(most expensive|highest|costliest|max price|priciest)\b', q):
        return 'expensive'
    if re.search(r'\b(under|below|less than|cheaper than|upto|up to)\b', q):
        return 'under'
    if re.search(r'\b(above|over|more than|greater than)\b', q):
        return 'over'
    if re.search(r'\b(how many|count|number of)\b', q):
        return 'count'
    if re.search(r'\bpage\s+\d+\b', q):
        return 'page'
    if re.search(r'\b(vs|versus|compare|difference between)\b', q):
        return 'compare'
    if re.search(r'\b(list|show|all products|which products|what products)\b', q):
        return 'list'
    if re.search(r'\b(price|mrp|cost|how much)\b', q):
        return 'price'
    return 'lookup'


def extract_price_limit(question):
    match = re.search(
        r'(?:under|below|less than|cheaper than|upto|up to|above|over|more than|greater than)\s*(?:rs\.?|inr|₹)?\s*(\d+(?:\.\d+)?)',
        normalize_text(question),
    )
    if not match:
        match = re.search(r'\b(\d{3,6})\b', normalize_text(question))
    return _parse_decimal(match.group(1)) if match else None


def extract_page_number(question):
    match = re.search(r'\bpage\s+(\d+)\b', normalize_text(question))
    return int(match.group(1)) if match else None


def product_payload(product):
    price = product.price
    return {
        'id': product.id,
        'catalogue_id': product.catalogue_id,
        'catalogue': product.catalogue.title,
        'brand': product.catalogue.brand,
        'page_number': product.page_number,
        'product_name': product.product_name,
        'code_or_sku': product.code_or_sku,
        'price': str(price) if price is not None else None,
        'price_raw': product.price_raw or (str(price) if price is not None else ''),
        'series': product.series,
    }


def score_product(product, query_tokens):
    if not query_tokens:
        return 0
    name_norm = normalize_text(f'{product.product_name} {product.code_or_sku} {product.series}')
    name_tokens = set(name_norm.split())
    score = 0
    matched = 0
    for token in query_tokens:
        if token in name_tokens:
            score += 18
            matched += 1
        elif len(token) >= 4 and token in name_norm:
            score += 10
            matched += 1
        elif len(token) >= 4 and any(token in part or part in token for part in name_tokens if len(part) >= 4):
            score += 4
            matched += 1
    if matched == len(query_tokens) and query_tokens:
        score += 20
    compact_name = name_norm.replace(' ', '')
    compact_query = ''.join(query_tokens)
    if compact_query and compact_query == compact_name:
        score += 40
    elif compact_query and compact_query in compact_name:
        score += 20
    return score


def search_products(question, catalogue=None, limit=20):
    qs = AIExtractedProduct.objects.filter(is_current=True).select_related('catalogue')
    if catalogue:
        qs = qs.filter(catalogue=catalogue)
    query_tokens = tokens(question, drop_brands=True)
    ranked = []
    for product in qs:
        ranked.append((score_product(product, query_tokens), product))
    ranked.sort(key=lambda item: (-item[0], item[1].page_number, item[1].id))
    if query_tokens:
        ranked = [item for item in ranked if item[0] > 0]
        if ranked:
            top_score = ranked[0][0]
            cutoff = max(20, int(top_score * 0.72))
            ranked = [item for item in ranked if item[0] >= cutoff]
    return [item[1] for item in ranked[:limit]]


def base_queryset(catalogue=None):
    qs = AIExtractedProduct.objects.filter(is_current=True).select_related('catalogue')
    if catalogue:
        qs = qs.filter(catalogue=catalogue)
    return qs


def retrieve(question, catalogue_id=None, last_context=None):
    last_context = last_context or {}
    intent = detect_intent(question)
    catalogue = detect_catalogue(question, catalogue_id)
    if catalogue is None and last_context.get('catalogue_id'):
        followup = bool(
            re.search(
                r'\b(it|that|those|them|same|other|what about|how about|and the|cheaper one)\b',
                normalize_text(question),
            )
        )
        reuse_intents = {'cheapest', 'expensive', 'list', 'count', 'page', 'under', 'over'}
        if followup or intent in reuse_intents:
            catalogue = AICatalogue.objects.filter(pk=last_context['catalogue_id']).first()
    qs = base_queryset(catalogue)

    if intent == 'cheapest':
        products = list(qs.exclude(price__isnull=True).order_by('price', 'id')[:5])
    elif intent == 'expensive':
        products = list(qs.exclude(price__isnull=True).order_by('-price', 'id')[:5])
    elif intent in {'under', 'over'}:
        limit = extract_price_limit(question)
        if limit is None:
            products = []
        elif intent == 'under':
            products = list(qs.filter(price__lt=limit).order_by('price', 'id'))
        else:
            products = list(qs.filter(price__gt=limit).order_by('price', 'id'))
    elif intent == 'page':
        page_number = extract_page_number(question)
        products = list(qs.filter(page_number=page_number).order_by('id')) if page_number else []
    elif intent == 'count':
        products = list(qs.order_by('page_number', 'id'))
    elif intent == 'list':
        products = list(qs.order_by('page_number', 'id'))
    elif intent == 'compare':
        parts = re.split(r'\b(?:vs|versus|compare|difference between|and)\b', normalize_text(question))
        found = []
        seen = set()
        for part in parts:
            part = part.strip()
            if len(part) < 3:
                continue
            matches = search_products(part, catalogue=catalogue, limit=1)
            if matches and matches[0].id not in seen:
                found.append(matches[0])
                seen.add(matches[0].id)
        if len(found) < 2:
            found = search_products(question, catalogue=catalogue, limit=4)
        products = found[:4]
    else:
        products = search_products(question, catalogue=catalogue, limit=8)
        if intent == 'price' and products:
            products = products[:1]
        if not products and last_context.get('product_ids'):
            products = list(qs.filter(id__in=last_context['product_ids']))

    return {
        'intent': intent,
        'catalogue': catalogue,
        'products': products,
    }


def format_price(product):
    if product.price_raw:
        return product.price_raw
    if product.price is not None:
        return str(product.price).rstrip('0').rstrip('.')
    return 'not listed'


def _scope_label(catalogue):
    return catalogue.title if catalogue else 'the extracted catalogues'


def build_answer(question, retrieved):
    intent = retrieved['intent']
    catalogue = retrieved['catalogue']
    products = retrieved['products']
    scope = _scope_label(catalogue)

    if intent == 'count':
        if catalogue:
            return f'{catalogue.title} has {len(products)} extracted product(s).'
        return f'There are {len(products)} extracted product(s) across the saved catalogues.'

    if not products:
        return f'I do not see that in {_scope_label(catalogue)}. Ask using a product name from the extracted catalogue.'

    if intent == 'cheapest':
        top = products[0]
        return f'The cheapest product in {scope} is {top.product_name} at {format_price(top)} (page {top.page_number}).'

    if intent == 'expensive':
        top = products[0]
        return f'The most expensive product in {scope} is {top.product_name} at {format_price(top)} (page {top.page_number}).'

    if intent == 'page':
        page_number = extract_page_number(question) or products[0].page_number
        names = ', '.join(f'{p.product_name} ({format_price(p)})' for p in products)
        return f'Page {page_number} of {scope} has: {names}.'

    if intent in {'under', 'over', 'list'}:
        names = ', '.join(f'{p.product_name} ({format_price(p)})' for p in products)
        verb = 'under' if intent == 'under' else 'over' if intent == 'over' else 'in'
        if intent == 'list':
            return f'{len(products)} product(s) in {scope}: {names}.'
        limit = extract_price_limit(question)
        return f'{len(products)} product(s) {verb} {limit} in {scope}: {names}.'

    if intent == 'compare':
        bits = [f'{p.product_name} is {format_price(p)}' for p in products]
        return 'Compared from the catalogue: ' + '; '.join(bits) + '.'

    if intent == 'price' or len(products) == 1:
        top = products[0]
        return (
            f'{top.product_name} is listed at {format_price(top)} in {top.catalogue.title} '
            f'(page {top.page_number}).'
        )

    names = ', '.join(f'{p.product_name} ({format_price(p)})' for p in products)
    return f'Matches in {scope}: {names}.'


def answer_question(question, catalogue_id=None, last_context=None):
    retrieved = retrieve(question, catalogue_id=catalogue_id, last_context=last_context)
    answer = build_answer(question, retrieved)
    products = retrieved['products']
    catalogue = retrieved['catalogue']
    sources = [product_payload(p) for p in products]
    context = {
        'catalogue_id': catalogue.id if catalogue else None,
        'intent': retrieved['intent'],
        'product_ids': [p.id for p in products],
    }
    return {
        'answer': answer,
        'intent': retrieved['intent'],
        'sources': sources,
        'context': context,
    }
