# AI app — catalogue PDF + business card OCR

All extraction logic lives in this app. Other backend apps are not modified for AI OCR.

**Docs**
- Postman (all endpoints): [`AI_OCR.postman_collection.json`](./AI_OCR.postman_collection.json)
- Payloads + sample responses: [`API_GUIDE.md`](./API_GUIDE.md)

## All endpoints

AI endpoints are open for demo/testing (no login / no `X-Workspace-Id`).

### Catalogue PDF extraction

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/ai/extract/` | Upload PDF, extract products JSON, save run + schema |
| `GET` | `/api/ai/extract/` | List extract runs |
| `GET` | `/api/ai/extract/{id}/` | Run detail |
| `GET` | `/api/ai/catalogues/` | List catalogues |
| `GET` | `/api/ai/catalogues/{id}/` | Catalogue + pages + products |
| `GET` | `/api/ai/catalogues/{id}/products/` | Products only (`?sku=` `&page_number=`) |

### Business card OCR

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/ai/cards/` | Upload 1–2 sides (image or PDF), extract contact JSON, save |
| `GET` | `/api/ai/cards/` | List cards (`?company=` `&name=` `&q=`) |
| `GET` | `/api/ai/cards/{id}/` | Card detail |

### Catalogue chat

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/ai/chat/` | Ask about extracted catalogue products |

### `POST /api/ai/extract/` (short)

`multipart/form-data`

| Field | Required | Notes |
|--------|----------|--------|
| `file` | yes | PDF only, max 50 MB |
| `page_mode` | yes | `full` / `first_n` / `range` |
| `page_count` | if `first_n` | e.g. `5` |
| `page_range` | if `range` | e.g. `16-20` or `1,3,5-7` |
| `model_tier` | no | `high_accuracy` (default), `balanced`, `budget` |
| `dpi` | no | default `200` |

### `POST /api/ai/cards/` (short)

`multipart/form-data`

| Field | Required | Notes |
|--------|----------|--------|
| `file` | yes | Repeat this key for front + back. jpg / png / webp / gif / pdf |
| `model_tier` | no | same tiers as extract |
