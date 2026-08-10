from django.conf import settings


def generate_ai_summary(entity_type: str, entity) -> str:
    if settings.AI_PROVIDER_MODE != 'stub':
        return entity.ai_summary or ''
    name = getattr(entity, 'name', None) or getattr(entity, 'title', str(entity))
    return f'Stub AI summary for {entity_type}: {name}. Key insights and follow-ups would appear here.'


def generate_ai_insights(catalogue) -> dict:
    return {
        'summary': f'Stub insights for catalogue "{catalogue.title}"',
        'highlights': ['Sample product cluster A', 'Pricing trend detected'],
        'confidence': 0.82,
    }


def semantic_search(query: str, workspace, limit=20) -> list:
    from api.products.models import Product
    from api.suppliers.models import Supplier

    products = Product.objects.filter(workspace=workspace, name__icontains=query)[:limit]
    suppliers = Supplier.objects.filter(workspace=workspace, name__icontains=query)[:limit]
    results = []
    for s in suppliers:
        results.append({'type': 'supplier', 'id': s.id, 'title': s.name, 'score': 0.9})
    for p in products:
        results.append({'type': 'product', 'id': p.id, 'title': p.name, 'score': 0.85})
    return results
