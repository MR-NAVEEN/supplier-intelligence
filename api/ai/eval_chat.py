"""Evaluate catalogue chat against gold Q&A. Uses live DB when run with local settings."""
import os
import sys

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.local')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
django.setup()

from api.ai.gold_chat import GOLD_CASES
from api.ai.services.chat import answer_question


def main():
    failed = []
    for case in GOLD_CASES:
        result = answer_question(case['q'])
        answer = result['answer']
        missing = [token for token in case['must'] if token.lower() not in answer.lower()]
        banned = [token for token in case.get('must_not', []) if token.lower() in answer.lower()]
        status = 'PASS' if not missing and not banned else 'FAIL'
        print(f"{status} {case['id']}")
        print(f"  Q: {case['q']}")
        print(f"  A: {answer}")
        if missing:
            print(f"  missing: {missing}")
        if banned:
            print(f"  banned: {banned}")
        if status == 'FAIL':
            failed.append(case['id'])
    print(f'\n{len(GOLD_CASES) - len(failed)}/{len(GOLD_CASES)} passed')
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
