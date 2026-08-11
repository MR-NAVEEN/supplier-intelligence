"""Live smoke for POST /api/ai/cards/ — not imported by manage.py test."""
import os
import sys
from io import BytesIO

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.local')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
django.setup()

from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient


def _sample_card_png():
    from PIL import Image, ImageDraw

    image = Image.new('RGB', (900, 520), color=(18, 42, 78))
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 24, 520), fill=(212, 175, 55))
    draw.text((60, 70), 'RAVI MEHTA', fill=(255, 255, 255))
    draw.text((60, 130), 'Purchase Manager', fill=(212, 175, 55))
    draw.text((60, 200), 'Vardhmaan Trading Co.', fill=(255, 255, 255))
    draw.text((60, 270), 'ravi.mehta@vardhmaan.test', fill=(230, 230, 230))
    draw.text((60, 310), '+91 98111 22334', fill=(230, 230, 230))
    draw.text((60, 350), 'www.vardhmaan.test', fill=(230, 230, 230))
    draw.text((60, 400), 'Andheri East, Mumbai', fill=(230, 230, 230))
    draw.text((60, 440), 'linkedin.com/in/ravimehta', fill=(230, 230, 230))
    buf = BytesIO()
    image.save(buf, format='PNG')
    return buf.getvalue()


def main():
    client = APIClient()
    upload = SimpleUploadedFile('sample-card.png', _sample_card_png(), content_type='image/png')
    resp = client.post('/api/ai/cards/', {'file': upload, 'model_tier': 'high_accuracy'}, format='multipart')
    print('EXTRACT', resp.status_code)
    body = resp.json()
    print('success', body.get('success'), 'message', body.get('message'))
    data = body.get('data') or {}
    if resp.status_code >= 400:
        print('error_preview', str(body)[:800])
        return 1
    print('card_id', data.get('id'))
    print('status', data.get('status'))
    print('full_name', data.get('full_name'))
    print('company', data.get('company'))
    print('emails', data.get('emails'))
    print('phones', data.get('phones'))
    print('website', data.get('website'))
    print('timing', data.get('timing'))
    print('costing', data.get('costing'))
    detail = client.get(f"/api/ai/cards/{data.get('id')}/")
    print('DETAIL', detail.status_code, (detail.json().get('data') or {}).get('full_name'))
    listing = client.get('/api/ai/cards/')
    print('LIST', listing.status_code, (listing.json().get('data') or {}).get('count'))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
