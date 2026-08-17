# AI OCR API Guide

Base URL: `http://127.0.0.1:8000`

All AI endpoints are **open for demo** (no login, no `X-Workspace-Id`).

Import the Postman collection: [`AI_OCR.postman_collection.json`](./AI_OCR.postman_collection.json)

---

## All endpoints (complete list)

### A) Catalogue PDF + photo extraction

| # | Method | Endpoint | What it does |
|---|--------|----------|--------------|
| 1 | `POST` | `/api/ai/extract/` | Upload PDF **or photos** → OCR products → save run + schema |
| 2 | `GET` | `/api/ai/extract/` | List extract runs |
| 3 | `GET` | `/api/ai/extract/{id}/` | One extract run detail |
| 4 | `GET` | `/api/ai/catalogues/` | List saved catalogues |
| 5 | `GET` | `/api/ai/catalogues/{id}/` | Catalogue + pages + products |
| 6 | `GET` | `/api/ai/catalogues/{id}/products/` | Products only (`?page_number=` `&sku=`) |

### B) Bulk spreadsheet import

| # | Method | Endpoint | What it does |
|---|--------|----------|--------------|
| 7 | `POST` | `/api/ai/bulk-upload/` | CSV / Excel rows → same catalogue product tables |

### C) Business card OCR

| # | Method | Endpoint | What it does |
|---|--------|----------|--------------|
| 8 | `POST` | `/api/ai/cards/` | Upload card image → OCR contacts → save |
| 9 | `GET` | `/api/ai/cards/` | List cards (`?company=` `&name=` `&q=`) |
| 10 | `GET` | `/api/ai/cards/{id}/` | One card detail + `result_json` |

### D) Catalogue chat

| # | Method | Endpoint | What it does |
|---|--------|----------|--------------|
| 11 | `POST` | `/api/ai/chat/` | Ask questions on extracted catalogue rows |

---

## Common response envelope

Success:

```json
{
  "success": true,
  "status": "200",
  "message": "Success",
  "data": {}
}
```

Error:

```json
{
  "success": false,
  "status": "400",
  "message": "Request failed",
  "data": {
    "file": ["Only PDF files are accepted."]
  }
}
```

List endpoints return paginated `data`:

```json
{
  "count": 1,
  "next": null,
  "previous": null,
  "results": []
}
```

---

## 1. Catalogue PDF OCR

### `POST /api/ai/extract/`

Upload a catalogue PDF → vision OCR → structured JSON → saved as extract run + catalogue/pages/products.

**Content-Type:** `multipart/form-data`  
**Important in Postman:** set `file` type to **File**, not Text. Use the **Body** tab (not Test Results).

#### Payload

| Field | Required | Type | Example | Notes |
|--------|----------|------|---------|--------|
| `file` | yes | File | `JBL.pdf` | PDF only, max 50 MB |
| `page_mode` | yes | Text | `first_n` | `full` \| `first_n` \| `range` |
| `page_count` | if `first_n` | Text | `5` | First N pages |
| `page_range` | if `range` | Text | `16-20` | Also `1,3,5-7` |
| `model_tier` | no | Text | `high_accuracy` | `high_accuracy` \| `balanced` \| `budget` |
| `dpi` | no | Text | `200` | 72–300 |

#### Sample request (first 5 pages)

```
POST /api/ai/extract/
file        = <PDF>
page_mode   = first_n
page_count  = 5
model_tier  = high_accuracy
```

#### Sample success response (`201`)

```json
{
  "success": true,
  "status": "201",
  "message": "Extraction completed",
  "data": {
    "id": 4,
    "upload": {
      "id": 4,
      "original_filename": "FINGER 2026.pdf",
      "file_size_bytes": 617582,
      "total_pages": 5,
      "content_type": "application/pdf",
      "created_at": "2026-08-11T12:43:14.259546+05:30"
    },
    "status": "succeeded",
    "page_mode": "first_n",
    "page_count": 5,
    "page_range": "",
    "pages_requested": [1, 2, 3, 4, 5],
    "model_tier": "high_accuracy",
    "model_name": "gpt-5.4",
    "dpi": 200,
    "result": {
      "source_file": "FINGER_2026.pdf",
      "total_pages_in_pdf": 5,
      "pages_processed": [1, 2, 3, 4, 5],
      "pages": [
        {
          "page_number": 1,
          "page_type": "product_listing",
          "series_or_section_title": null,
          "products": [
            {
              "product_name": "SOUNDKING-5W",
              "code_or_sku": null,
              "price": "1499",
              "currency": null,
              "description": null,
              "attributes": {}
            }
          ],
          "raw_text_summary": "SOUNDKING-5W MRP:-1499; ...",
          "page_notes": "Page contains product images with names and MRP prices only."
        }
      ]
    },
    "summary": {
      "pages_kept": 5,
      "products_count": 12,
      "advertisement_pages_skipped": 0
    },
    "timing": {
      "started_at": "2026-08-11T07:13:14.Z",
      "finished_at": "2026-08-11T07:13:31.Z",
      "duration_ms": 17626,
      "duration_seconds": 17.63
    },
    "costing": {
      "currency": "USD",
      "estimated_cost_usd": "0.059360",
      "prompt_tokens": 12000,
      "completion_tokens": 1500,
      "total_tokens": 13500,
      "model_name": "gpt-5.4",
      "breakdown": {
        "input_usd_per_1m_tokens": "2.50",
        "output_usd_per_1m_tokens": "15.00",
        "pages_billed": 5,
        "avg_cost_per_page_usd": "0.011872"
      }
    },
    "error_message": "",
    "created_at": "2026-08-11T12:43:14.305096+05:30"
  }
}
```

#### Common errors

| Status | When |
|--------|------|
| `400` | Missing `page_mode`, missing `page_count` for `first_n`, non-PDF file |
| `402` | OpenAI quota exhausted |
| `500` | `OPENAI_API_KEY` not set |
| `502` | Upstream model / extract failure |

---

### `GET /api/ai/extract/`

List saved extract runs.

#### Sample response (`200`)

```json
{
  "success": true,
  "status": "200",
  "message": "Success",
  "data": {
    "count": 4,
    "next": null,
    "previous": null,
    "results": [
      {
        "id": 4,
        "source_file": "FINGER 2026.pdf",
        "status": "succeeded",
        "page_mode": "first_n",
        "pages_requested": [1, 2, 3, 4, 5],
        "pages_kept": 5,
        "products_count": 12,
        "duration_ms": 17626,
        "estimated_cost_usd": "0.059360",
        "created_at": "2026-08-11T12:43:14.305096+05:30"
      }
    ]
  }
}
```

---

### `GET /api/ai/extract/{id}/`

Full run detail (same shape as POST success `data`).

Example: `GET /api/ai/extract/4/`

---

### `GET /api/ai/catalogues/`

List normalized catalogues created after successful extracts.

#### Sample response (`200`)

```json
{
  "success": true,
  "status": "200",
  "message": "Success",
  "data": {
    "count": 2,
    "next": null,
    "previous": null,
    "results": [
      {
        "id": 2,
        "title": "FINGER 2026",
        "brand": "FINGER",
        "source_filename": "FINGER 2026.pdf",
        "total_pages": 5,
        "current_run": 4,
        "products_count": 12,
        "pages_count": 5,
        "created_at": "2026-08-11T12:43:31.954693+05:30",
        "updated_at": "2026-08-11T12:43:32.254001+05:30"
      }
    ]
  }
}
```

---

### `GET /api/ai/catalogues/{id}/`

Catalogue + current pages + nested products (schema for chatbots / search).

Example: `GET /api/ai/catalogues/2/`

#### Sample response (`200`) — truncated

```json
{
  "success": true,
  "status": "200",
  "message": "Success",
  "data": {
    "id": 2,
    "title": "FINGER 2026",
    "brand": "FINGER",
    "source_filename": "FINGER 2026.pdf",
    "total_pages": 5,
    "current_run": 4,
    "pages": [
      {
        "id": 2,
        "page_number": 1,
        "page_type": "product_listing",
        "series_or_section_title": "",
        "raw_text_summary": "SOUNDKING-5W MRP:-1499; ...",
        "page_notes": "...",
        "is_current": true,
        "products": [
          {
            "id": 5,
            "page_number": 1,
            "product_name": "SOUNDKING-5W",
            "code_or_sku": "",
            "price": "1499.00",
            "price_raw": "1499",
            "currency": "",
            "description": "",
            "series": "",
            "attributes": {},
            "is_current": true,
            "created_at": "2026-08-11T12:43:32.018999+05:30"
          }
        ]
      }
    ],
    "products": [],
    "created_at": "2026-08-11T12:43:31.954693+05:30",
    "updated_at": "2026-08-11T12:43:32.254001+05:30"
  }
}
```

> Note: products also appear nested under each page. A flat `products` list may be present depending on serializer version.

---

### `GET /api/ai/catalogues/{id}/products/`

Flat product list for one catalogue.

Optional query params:

| Param | Example | Notes |
|--------|---------|--------|
| `page_number` | `1` | Filter by page |
| `sku` | `TSCG` | Case-insensitive contains on `code_or_sku` |

#### Sample response (`200`)

```json
{
  "success": true,
  "status": "200",
  "message": "Success",
  "data": {
    "count": 12,
    "next": null,
    "previous": null,
    "results": [
      {
        "id": 5,
        "page_number": 1,
        "product_name": "SOUNDKING-5W",
        "code_or_sku": "",
        "price": "1499.00",
        "price_raw": "1499",
        "currency": "",
        "description": "",
        "series": "",
        "attributes": {},
        "is_current": true,
        "created_at": "2026-08-11T12:43:32.018999+05:30"
      }
    ]
  }
}
```

---

## 1b. Bulk CSV / Excel import

### `POST /api/ai/bulk-upload/`

Reads spreadsheet rows (no OCR) and saves into the **same** catalogue/product tables.

**Formats:** `.xlsx`, `.xlsm`, `.csv`, `.tsv`  
**Not supported:** `.xls` (save as xlsx/csv)

#### Payload (`multipart/form-data`)

| Field | Required | Example | Notes |
|--------|----------|---------|--------|
| `file` | yes | `products.xlsx` | One file |
| `sheet` | no | `Sheet1` or `0` | Excel sheet |
| `header_row` | no | `2` | 1-based if auto-detect is wrong |
| `column_map` | no | `{"product_name":"Item Name","price":"MRP"}` | JSON string |
| `max_rows` | no | `5000` | Cap |

Auto-maps headers like Item Name, SKU, MRP, Rate, Model No.

#### Sample request

```
POST /api/ai/bulk-upload/
file = products.csv
```

#### Sample success (`201`)

Same envelope as extract: `status=succeeded`, `summary.products_count`, `result.column_map`, `result.pages`.

---

## 2. Business Card OCR

### `POST /api/ai/cards/`

Upload one or both sides of a business card (images and/or PDF). Vision OCR merges them into **one** contact record.

**Content-Type:** `multipart/form-data`

#### Payload

| Field | Required | Type | Example | Notes |
|--------|----------|------|---------|--------|
| `file` | yes | File (repeat) | `front.jpg`, `back.jpg` | jpg / png / webp / gif / pdf. Repeat `file` for each side. Also accepts `files`. |
| `model_tier` | no | Text | `high_accuracy` | Same tiers as catalogue |

Saved fields: `full_name`, `job_title`, `company`, `emails`, `phones`, `website`, `address`, `linkedin`, `brands`, `extras`, `extra_text`.

#### Sample request (front + back)

```
POST /api/ai/cards/
file        = <front image or pdf>
file        = <back image>
model_tier  = high_accuracy
```

A single PDF with both sides also works: one `file` = `card.pdf`.

#### Sample success response (`201`)

```json
{
  "success": true,
  "status": "201",
  "message": "Card extracted",
  "data": {
    "id": 1,
    "original_filename": "WhatsApp Image 2026-08-11 at 2.00.56 PM.jpeg",
    "status": "succeeded",
    "full_name": "VANAPALLI BHASKAR",
    "job_title": "Founder & Director",
    "company": "The Event Planners",
    "emails": ["vbtheeventplanners@gmail.com"],
    "phones": ["+91 9000 229777", "+91 79953 49777"],
    "website": "vbtheeventplanners.com",
    "address": "Vaisakhi Residency, opp. Sampath Vinayaka Temple, B-Block109, Visakhapatnam - 03",
    "linkedin": "",
    "brands": [],
    "extras": {},
    "extra_text": "VB\nCrafting Memories\nWeddings • Corporate • Entertainment",
    "result_json": {
      "full_name": "VANAPALLI BHASKAR",
      "job_title": "Founder & Director",
      "company": "The Event Planners",
      "emails": ["vbtheeventplanners@gmail.com"],
      "phones": ["+91 9000 229777", "+91 79953 49777"],
      "website": "vbtheeventplanners.com",
      "address": "Vaisakhi Residency, opp. Sampath Vinayaka Temple, B-Block109, Visakhapatnam - 03",
      "linkedin": "",
      "extras": {},
      "extra_text": "VB\nCrafting Memories\nWeddings • Corporate • Entertainment"
    },
    "model_name": "gpt-5.4",
    "timing": {
      "started_at": "2026-08-11T08:32:06.676807Z",
      "finished_at": "2026-08-11T08:32:13.194498Z",
      "duration_ms": 6517,
      "duration_seconds": 6.52
    },
    "costing": {
      "currency": "USD",
      "estimated_cost_usd": "0.007588",
      "prompt_tokens": 2117,
      "completion_tokens": 153,
      "total_tokens": 2270,
      "model_name": "gpt-5.4",
      "breakdown": {
        "input_usd_per_1m_tokens": "2.50",
        "output_usd_per_1m_tokens": "15.00"
      }
    },
    "error_message": "",
    "created_at": "2026-08-11T14:02:06.679748+05:30"
  }
}
```

#### Common errors

| Status | When |
|--------|------|
| `400` | Non-image file (e.g. `.txt`) |
| `402` | OpenAI quota exhausted |
| `500` | Missing API key |
| `502` | Extract failure (row still saved with `status=failed`) |

---

### `GET /api/ai/cards/`

List saved cards.

Optional query params:

| Param | Example | Notes |
|--------|---------|--------|
| `company` | `Event` | Company contains |
| `name` | `Bhaskar` | Full name contains |
| `q` | `planner` | Search name / company / title |

#### Sample response (`200`)

```json
{
  "success": true,
  "status": "200",
  "message": "Success",
  "data": {
    "count": 1,
    "next": null,
    "previous": null,
    "results": [
      {
        "id": 1,
        "original_filename": "WhatsApp Image 2026-08-11 at 2.00.56 PM.jpeg",
        "status": "succeeded",
        "full_name": "VANAPALLI BHASKAR",
        "job_title": "Founder & Director",
        "company": "The Event Planners",
        "emails": ["vbtheeventplanners@gmail.com"],
        "phones": ["+91 9000 229777", "+91 79953 49777"],
        "duration_ms": 6517,
        "estimated_cost_usd": "0.007588",
        "created_at": "2026-08-11T14:02:06.679748+05:30"
      }
    ]
  }
}
```

---

### `GET /api/ai/cards/{id}/`

Full card detail including `result_json`, `timing`, `costing`.

Example: `GET /api/ai/cards/1/`

Same shape as POST success `data`.

---

## 3. Catalogue chat

Answers come from **extracted DB rows** (Finger / JBL products already saved). It does not re-read the PDF.

### `POST /api/ai/chat/`

**Content-Type:** `application/json`

#### Payload

| Field | Required | Example | Notes |
|--------|----------|---------|--------|
| `message` | yes | `What is the MRP of SOUNDKING-5W?` | Natural language |
| `session_id` | no | `1` | Keeps catalogue context for follow-ups |
| `catalogue_id` | no | `2` | Limit to one catalogue |

#### Sample request

```json
{
  "message": "What is the cheapest product in the Finger catalogue?"
}
```

#### Sample success response (`200`)

```json
{
  "success": true,
  "status": "200",
  "message": "Answered",
  "data": {
    "session_id": 1,
    "answer": "The cheapest product in FINGER 2026 is HOLD-ME-UP3 at 499 (page 5).",
    "intent": "cheapest",
    "sources": [
      {
        "id": 16,
        "catalogue_id": 2,
        "catalogue": "FINGER 2026",
        "brand": "FINGER",
        "page_number": 5,
        "product_name": "HOLD-ME-UP3",
        "code_or_sku": "",
        "price": "499.00",
        "price_raw": "499",
        "series": ""
      }
    ]
  }
}
```

Follow-up:

```json
{
  "message": "What about the most expensive?",
  "session_id": 1
}
```

---

## Quick Postman checklist

1. Import `AI_OCR.postman_collection.json`
2. Set collection variable `baseUrl` = `http://127.0.0.1:8000`
3. For uploads: Body → form-data → `file` type = **File**
4. After POST extract / card, collection scripts auto-set `extractRunId` / `cardId` / `catalogueId`
5. View response in **Body** tab

## Env required for POST extract/card

```
OPENAI_API_KEY=sk-...
```

Loaded from `supplier-intelligence/.env`.
