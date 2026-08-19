from rest_framework.exceptions import ValidationError


def parse_page_range(selection, total_pages):
    """Parse '1-5', '1,3,5-7' into sorted 1-based page numbers within the PDF."""
    selection = (selection or '').strip()
    if not selection:
        raise ValidationError({'page_range': 'page_range is required when page_mode is range.'})

    indices = set()
    for part in selection.split(','):
        part = part.strip()
        if not part:
            continue
        try:
            if '-' in part:
                a, b = part.split('-', 1)
                lo, hi = int(a.strip()), int(b.strip())
                if lo > hi:
                    lo, hi = hi, lo
                for page in range(lo, hi + 1):
                    if 1 <= page <= total_pages:
                        indices.add(page)
            else:
                page = int(part)
                if 1 <= page <= total_pages:
                    indices.add(page)
        except ValueError as exc:
            raise ValidationError({'page_range': f'Invalid page_range fragment: {part}'}) from exc

    if not indices:
        raise ValidationError(
            {'page_range': f'page_range {selection!r} does not match any page in 1-{total_pages}.'}
        )
    return sorted(indices)


def resolve_pages(page_mode, total_pages, page_count=None, page_range=None, max_pages=100):
    if total_pages < 1:
        raise ValidationError({'file': 'PDF has no readable pages.'})

    if page_mode == 'full':
        pages = list(range(1, total_pages + 1))
    elif page_mode == 'first_n':
        if not page_count:
            raise ValidationError({'page_count': 'page_count is required when page_mode is first_n.'})
        try:
            n = int(page_count)
        except (TypeError, ValueError) as exc:
            raise ValidationError({'page_count': 'page_count must be a positive integer.'}) from exc
        if n < 1:
            raise ValidationError({'page_count': 'page_count must be at least 1.'})
        pages = list(range(1, min(n, total_pages) + 1))
    elif page_mode == 'range':
        pages = parse_page_range(page_range, total_pages)
    else:
        raise ValidationError({'page_mode': 'page_mode must be full, first_n, or range.'})

    if len(pages) > max_pages:
        raise ValidationError(
            {
                'pages': (
                    f'Requested {len(pages)} pages; max allowed per request is {max_pages}. '
                    'Use a smaller first_n or page_range.'
                )
            }
        )
    return pages