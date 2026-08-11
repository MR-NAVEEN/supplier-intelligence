# AI app — catalogue PDF extraction

All extraction logic lives in this app. Other backend apps are not modified.

## Endpoints

Requires `Authorization: Bearer <token>` and `X-Workspace-Id`.

### `POST /api/ai/extract/`

`multipart/form-data`

| Field | Required | Notes |
|--------|----------|--------|
| `file` | yes | PDF only, max 50 MB |
| `page_mode` | yes | `full` / `first_n` / `range` |
| `page_count` | if `first_n` | e.g. `5` |
| `page_range` | if `range` | e.g. `16-20` or `1,3,5-7` |
| `model_tier` | no | `high_accuracy` (default), `balanced`, `budget` |
| `dpi` | no | default `200` |

Response envelope includes extraction JSON, `timing`, and `costing`.

### `GET /api/ai/extract/`

List recent runs for the workspace.

### `GET /api/ai/extract/{id}/`

Fetch a saved run.
