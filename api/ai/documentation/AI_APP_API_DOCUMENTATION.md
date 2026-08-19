# AI App — API Documentation

Base path: `/api/ai/`
Auth: none required (`AllowAny` on every endpoint — no token needed)
Every response is wrapped in the same envelope:

```json
{
  "success": true,
  "status": "200",
  "message": "Success",
  "data": { ... }
}
```

On failure, `success` is `false`, `status` is the HTTP code as a string, and `message`/`data` describe the error, e.g.:

```json
{
  "success": false,
  "status": "400",
  "message": "Request failed",
  "data": { "pages": "Requested 101 pages; max allowed per request is 100. ..." }
}
```

---

## ⚠️ Known issue (as of 2026-08-19)

A recent merge added a **required** `card` field (business card id) to `POST /api/ai/extract/`, and a required, non-nullable `business_card` link on the underlying `AICatalogue` / `AICatalogueUpload` / `AIExtractionRun` / `AIExtractedPage` / `AIExtractedProduct` models. On top of that, there's an argument-count bug (`_succeed_run` calls `persist_run_to_schema(run, result)` with 2 args, but the function now requires 3) that makes `POST /api/ai/extract/` throw a `TypeError` on every request. **Confirmed live:** `POST /api/ai/bulk-upload/` (product spreadsheet import) currently throws `IntegrityError: NOT NULL constraint failed: ai_aicatalogueupload.business_card_id` on the very first DB write, before any parsing even runs. This doc describes the intended/working contract for those two endpoints; if you hit a 500, this pre-existing issue is why.

**Not affected:** `POST /api/ai/cards/bulk-upload/` (section 13 below) writes only to `AIBusinessCard`, which has no such required link — it's fully working today, verified end-to-end.

---

## 1. Extract catalogue — `POST /api/ai/extract/`

Extracts product listings from a PDF catalogue **or** a set of catalogue photos using AI vision. One PDF *or* multiple photos per request — never both, never more than one PDF.

### Payload (`multipart/form-data`)

| Field | Required | Notes |
|---|---|---|
| `card` | **yes** | id of an `AIBusinessCard` (create one first via `POST /api/ai/cards/`) — see known issue above |
| `file` (repeatable) | yes | the PDF, or one or more photo files. Repeat the key `file` for multiple photos (`files` / `files[]` also accepted) |
| `page_mode` | required for PDFs | `full`, `first_n`, or `range`. Optional for photos (defaults to `full`) |
| `page_count` | required if `page_mode=first_n` | integer, e.g. `5` |
| `page_range` | required if `page_mode=range` | e.g. `"16-20"` |
| `model_tier` | no (default `high_accuracy`) | `budget`, `balanced`, or `high_accuracy` |
| `dpi` | no (default `200`) | 72–300, PDF render resolution |

Rules enforced by the server:
- Accepted file types: `.pdf`, `.jpg`, `.jpeg`, `.png`, `.webp`, `.gif`, `.bmp`, `.tif`, `.tiff`. CSV/XLSX are rejected here — use `/api/ai/bulk-upload/` instead.
- Max file size: 50 MB per file.
- Max pages per request: `AI_MAX_PAGES_PER_REQUEST` (currently **100**).
- Can't mix a PDF and photos in the same request. Only one PDF per request (photos can be multiple).

### Example — PDF, first 5 pages

```
POST /api/ai/extract/
Content-Type: multipart/form-data

card       = 3
file       = catalogue.pdf
page_mode  = first_n
page_count = 5
model_tier = high_accuracy
```

### Example — multiple photos

```
POST /api/ai/extract/
Content-Type: multipart/form-data

card = 3
file = page1.jpg
file = page2.jpg
file = page3.jpg
```

### Response (`201`)

```json
{
  "success": true,
  "status": "201",
  "message": "Extraction completed",
  "data": {
    "id": 13,
    "upload": {
      "id": 13,
      "original_filename": "JBL.pdf",
      "file_size_bytes": 1093832,
      "total_pages": 8,
      "content_type": "application/pdf",
      "created_at": "2026-08-18T22:19:16.047063+05:30"
    },
    "status": "succeeded",
    "page_mode": "first_n",
    "page_count": 8,
    "page_range": "",
    "pages_requested": [1, 2, 3, 4, 5, 6, 7, 8],
    "model_tier": "high_accuracy",
    "model_name": "gpt-5.4",
    "dpi": 200,
    "result": {
      "source_file": "JBL.pdf",
      "total_pages_in_pdf": 8,
      "pages_processed": [1, 2, 3, 4, 5, 6, 7, 8],
      "pages": [
        {
          "page_type": "product_listing",
          "series_or_section_title": "JBL SPEAKER",
          "products": [
            { "product_name": "GO 4", "code_or_sku": null, "price": "5499", "currency": null, "description": null, "attributes": {} }
          ],
          "raw_text_summary": "JBL SPEAKER. GO 4 MRP:-5499...",
          "page_notes": null,
          "page_number": 4
        }
      ]
    },
    "summary": { "pages_kept": 8, "products_count": 19, "advertisement_pages_skipped": 0 },
    "timing": { "started_at": "...", "finished_at": "...", "duration_ms": 32046, "duration_seconds": 32.05 },
    "costing": {
      "currency": "USD",
      "estimated_cost_usd": "0.094235",
      "prompt_tokens": 27680,
      "completion_tokens": 1669,
      "total_tokens": 29349,
      "model_name": "gpt-5.4",
      "breakdown": { "input_usd_per_1m_tokens": "2.50", "output_usd_per_1m_tokens": "15.00", "pages_billed": 8, "avg_cost_per_page_usd": "0.011779" }
    },
    "error_message": "",
    "created_at": "2026-08-18T22:19:16.947063+05:30"
  }
}
```

**Note:** `status` can be `"succeeded"` with `pages_kept: 0` / `products_count: 0` — that means every page was classified as an ad/promo page and skipped, not that the request failed.

### Errors

| Status | Cause |
|---|---|
| 400 | missing/wrong `page_mode`, wrong field name, non-multipart body, unsupported file type, mixed PDF+photos, 2 PDFs, over the page cap, corrupt/unreadable PDF |
| 500 | `OPENAI_API_KEY` not set on the server |
| 402 | OpenAI quota/credit exhausted |
| 502 | OpenAI/network error |

---

## 2. List extraction runs — `GET /api/ai/extract/`

Paginated list of past extraction runs (uses `AIExtractionRunListSerializer` — a lighter shape than the detail view).

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
        "id": 13,
        "source_file": "JBL.pdf",
        "status": "succeeded",
        "page_mode": "first_n",
        "pages_requested": [1, 2, 3, 4, 5, 6, 7, 8],
        "pages_kept": 8,
        "products_count": 19,
        "duration_ms": 32046,
        "estimated_cost_usd": "0.094235",
        "created_at": "2026-08-18T22:19:16.947063+05:30"
      }
    ]
  }
}
```

## 3. Retrieve one extraction run — `GET /api/ai/extract/{id}/`

Same full shape as the `201` response from section 1's `data`.

---

## 4. List catalogues — `GET /api/ai/catalogues/`

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
        "id": 1,
        "title": "JBL",
        "brand": "JBL",
        "source_filename": "JBL.pdf",
        "total_pages": 8,
        "current_run": 13,
        "products_count": 19,
        "pages_count": 8,
        "created_at": "2026-08-11T12:33:05.042594+05:30",
        "updated_at": "2026-08-18T22:19:48.520008+05:30"
      }
    ]
  }
}
```

## 5. Retrieve one catalogue — `GET /api/ai/catalogues/{id}/`

Full schema: every current page and every current product nested inside.

```json
{
  "success": true,
  "status": "200",
  "message": "Success",
  "data": {
    "id": 1,
    "title": "JBL",
    "brand": "JBL",
    "source_filename": "JBL.pdf",
    "total_pages": 8,
    "current_run": 13,
    "pages": [
      {
        "id": 40,
        "page_number": 4,
        "page_type": "product_listing",
        "series_or_section_title": "JBL SPEAKER",
        "raw_text_summary": "JBL SPEAKER. GO 4 MRP:-5499...",
        "page_notes": null,
        "is_current": true,
        "products": [
          { "id": 101, "page_number": 4, "product_name": "GO 4", "code_or_sku": "", "price": "5499.00", "price_raw": "5499", "currency": "", "description": "", "series": "JBL SPEAKER", "attributes": {}, "is_current": true, "created_at": "..." }
        ]
      }
    ],
    "products": [ /* every current product in the catalogue, flat */ ],
    "created_at": "...",
    "updated_at": "..."
  }
}
```

---

## 6. List a catalogue's products — `GET /api/ai/catalogues/{catalogue_id}/products/`

Same product shape as above, scoped to one catalogue. Optional query params: `?page_number=4`, `?sku=ABC`.

## 7. List / manage products directly — `/api/ai/products/`

A flat, catalogue-agnostic view over `AIExtractedProduct`, with full CRUD:

| Method | Purpose |
|---|---|
| `GET /api/ai/products/` | list all current products across every catalogue (filters: `?page_number=`, `?sku=`) |
| `GET /api/ai/products/{id}/` | one product |
| `POST /api/ai/products/` | manually create a product row |
| `PUT` / `PATCH /api/ai/products/{id}/` | edit a product |
| `DELETE /api/ai/products/{id}/` | soft-delete (sets `is_current=false`, doesn't remove the row) |

Write payload (`POST`/`PUT`/`PATCH`) — JSON:

```json
{
  "business_card": 3,
  "catalogue": 1,
  "run": 13,
  "page": 40,
  "page_number": 4,
  "product_name": "GO 4",
  "code_or_sku": "GO4-BLK",
  "price": "5499.00",
  "price_raw": "5499",
  "currency": "INR",
  "description": "Portable Bluetooth speaker",
  "series": "JBL SPEAKER",
  "attributes": {},
  "is_current": true
}
```
This is meant for manual corrections, not the normal extraction flow — you need valid `catalogue`/`run`/`page` ids from an existing extraction (and currently `business_card`, per the known issue above).

---

## 8. Extract a business card — `POST /api/ai/cards/`

OCRs a photo (or PDF) of a business card into structured contact fields. Supports multiple sides (front/back) — repeat the `file` key.

### Payload (`multipart/form-data`)

| Field | Required | Notes |
|---|---|---|
| `file` (repeatable, max 6) | yes | jpg, png, webp, gif, bmp, tiff, or pdf |
| `model_tier` | no (default `high_accuracy`) | `budget`, `balanced`, `high_accuracy` |

```
POST /api/ai/cards/
file = front.jpg
file = back.jpg
```

### Response (`201`)

```json
{
  "success": true,
  "status": "201",
  "message": "Card extracted",
  "data": {
    "id": 2,
    "original_filename": "card.jpg",
    "status": "succeeded",
    "full_name": "Jane Doe",
    "job_title": "VP Sales",
    "company": "Acme Corp",
    "emails": ["jane.doe@acme.com"],
    "phones": ["+1 555 123 4567"],
    "website": "",
    "address": "",
    "linkedin": "",
    "brands": [],
    "extras": {},
    "extra_text": "",
    "source_files": [{ "filename": "card.jpg", "content_type": "image/jpeg", "size_bytes": 11707 }],
    "result_json": { "full_name": "Jane Doe", "job_title": "VP Sales", "company": "Acme Corp", "emails": ["jane.doe@acme.com"], "phones": ["+1 555 123 4567"] },
    "model_name": "gpt-5.4",
    "timing": { "started_at": "...", "finished_at": "...", "duration_ms": 2144, "duration_seconds": 2.14 },
    "costing": { "currency": "USD", "estimated_cost_usd": "0.003455", "prompt_tokens": 938, "completion_tokens": 74, "total_tokens": 1012, "model_name": "gpt-5.4", "breakdown": {} },
    "error_message": "",
    "created_at": "2026-08-17T22:35:08.181576+05:30"
  }
}
```

## 9. List business cards — `GET /api/ai/cards/`

Paginated list, filterable with `?company=Acme`, `?name=Jane`, `?q=free-text`.

## 10. Retrieve one business card — `GET /api/ai/cards/{id}/`

Same shape as the `201` response above.

---

## 11. Chat with the catalogue data — `POST /api/ai/chat/`

Ask natural-language questions about the extracted catalogue data. An LLM writes a real, read-only SQL query against `ai_aicatalogue` / `ai_aiextractedpage` / `ai_aiextractedproduct` (never anything else — writes and other tables are blocked), runs it, and answers in plain English from the results. Handles aggregations, filters, comparisons, and joins — not just keyword matching.

### Payload (JSON)

| Field | Required | Notes |
|---|---|---|
| `message` | yes | the question, max 2000 chars |
| `session_id` | no | pass back a previous `session_id` to keep the conversation logged under one session |
| `catalogue_id` | no | hints the agent to prefer one catalogue (e.g. `1` = JBL) unless the question clearly says otherwise |

```json
{ "message": "What is the most expensive product in the JBL catalogue?" }
```

### Response (`200`)

```json
{
  "success": true,
  "status": "200",
  "message": "Answered",
  "data": {
    "session_id": 7,
    "answer": "The most expensive product in the JBL catalogue is PARTYBOX 710 at 74999.",
    "intent": "query",
    "sources": [
      { "product_name": "PARTYBOX 710", "price": "74999.00", "price_raw": "74999", "currency": "", "page_number": 8, "catalogue_title": "JBL" }
    ]
  }
}
```

`intent` is one of: `query` (SQL ran and answered), `clarify` (question too vague, `answer` asks a follow-up), `off_topic` (unrelated to catalogue data), `error` (SQL couldn't be fixed after 3 tries — `answer` explains what went wrong in plain language).

### Example questions that work well

- "What is the cheapest product in the JBL catalogue?"
- "How many products does each catalogue have, and what is the average price per catalogue?"
- "Show all products under 2000 in the FINGER 2026 catalogue."
- "Compare the price of WAVE BUDS 2 and WAVE BEAM 2."
- "Which single product is the most expensive across all catalogues, and which catalogue is it in?"
- "What products are on page 4 of the JBL catalogue?"

---

## 12. Bulk-upload products from Excel/CSV — `POST /api/ai/bulk-upload/`

Imports a spreadsheet of products directly into the database — normally **no AI call, no OCR**, just parses rows. This is the endpoint for spreadsheets; `/api/ai/extract/` explicitly rejects CSV/XLSX files.

> ⚠️ See the known-issue box at the top of this doc — this endpoint currently 500s on every request due to a pre-existing bug unrelated to the mapping logic below.

### Payload (`multipart/form-data`)

| Field | Required | Notes |
|---|---|---|
| `file` | yes | `.xlsx`, `.xlsm`, `.csv`, or `.tsv` (legacy `.xls` is **not** supported — re-save as `.xlsx`) |
| `sheet` | no | sheet name or index (xlsx only); defaults to the first sheet |
| `header_row` | no | 1-based row number where headers live; auto-detected if omitted |
| `column_map` | no | JSON string to force a column mapping, e.g. `{"product_name":"Item Name","price":"MRP"}` |
| `max_rows` | no (default 5000, max 20000) | safety cap |

### What your Excel/CSV needs to look like

The importer auto-detects the header row (scans the first 20 rows for the one that best matches known column names) and auto-maps columns by name — **you don't need exact column names**, just something recognizable. It understands these canonical fields and synonyms (case-insensitive):

| Canonical field | Recognized header names (any of these) | Required? |
|---|---|---|
| `product_name` | Product Name, Product, Item, Item Name, Name, Model, Model Name, Goods, Description of Goods, Product Title | one of `product_name` **or** `code_or_sku` must be present |
| `code_or_sku` | SKU, Code, Item Code, Product Code, Model No, Model Number, Article, Article No, HSN, Part No, Part Number, Item No | (see above) |
| `price` | Price, MRP, Rate, Amount, Unit Price, Selling Price, DP, Dealer Price, Price (MRP), MRP Price | optional |
| `currency` | Currency, Curr, CCY | optional |
| `description` | Description, Details, Spec, Specification, Remarks | optional |
| `series` | Series, Category, Brand, Range, Collection | optional |
| `page_number` | Page, Page No, Page Number, Pg | optional, defaults to `1` — use this to group products visually the way catalogue pages do |

Anything else in the sheet (any extra column not matched above) is kept, not dropped — it gets stored per-row in the product's `attributes` JSON field, keyed by its original header text.

### AI fallback for unrecognized headers

If the synonym dictionary above can't find **either** `product_name` or `code_or_sku` in the headers, the importer automatically asks an LLM to map the columns before giving up — sending it just the header row plus the first 3 data rows (never the whole sheet), and only trusting field/header pairs that actually exist in your file. This means unusual headers like `"What It Is"`, `"Item Desc"`, `"Ref No"` still work without you having to pass `column_map` by hand. The response tells you which path was used via `column_map_source`: `"heuristic"` (dictionary matched it, instant, free), `"ai"` (fallback kicked in, ~1-2s and a fraction of a cent), or `"user"` (you passed `column_map` explicitly, which always wins over both). If the AI can't map it either — or `OPENAI_API_KEY` isn't set — you get the same clean 400 asking for an explicit `column_map`, never a crash.

**Rules:**
- At least `product_name` or `code_or_sku` must be detected (dictionary, then AI, then reject), or the whole import is rejected with a 400.
- A row with no name, no SKU, *and* no price is skipped (treated as blank/decorative).
- Rows are grouped into "pages" by `page_number` for display purposes — if you don't include a page column, everything lands on page 1.
- If auto-detection (heuristic or AI) picks the wrong header row or wrong columns, pass `header_row` and/or `column_map` explicitly — an explicit `column_map` always takes priority over both the dictionary and the AI guess.

### Example minimal CSV

```csv
Product Name,SKU,Price
Test Widget,SKU-1,199
Test Gadget,SKU-2,299
```

### Example with more fields

```csv
Item Name,Model No,MRP,Category,Page
WAVE BUDS 2,,6999,JBL BUDS,1
WAVE BEAM 2,,7499,JBL BUDS,1
GO 4,,5499,JBL SPEAKER,4
```

### Example forcing a column map (when headers are unusual)

```
POST /api/ai/bulk-upload/
file        = my_price_list.xlsx
column_map  = {"product_name":"Item Desc","code_or_sku":"Part #","price":"List Price"}
```

### Response (`201`)

```json
{
  "success": true,
  "status": "201",
  "message": "Extraction completed",
  "data": {
    "id": 9,
    "upload": { "id": 9, "original_filename": "smoke.csv", "file_size_bytes": 75, "total_pages": 1, "content_type": "application/octet-stream", "created_at": "..." },
    "status": "succeeded",
    "model_name": "spreadsheet-import",
    "result": {
      "source_file": "smoke.csv",
      "source_type": "spreadsheet",
      "sheet": "smoke.csv",
      "header_row": 1,
      "column_map": { "product_name": "product_name", "code_or_sku": "code_or_sku", "price": "price" },
      "column_map_source": "heuristic",
      "pages": [
        {
          "page_number": 1,
          "page_type": "product_listing",
          "products": [
            { "product_name": "Test Widget", "code_or_sku": "SKU-1", "price": "199", "page_number": 1 },
            { "product_name": "Test Gadget", "code_or_sku": "SKU-2", "price": "299", "page_number": 1 }
          ],
          "raw_text_summary": "2 rows from spreadsheet",
          "page_notes": "sheet=smoke.csv"
        }
      ],
      "rows_imported": 2,
      "rows_skipped": 0
    },
    "summary": { "pages_kept": 1, "products_count": 2, "advertisement_pages_skipped": 0 },
    "timing": { "duration_ms": 27, "duration_seconds": 0.03 },
    "costing": { "estimated_cost_usd": "0.000000", "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0 }
  }
}
```

Cost is `0` unless the AI column-mapping fallback triggered (see above) — the row-parsing itself never calls AI. Same underlying storage as `/api/ai/extract/`: it creates/updates an `AICatalogue` (keyed by filename) and writes `AIExtractedPage` / `AIExtractedProduct` rows, so imported products show up in `/api/ai/catalogues/` and are answerable through `/api/ai/chat/` immediately.

### Errors

| Status | Cause |
|---|---|
| 400 | not `.xlsx`/`.xlsm`/`.csv`/`.tsv`, more than one file, `.xls` (legacy), empty sheet, no `product_name`/`code_or_sku` column detected, bad `column_map` JSON |

---

## 13. Bulk-upload business cards from Excel/CSV — `POST /api/ai/cards/bulk-upload/`

Imports business-card contacts directly into the database from a spreadsheet — one row = one `AIBusinessCard`. No image, no OCR; this is for when you already have contact data in a sheet (e.g. exported from a trade show scanner app or a CRM) rather than photos of physical cards. For photos, use `POST /api/ai/cards/` (section 8) instead.

**Fully working today** — unlike the product bulk-upload above, this endpoint doesn't touch any of the models affected by the known `business_card`-required-FK issue; it only writes to `AIBusinessCard`, which has no such dependency (`image` is nullable specifically to support this row-per-contact-record flow with no photo).

### Payload (`multipart/form-data`)

| Field | Required | Notes |
|---|---|---|
| `file` | yes | `.xlsx`, `.xlsm`, `.csv`, or `.tsv` (legacy `.xls` not supported) |
| `sheet` | no | sheet name or index (xlsx only); defaults to the first sheet |
| `header_row` | no | 1-based row number where headers live; auto-detected if omitted |
| `column_map` | no | JSON string to force a mapping, e.g. `{"full_name":"Contact Person","company":"Organisation"}` |
| `max_rows` | no (default 5000, max 20000) | safety cap |

### What your Excel/CSV needs to look like

Same auto-detection approach as the product importer — column names don't need to match exactly:

| Canonical field | Recognized header names (any of these) | Required? |
|---|---|---|
| `full_name` | Full Name, Name, Contact Name, Contact Person, Person, Person Name, Customer Name | one of `full_name` **or** `company` must be present |
| `company` | Company, Company Name, Organisation, Organization, Firm, Business Name, Vendor, Employer | (see above) |
| `job_title` | Job Title, Title, Designation, Position, Role | optional |
| `emails` | Email, Emails, Email Id, Email Address, E-Mail, Mail, Mail Id | optional, **list field** — see below |
| `phones` | Phone, Phones, Mobile, Mobile Number, Contact Number, Contact No, Phone Number, Tel, Telephone, Cell | optional, **list field** |
| `website` | Website, Web, URL, Site, Web Site | optional |
| `address` | Address, Location, Full Address | optional |
| `linkedin` | LinkedIn, LinkedIn URL, LinkedIn Profile | optional |

**List fields (`emails`, `phones`):** a single cell can hold multiple values separated by a comma or semicolon, e.g. `jane@acme.com; jane.doe@gmail.com` → stored as `["jane@acme.com", "jane.doe@gmail.com"]`. Duplicates (case-insensitive) are dropped automatically.

Anything else in the sheet is kept in the card's `extras` JSON field, keyed by its original header text — same pattern as `attributes` on products.

### AI fallback for unrecognized headers

Identical mechanism to the product importer (section 12): if neither `full_name` nor `company` can be found by the dictionary, headers + a few sample rows go to an LLM to map before giving up. Verified working live — headers like `"Who"`, `"Works At"`, `"Reach Via"`, `"Ring Them"` were correctly mapped to `full_name`, `company`, `emails`, `phones` respectively with zero manual `column_map`. Response includes `column_map_source` the same way.

**Rules:**
- At least `full_name` or `company` must be detected (dictionary, then AI, then reject), or the whole import is rejected with a 400.
- A row with neither a name nor a company is skipped.
- Every imported row gets `status="succeeded"`, `model_name="excel-import"`, and `estimated_cost_usd="0.000000"` (unless the AI mapping fallback triggered, which costs a fraction of a cent **once per upload**, not per row).
- The whole batch is written in one DB transaction — if something fails partway through, nothing from that request is saved.

### Example minimal CSV

```csv
Full Name,Job Title,Company,Email,Phone,Website
Jane Doe,VP Sales,Acme Corp,jane.doe@acme.com,+1 555 123 4567,acme.com
John Smith,CTO,Beta Industries,john@beta.io; john.smith@gmail.com,555-999-1111,beta.io
```

### Example with unrecognizable headers (AI fallback)

```csv
Who,Works At,Reach Via,Ring Them
Priya Nair,Zenith Traders,priya.nair@zenith.co.in,9876543210
```

### Response (`201`)

```json
{
  "success": true,
  "status": "201",
  "message": "Bulk cards imported",
  "data": {
    "source_file": "cards_clean.csv",
    "sheet": "cards_clean.csv",
    "header_row": 1,
    "column_map": { "full_name": "Full Name", "job_title": "Job Title", "company": "Company", "emails": "Email", "phones": "Phone", "website": "Website" },
    "column_map_source": "heuristic",
    "rows_imported": 2,
    "rows_skipped": 0,
    "cards": [
      {
        "id": 2,
        "original_filename": "cards_clean.csv",
        "status": "succeeded",
        "full_name": "Jane Doe",
        "job_title": "VP Sales",
        "company": "Acme Corp",
        "emails": ["jane.doe@acme.com"],
        "phones": ["+1 555 123 4567"],
        "brands": [],
        "website": "acme.com",
        "address": "",
        "linkedin": "",
        "extras": {},
        "estimated_cost_usd": "0.000000",
        "created_at": "2026-08-19T15:32:54.065533+05:30"
      },
      {
        "id": 3,
        "full_name": "John Smith",
        "job_title": "CTO",
        "company": "Beta Industries",
        "emails": ["john@beta.io", "john.smith@gmail.com"],
        "phones": ["555-999-1111"],
        "website": "beta.io"
      }
    ]
  }
}
```

Imported cards show up immediately in `GET /api/ai/cards/` and `GET /api/ai/cards/{id}/`, filterable the same way as OCR'd cards (`?company=`, `?name=`, `?q=`).

### Errors

| Status | Cause |
|---|---|
| 400 | not `.xlsx`/`.xlsm`/`.csv`/`.tsv`, more than one file, `.xls` (legacy), file over 50MB, empty sheet, no `full_name`/`company` column detected (even after the AI fallback), bad `column_map` JSON |
| 400 | DB write failure during the batch (rare — reported as "Could not save imported cards") |
