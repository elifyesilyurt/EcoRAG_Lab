"""Real retrieval/model evaluation; no mocked model and no UI import.

Static topic summaries, UI streaming, and Turkish query translation are excluded.
Narrative answers use the production prompt; math uses the production extractor
and restricted evaluator. Rule-based scores are regression signals, not a
complete semantic/faithfulness assessment. Save raw answers for human review.
"""
import argparse
import gc
import json
import math
from pathlib import Path
import re
import sqlite3
import sys
from typing import Optional

from answer_prompts import build_rag_prompts
from dynamic_math_engine import DynamicMathExecutor, POT_EXTRACTION_SYSTEM_PROMPT
from ingestion_core import (INDEX_VERSION, build_evidence_context, numeric_evidence_allowed,
                            prioritize_audited_evidence, select_evidence_chunks, source_hash)
from query_routing import is_esg_query
from temporal_scope import (requested_fiscal_years, retrieval_report_years,
                            select_temporal_chunks, temporal_evidence_instruction)
from test_baseline_regressions import load_app_functions

ROOT = Path(__file__).resolve().parent


def answer_numbers(answer):
    # English evaluation narrative: grouping commas are distinct from decimals.
    return [float(value.replace(',', '')) for value in re.findall(r'(?<!\w)-?\d+(?:,\d{3})*(?:\.\d+)?', answer)]


def score_case(case, record):
    if record.get('error'):
        return False
    mode = case['mode']
    if mode == 'out_of_domain':
        return record.get('status') == 'out_of_domain'
    if mode == 'no_evidence':
        return record.get('status') == 'no_evidence'
    if mode == 'math':
        result = record.get('math', {})
        return bool(result.get('success') and isinstance(result.get('result'), (int, float))
                    and math.isclose(result['result'], case['expected_result'],
                                     rel_tol=0, abs_tol=case.get('tolerance', .000001)))
    if mode == 'math_abstain':
        # A crash/invalid syntax is not evidence of deliberate abstention.
        raw = record.get('raw_code', '').lower()
        return bool(not record.get('math', {}).get('success') and
                    any(token in raw for token in ('unavailable', 'not reported', 'cannot', 'not exact', 'insufficient')))
    answer = record.get('answer', '')
    numbers = answer_numbers(answer)
    return (all(any(math.isclose(actual, value, rel_tol=0, abs_tol=.000001) for actual in numbers)
                for value in case.get('required_numbers', []))
            and not any(any(math.isclose(actual, value, rel_tol=0, abs_tol=.000001) for actual in numbers)
                        for value in case.get('forbidden_numbers', []))
            and all(any(token.lower() in answer.lower() for token in group)
                    for group in case.get('required_groups', [])))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', required=True, help='Running local Foundry endpoint')
    parser.add_argument('--model', default='phi-4-mini')
    parser.add_argument('--output', required=True)
    parser.add_argument('--case', help='Run one fixture ID')
    args = parser.parse_args()
    import requests
    report = {'status': 'running', 'model': args.model, 'endpoint': args.base_url,
              'index_sha256': source_hash(ROOT / 'rag_storage.db'), 'cases': [],
              'limitations': 'Rule checks are not full semantic validation; inspect raw answers. UI/translation/static routes excluded.'}
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    def save():
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    try:
        response = requests.get(args.base_url.rstrip('/') + '/v1/models', timeout=5)
        response.raise_for_status()
        report['available_models'] = response.json()
    except (requests.RequestException, ValueError) as exc:
        report.update(status='blocked', error=f'Model endpoint unavailable: {exc}')
        save()
        print(report['error'], file=sys.stderr)
        return 2
    import numpy as np
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer('nomic-ai/nomic-embed-text-v1.5', trust_remote_code=True)
    app = load_app_functions({'search_context_hybrid', 'query_foundry', 'trim_repetition'}, {
        'Optional': Optional, 'gc': gc, 'json': json, 're': re, 'sqlite3': sqlite3, 'np': np,
        'requests': requests, 'get_foundry_base_url': lambda: args.base_url.rstrip('/'), 'MODEL_NAME': args.model,
        'DB_PATH': str(ROOT / 'rag_storage.db'), 'embedder': model, 'MAX_K': 6,
        'RELATIVE_DROP_RATIO': .70, 'MIN_SCORE_FLOOR': .15,
        'retrieval_report_years': retrieval_report_years, 'requested_fiscal_years': requested_fiscal_years,
        'select_temporal_chunks': select_temporal_chunks, 'INDEX_VERSION': INDEX_VERSION,
        'numeric_evidence_allowed': numeric_evidence_allowed, 'prioritize_audited_evidence': prioritize_audited_evidence,
    })
    fixtures = json.loads((ROOT / 'tests/fixtures/answer_evaluation.json').read_text())
    if args.case:
        fixtures = [case for case in fixtures if case['id'] == args.case]
        if not fixtures:
            parser.error('Unknown fixture ID')
    for case in fixtures:
        record = {'id': case['id'], 'query': case['query'], 'mode': case['mode']}
        try:
            if not is_esg_query(case['query']):
                record['status'] = 'out_of_domain'
            else:
                chunks, score = app['search_context_hybrid'](case['query'])
                chunks = select_evidence_chunks(chunks, scope_query=case['query'])
                record.update(score=score, evidence=chunks)
                if not chunks or score < .15:
                    record['status'] = 'no_evidence'
                elif case['mode'] in ('math', 'math_abstain'):
                    prompt = (temporal_evidence_instruction(case['query']) + '\n\nContext:\n'
                              + build_evidence_context(chunks) + '\n\nQuestion: ' + case['query']
                              + '\n\nExecutable Python code:')
                    raw = app['query_foundry'](POT_EXTRACTION_SYSTEM_PROMPT, prompt, temperature=0)
                    record.update(status='generated', raw_code=raw, math=DynamicMathExecutor.execute_code_lines(raw))
                else:
                    system, prompt = build_rag_prompts(build_evidence_context(chunks), case['query'], case['lang'])
                    record.update(status='generated', answer=app['query_foundry'](system, prompt, temperature=.1, max_tokens=1024))
        except Exception as exc:
            record.update(status='error', error=f'{type(exc).__name__}: {exc}')
        record['passed'] = score_case(case, record)
        report['cases'].append(record)
        save()
        print(case['id'], 'PASS' if record['passed'] else 'FAIL', flush=True)
    report.update(status='completed', passed=sum(row['passed'] for row in report['cases']), total=len(report['cases']))
    save()
    return 0 if report['passed'] == report['total'] else 1


if __name__ == '__main__':
    sys.exit(main())
