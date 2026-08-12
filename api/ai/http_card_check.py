"""Local HTTP checks for /api/ai/cards/ against the running server."""
import json
import sys
import urllib.error
import urllib.request
from io import BytesIO

BASE = 'http://127.0.0.1:8000'


def dump(title, code, body):
    print(f'=== {title} {code} ===')
    try:
        parsed = json.loads(body)
        print(json.dumps(parsed, indent=2)[:1500])
        return parsed
    except Exception:
        print(body[:800])
        return None


def request(path, method='GET', data=None, headers=None):
    req = urllib.request.Request(BASE + path, data=data, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode()


def multipart(fields):
    boundary = '----CardHttpCheckBoundary'
    chunks = []
    for name, value in fields:
        if isinstance(value, tuple):
            filename, content, content_type = value
            chunks.append(f'--{boundary}\r\n'.encode())
            chunks.append(
                f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'.encode()
            )
            chunks.append(f'Content-Type: {content_type}\r\n\r\n'.encode())
            chunks.append(content)
            chunks.append(b'\r\n')
        else:
            chunks.append(f'--{boundary}\r\n'.encode())
            chunks.append(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
            chunks.append(str(value).encode())
            chunks.append(b'\r\n')
    chunks.append(f'--{boundary}--\r\n'.encode())
    return b''.join(chunks), {'Content-Type': f'multipart/form-data; boundary={boundary}'}


def sample_card_png():
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
    buf = BytesIO()
    image.save(buf, format='PNG')
    return buf.getvalue()


def main():
    live = '--live' in sys.argv
    code, body = request('/api/ai/cards/')
    listing = dump('GET /api/ai/cards/', code, body)
    if code != 200:
        return 1

    data, headers = multipart([('file', ('note.txt', b'not a card', 'text/plain'))])
    code, body = request('/api/ai/cards/', method='POST', data=data, headers=headers)
    dump('POST reject txt', code, body)
    if code != 400:
        return 1

    if not live:
        print('SKIP live extract (pass --live to call OpenAI)')
        print('OK local HTTP checks')
        return 0

    data, headers = multipart([('file', ('sample-card.png', sample_card_png(), 'image/png'))])
    code, body = request('/api/ai/cards/', method='POST', data=data, headers=headers)
    created = dump('POST /api/ai/cards/', code, body)
    if code != 201:
        return 1
    card_id = (created or {}).get('data', {}).get('id')
    code, body = request(f'/api/ai/cards/{card_id}/')
    dump(f'GET /api/ai/cards/{card_id}/', code, body)
    code, body = request('/api/ai/cards/?company=Vardhmaan')
    dump('GET /api/ai/cards/?company=Vardhmaan', code, body)
    return 0 if code == 200 else 1


if __name__ == '__main__':
    raise SystemExit(main())
