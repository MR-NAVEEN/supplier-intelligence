"""One-shot bootstrap for supplier-intelligence apps structure."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APPS = [
    'workspaces', 'suppliers', 'products', 'categories', 'catalogues',
    'business_cards', 'jobs', 'search', 'notifications', 'dashboard',
    'settings_app', 'activity', 'analytics',
]

STUB = '''from django.apps import AppConfig


class {cls}Config(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api.{name}'
    label = '{label}'
'''

for app in APPS:
    d = ROOT / 'api' / app
    d.mkdir(parents=True, exist_ok=True)
    (d / '__init__.py').touch()
    (d / 'migrations' / '__init__.py').parent.mkdir(parents=True, exist_ok=True)
    (d / 'migrations' / '__init__.py').touch()
    label = app.replace('_app', '')
    cls = ''.join(p.capitalize() for p in label.split('_'))
    (d / 'apps.py').write_text(STUB.format(cls=cls, name=app, label=label), encoding='utf-8')
    for f in ('models.py', 'views.py', 'urls.py', 'serializers.py', 'admin.py', 'tests.py'):
        if not (d / f).exists():
            (d / f).write_text('', encoding='utf-8')

print('Bootstrap apps created:', len(APPS))
