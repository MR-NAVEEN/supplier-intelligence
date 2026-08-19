# AI app — catalogue PDF + business card OCR

All extraction logic lives in this app. Other backend apps are not modified for AI OCR.

**Docs**
- Postman (all endpoints): [`AI_OCR.postman_collection.json`](./AI_OCR.postman_collection.json)
- Payloads + sample responses: [`API_GUIDE.md`](./API_GUIDE.md)

## All endpoints

AI endpoints are open for demo/testing (no login / no `X-Workspace-Id`).

### Catalogue PDF + photo extraction

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/ai/extract/` | Upload PDF or photos, extract products JSON, save |
| `GET` | `/api/ai/extract/` | List extract runs |
| `GET` | `/api/ai/extract/{id}/` | Run detail |
| `GET` | `/api/ai/catalogues/` | List catalogues |
| `GET` | `/api/ai/catalogues/{id}/` | Catalogue + pages + products |
| `GET` | `/api/ai/catalogues/{id}/products/` | Products only (`?sku=` `&page_number=`) |

### Bulk spreadsheet import

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/ai/bulk-upload/` | CSV / Excel → same catalogue product tables |

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
| `file` | yes | PDF **or** photos (jpg/png/webp/gif/tiff). Repeat `file` for multiple photos. Max 50 MB each |
| `page_mode` | PDF yes; photos no | `full` / `first_n` / `range` (photos default `full`) |
| `page_count` | if `first_n` | e.g. `5` |
| `page_range` | if `range` | e.g. `16-20` or `1,3,5-7` |
| `model_tier` | no | `high_accuracy` (default), `balanced`, `budget` |
| `dpi` | no | PDF render dpi, default `200` |

Excel/CSV is **not** accepted here. Use `POST /api/ai/bulk-upload/`.

### `POST /api/ai/bulk-upload/` (short)

`multipart/form-data`

| Field | Required | Notes |
|--------|----------|--------|
| `file` | yes | `.xlsx` / `.xlsm` / `.csv` / `.tsv` |
| `sheet` | no | Sheet name or index (Excel) |
| `header_row` | no | 1-based header row if auto-detect is wrong |
| `column_map` | no | JSON `{"product_name":"Item Name","price":"MRP"}` |

### `POST /api/ai/cards/` (short)

`multipart/form-data`

| Field | Required | Notes |
|--------|----------|--------|
| `file` | yes | Repeat this key for front + back. jpg / png / webp / gif / pdf |
| `model_tier` | no | same tiers as extract |
