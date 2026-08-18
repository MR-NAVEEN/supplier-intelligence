import json
import os
import re
import time

from django.db import connection

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

from api.ai.models import AICatalogue, AIExtractedPage, AIExtractedProduct
from api.ai.services.extraction import MODEL_TIERS

MAX_SQL_RETRIES = 3
MAX_SAMPLE_ROWS = 5

MODEL_MAP = {
    AICatalogue._meta.db_table: AICatalogue,
    AIExtractedPage._meta.db_table: AIExtractedPage,
    AIExtractedProduct._meta.db_table: AIExtractedProduct,
}
ALLOWED_TABLES = frozenset(MODEL_MAP)

PRIMARY_MODEL = MODEL_TIERS['balanced']
FALLBACK_MODELS = (MODEL_TIERS['high_accuracy'], 'gpt-4o-mini')

DIALECT_READ_ONLY = {
    'sqlite': 'SELECT or WITH',
    'postgresql': 'SELECT or WITH',
    'mysql': 'SELECT or WITH',
}

BANNED_SQL_KEYWORDS = (
    'INSERT', 'UPDATE', 'DELETE', 'DROP', 'ALTER', 'CREATE', 'REPLACE', 'ATTACH', 'DETACH', 'PRAGMA',
)

ANALYZE_PROMPT = """\
You are a friendly, expert {dialect} data analyst answering questions about a product catalogue database.
Study the schema knowledge and infer which tables/columns/joins answer the user.

Return JSON only:
{{
  "status": "query" | "clarify" | "off_topic",
  "sql": "SELECT ..." or null,
  "message": "natural human reply when not executing SQL",
  "sample_questions": ["..."]
}}

Rules:
- Use only read-only SQL ({read_only_clause}).
- Use relations from the knowledge base to choose JOINs.
- Use LIKE for fuzzy text search when helpful.
- Do NOT add LIMIT unless the user explicitly asks for top/first/limited rows.
- Select only columns needed to answer the question.
- Apply precise WHERE filters from the question (e.g. brand, product name, price criteria, page number).
- ai_aiextractedproduct and ai_aiextractedpage keep old superseded rows from prior extraction runs.
  ALWAYS filter is_current = 1 on both tables unless the user explicitly asks about history/previous versions.
- status=query when you can write SQL confidently.
- status=clarify when the question is vague but likely about this catalogue data;
  ask one helpful follow-up in message and include sample_questions.
- status=off_topic when unrelated to catalogues/products;
  explain politely in message and include sample_questions the user could ask.

SCHEMA KNOWLEDGE:
{schema_context}
"""

FIX_SQL_PROMPT = """\
You fix broken {dialect} queries for a catalogue data analyst agent.
Return JSON: {{"sql":"..."}}.
Keep queries read-only ({read_only_clause}). Do not add LIMIT unless the user asked for limited rows.
ai_aiextractedproduct and ai_aiextractedpage keep old superseded rows; keep any is_current = 1 filter intact.

SCHEMA KNOWLEDGE:
{schema_context}
"""

RESPOND_PROMPT = """\
You are a concise business assistant. Answer ONLY what the user asked — nothing extra.

Rules:
- Use only the query results provided. Do not invent data.
- If the user specified a catalogue, brand, product, or price — answer only for that scope.
- Do NOT offer follow-up suggestions unless there are zero matching rows.
- If row_count is greater than the sample size, state the total count and summarize the sample; do not list every row.
- Keep the answer to 1-3 short sentences. No markdown bold, no bullet dumps.
- If no rows match, say so in one sentence and suggest one clearer filter.
"""

FAILURE_PROMPT = """\
You are a helpful catalogue database assistant.
The user's question could not be answered because the SQL failed.
Explain what went wrong in plain language and suggest 3 better questions.
Be natural and concise.

SCHEMA KNOWLEDGE:
{schema_context}
"""


def _truncate(value, limit=120):
    if value is None:
        return None
    text = str(value)
    return text if len(text) <= limit else text[: limit - 3] + '...'


def _relation_lines():
    lines = []
    for table, model in MODEL_MAP.items():
        for field in model._meta.fields:
            if field.is_relation and field.related_model in MODEL_MAP.values():
                lines.append(
                    f'{table}.{field.column} -> {field.related_model._meta.db_table}.{field.related_model._meta.pk.column}'
                )
    return lines


def build_schema_context():
    lines = [f'database={connection.vendor} tables={len(ALLOWED_TABLES)}', 'relations:']
    lines += [f'  - {line}' for line in _relation_lines()]
    for table, model in sorted(MODEL_MAP.items()):
        cols = ', '.join(
            f"{f.column}{'*' if f.primary_key else ''}:{f.get_internal_type()}" for f in model._meta.fields
        )
        lines.append(f'\n{table} [{model.objects.count()} rows]')
        lines.append(f'  columns: {cols}')
        for idx, obj in enumerate(model.objects.order_by('-id')[:2], start=1):
            sample = {f.column: _truncate(getattr(obj, f.attname)) for f in model._meta.fields}
            lines.append(f'  sample_{idx}: {json.dumps(sample, default=str, ensure_ascii=False)}')
    return '\n'.join(lines)


def _cte_names(sql):
    return {m.lower() for m in re.findall(r'(?:\bWITH\b|,)\s*([a-zA-Z_][a-zA-Z0-9_]*)\s+AS\s*\(', sql, re.IGNORECASE)}


def _referenced_tables(sql):
    return {m.lower() for m in re.findall(r'\b(?:from|join)\s+"?([a-zA-Z_][a-zA-Z0-9_]*)"?', sql, re.IGNORECASE)}


def is_allowed_sql(sql):
    cleaned = re.sub(r'--.*?\n|/\*.*?\*/', ' ', sql, flags=re.S).strip()
    if not cleaned:
        return False
    first = cleaned.split(None, 1)[0].upper()
    if first not in {'SELECT', 'WITH'}:
        return False
    upper = cleaned.upper()
    if any(re.search(rf'\b{word}\b', upper) for word in BANNED_SQL_KEYWORDS):
        return False
    tables = _referenced_tables(cleaned) - _cte_names(cleaned)
    return bool(tables) and tables.issubset(ALLOWED_TABLES)


def execute_sql(sql):
    if not is_allowed_sql(sql):
        raise ValueError('Only read-only SELECT/WITH queries against catalogue tables are allowed.')
    with connection.cursor() as cursor:
        cursor.execute(sql)
        cols = [c[0] for c in cursor.description or []]
        rows = [dict(zip(cols, row)) for row in cursor.fetchall()]
    return cols, rows


def _require_client():
    if OpenAI is None:
        raise RuntimeError('openai package is not installed. Run: pip install openai')
    api_key = os.environ.get('OPENAI_API_KEY', '')
    if not api_key:
        raise RuntimeError('OPENAI_API_KEY is not set.')
    return OpenAI(api_key=api_key)


def _chat(messages, json_mode=False, temperature=0.2):
    client = _require_client()
    last_error = None
    for model in (PRIMARY_MODEL, *FALLBACK_MODELS):
        use_temperature = True
        for _ in range(2):
            try:
                kwargs = {'model': model, 'messages': messages}
                if json_mode:
                    kwargs['response_format'] = {'type': 'json_object'}
                if use_temperature:
                    kwargs['temperature'] = temperature
                resp = client.chat.completions.create(**kwargs)
                return resp.choices[0].message.content or ''
            except Exception as exc:  # noqa: BLE001 - model/param fallback chain
                last_error = exc
                msg = str(exc).lower()
                if use_temperature and 'temperature' in msg and 'unsupported' in msg:
                    use_temperature = False
                    continue
                break
    raise RuntimeError(f'Could not reach OpenAI API: {last_error}')


def _chat_json(messages, temperature=0):
    content = _chat(messages, json_mode=True, temperature=temperature)
    return json.loads(content)


class _SQLAgent:
    def __init__(self):
        self.dialect = connection.vendor
        self.read_only_clause = DIALECT_READ_ONLY.get(self.dialect, 'SELECT or WITH')
        self.schema_context = build_schema_context()

    def analyze(self, question, catalogue_hint=None):
        system = ANALYZE_PROMPT.format(
            dialect=self.dialect, read_only_clause=self.read_only_clause, schema_context=self.schema_context
        )
        user_content = question
        if catalogue_hint:
            user_content = (
                f'{question}\n\n(Context: the user is currently focused on catalogue id={catalogue_hint}; '
                'prefer filtering to that catalogue unless the question clearly asks about something else.)'
            )
        return _chat_json([{'role': 'system', 'content': system}, {'role': 'user', 'content': user_content}])

    def fix_sql(self, question, sql, error):
        system = FIX_SQL_PROMPT.format(
            dialect=self.dialect, read_only_clause=self.read_only_clause, schema_context=self.schema_context
        )
        payload = json.dumps({'question': question, 'sql': sql, 'error': error}, default=str, ensure_ascii=False)
        result = _chat_json([{'role': 'system', 'content': system}, {'role': 'user', 'content': payload}])
        return str(result.get('sql', '')).strip()

    def respond(self, question, rows):
        payload = json.dumps(
            {
                'question': question,
                'row_count': len(rows),
                'sample_size': min(len(rows), MAX_SAMPLE_ROWS),
                'rows_sample': rows[:MAX_SAMPLE_ROWS],
                'note': 'Answer only the user question. Full data stays in DB; you see a sample only.',
            },
            default=str,
            ensure_ascii=False,
        )
        return _chat(
            [{'role': 'system', 'content': RESPOND_PROMPT}, {'role': 'user', 'content': payload}],
            temperature=0.4,
        ).strip()

    def explain_failure(self, question, sql, error):
        system = FAILURE_PROMPT.format(schema_context=self.schema_context)
        payload = json.dumps({'question': question, 'sql': sql, 'error': error}, default=str, ensure_ascii=False)
        return _chat(
            [{'role': 'system', 'content': system}, {'role': 'user', 'content': payload}],
            temperature=0.4,
        ).strip()

    def handle(self, question, catalogue_hint=None):
        question = (question or '').strip()
        if not question:
            return {
                'answer': 'Please enter a question about the catalogue data.',
                'intent': 'clarify',
                'sources': [],
                'context': {},
            }

        analysis = self.analyze(question, catalogue_hint=catalogue_hint)
        status = analysis.get('status', 'clarify')

        if status in {'clarify', 'off_topic'}:
            message = (analysis.get('message') or '').strip()
            samples = analysis.get('sample_questions') or []
            if samples:
                message = f'{message}\n\nYou could ask:\n' + '\n'.join(f'- {item}' for item in samples[:2])
            return {'answer': message, 'intent': status, 'sources': [], 'context': {'sample_questions': samples}}

        sql = (analysis.get('sql') or '').strip().rstrip(';')
        if not sql:
            return {
                'answer': analysis.get('message') or "I couldn't turn that into a query. Could you rephrase?",
                'intent': 'clarify',
                'sources': [],
                'context': {},
            }

        last_error = ''
        for attempt in range(1, MAX_SQL_RETRIES + 1):
            try:
                cols, rows = execute_sql(sql)
                answer = self.respond(question, rows)
                return {
                    'answer': answer,
                    'intent': 'query',
                    'sources': rows[:MAX_SAMPLE_ROWS],
                    'context': {'sql': sql, 'row_count': len(rows)},
                }
            except Exception as exc:  # noqa: BLE001 - self-heal via LLM
                last_error = str(exc)
                if attempt >= MAX_SQL_RETRIES:
                    break
                sql = self.fix_sql(question, sql, last_error).rstrip(';')
                if not sql:
                    break
                time.sleep(1)

        return {
            'answer': self.explain_failure(question, sql, last_error),
            'intent': 'error',
            'sources': [],
            'context': {'sql': sql},
        }


def answer_question(question, catalogue_id=None, last_context=None):
    agent = _SQLAgent()
    result = agent.handle(question, catalogue_hint=catalogue_id)
    return result
