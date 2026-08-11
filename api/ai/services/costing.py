import os
from decimal import Decimal, ROUND_HALF_UP

# Fallback USD per 1M tokens. Override with env so rates can be updated without code edits.
DEFAULT_RATES = {
    'gpt-5.4': {'input': Decimal('2.50'), 'output': Decimal('15.00')},
    'gpt-5.4-mini': {'input': Decimal('0.40'), 'output': Decimal('1.60')},
    'gpt-5.6-luna': {'input': Decimal('0.15'), 'output': Decimal('0.60')},
}


def _rate(model_name, kind):
    env_key = f'AI_PRICE_{kind.upper()}_PER_1M'
    raw = os.environ.get(env_key)
    if raw:
        try:
            return Decimal(str(raw))
        except Exception:
            pass
    rates = DEFAULT_RATES.get(model_name) or DEFAULT_RATES['gpt-5.4']
    return rates[kind]


def estimate_cost(model_name, prompt_tokens, completion_tokens):
    prompt_tokens = int(prompt_tokens or 0)
    completion_tokens = int(completion_tokens or 0)
    input_rate = _rate(model_name, 'input')
    output_rate = _rate(model_name, 'output')
    million = Decimal('1000000')
    cost = (Decimal(prompt_tokens) / million * input_rate) + (
        Decimal(completion_tokens) / million * output_rate
    )
    cost = cost.quantize(Decimal('0.000001'), rounding=ROUND_HALF_UP)
    total_tokens = prompt_tokens + completion_tokens
    return {
        'currency': 'USD',
        'estimated_cost_usd': cost,
        'prompt_tokens': prompt_tokens,
        'completion_tokens': completion_tokens,
        'total_tokens': total_tokens,
        'model_name': model_name,
        'breakdown': {
            'input_usd_per_1m_tokens': str(input_rate),
            'output_usd_per_1m_tokens': str(output_rate),
            'pricing_note': 'Estimate from token usage × configured rates (not an OpenAI invoice).',
        },
    }