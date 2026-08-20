import os
import re
from decimal import Decimal, InvalidOperation

from api.ai.models import AICatalogue, AIExtractedPage, AIExtractedProduct, AIBusinessCard


def _title_from_filename(filename):
    base = os.path.splitext(filename or '')[0]
    return (base or 'Catalogue').replace('_', ' ').strip()


def _parse_price(raw):
    if raw is None or raw == '':
        return None
    text = re.sub(r'[^\d.]', '', str(raw))
    if not text:
        return None
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def _search_text(name, sku, series, description, attributes):
    parts = [name, sku, series, description]
    if isinstance(attributes, dict):
        for key, val in attributes.items():
            parts.append(str(key))
            parts.append(str(val))
    return ' '.join(p for p in parts if p).strip()


def get_or_create_catalogue(workspace, filename, total_pages, user, card=None, supplier=None):
    filename = filename or 'catalogue.pdf'
    # supplier (like business_card) is a tag, not part of the lookup -- the real
    # uniqueness key is just (workspace, source_filename), so re-extracting the same
    # file always updates the same catalogue regardless of which card/supplier this
    # particular run carries.
    catalogue, _created = AICatalogue.objects.get_or_create(
        workspace=workspace,
        source_filename=filename,
        defaults={
            'title': _title_from_filename(filename),
            'brand': _title_from_filename(filename).split()[0] if filename else '',
            'total_pages': total_pages or 0,
            'created_by': user,
            'business_card': card,
            'supplier': supplier,
        },
    )
    update_fields = []
    if total_pages and catalogue.total_pages != total_pages:
        catalogue.total_pages = total_pages
        update_fields.append('total_pages')
    if card and catalogue.business_card_id != card.id:
        catalogue.business_card = card
        update_fields.append('business_card')
    if supplier and catalogue.supplier_id != supplier.id:
        catalogue.supplier = supplier
        update_fields.append('supplier')
    if update_fields:
        catalogue.save(update_fields=update_fields + ['updated_at'])
    return catalogue


def persist_run_to_schema(run, result, card=None, supplier=None):
    """Flatten extract JSON into catalogue / page / product rows. Does not change run.result_json."""
    upload = run.upload
    filename = upload.original_filename if upload else (result or {}).get('source_file') or 'catalogue.pdf'
    total_pages = (result or {}).get('total_pages_in_pdf') or (upload.total_pages if upload else 0)
    catalogue = get_or_create_catalogue(run.workspace, filename, total_pages, run.created_by, card, supplier)

    if upload and upload.catalogue_id != catalogue.id:
        upload.catalogue = catalogue
        upload.save(update_fields=['catalogue', 'updated_at'])

    run.catalogue = catalogue
    run.save(update_fields=['catalogue', 'updated_at'])

    touched_pages = [
        int(p.get('page_number'))
        for p in (result or {}).get('pages') or []
        if p.get('page_number') is not None
    ]
    if touched_pages:
        AIExtractedPage.objects.filter(catalogue=catalogue, page_number__in=touched_pages).update(is_current=False)
        AIExtractedProduct.objects.filter(catalogue=catalogue, page_number__in=touched_pages).update(is_current=False)

    for page_data in (result or {}).get('pages') or []:
        page_number = int(page_data.get('page_number') or 0)
        if page_number < 1:
            continue
        page = AIExtractedPage.objects.create(
            catalogue=catalogue,
            business_card = card,
            supplier=supplier,
            run=run,
            page_number=page_number,
            page_type=page_data.get('page_type') or '',
            series_or_section_title=page_data.get('series_or_section_title') or '',
            raw_text_summary=page_data.get('raw_text_summary') or '',
            page_notes=page_data.get('page_notes') or '',
            is_current=True,
        )
        for prod in page_data.get('products') or []:
            name = (prod.get('product_name') or '').strip()
            sku = (prod.get('code_or_sku') or '').strip()
            price_raw = '' if prod.get('price') is None else str(prod.get('price')).strip()
            attrs = prod.get('attributes') if isinstance(prod.get('attributes'), dict) else {}
            description = prod.get('description') or ''
            series = (prod.get('series') or page_data.get('series_or_section_title') or '')
            AIExtractedProduct.objects.create(
                business_card = card,
                supplier=supplier,
                catalogue=catalogue,
                run=run,
                page=page,
                page_number=page_number,
                product_name=name,
                code_or_sku=sku,
                price=_parse_price(price_raw),
                price_raw=price_raw,
                currency=(prod.get('currency') or '').strip(),
                description=description,
                series=series,
                attributes=attrs,
                search_text=_search_text(name, sku, series, description, attrs),
                is_current=True,
            )

    catalogue.current_run = run
    catalogue.created_by = run.created_by
    catalogue.save(update_fields=['current_run', 'updated_at'])
    return catalogue