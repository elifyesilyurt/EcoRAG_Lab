"""Fail-closed numeric narratives; source values never come from model prose."""
import re

from answer_prompts import build_rag_prompts
from audited_math import audited_catalog, metric_tokens, requested_operation, requested_output_unit, unsupported_scope
from ingestion_core import build_evidence_context
from temporal_scope import requested_calendar_years, requested_fiscal_years


def unavailable(lang):
    return ('İstenen sayısal iddiayı metrik, dönem ve kapsamıyla doğrulayamıyorum; güvenilir bir sayı veremiyorum.'
            if lang == 'tr' else
            'The requested numeric claim cannot be verified for its metric, period and scope; no reliable value is available.')


def has_numeric_claim(text):
    # Year/page numbers also require source binding. Do not silently exempt them.
    words = (r'zero|half|quarter|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|'
             r'sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|'
             r'hundred|thousand|million|billion|trillion|percent|percentage|'
             r'sıfır|yarım|çeyrek|bir|iki|üç|dört|beş|altı|yedi|sekiz|dokuz|on|yirmi|otuz|kırk|elli|yüz|bin|milyon|milyar|yüzde')
    return bool(re.search(r'\d|[%‰]|\b(?:' + words + r')\b', text, re.IGNORECASE))


def source_narrative(query, chunks, lang):
    """Direct source lookup requires an explicit period and core metric tokens; omitted source scope stays explicit in the answer.

    Multiple metrics or missing columns never fall back to another year/metric.
    Arithmetic belongs to the separate audited calculation route.
    """
    periods = requested_fiscal_years(query) + requested_calendar_years(query)
    if not periods or requested_operation(query):
        return None
    question_tokens = set(metric_tokens(query))
    matches = {}
    for row in audited_catalog(chunks).values():
        words = set(metric_tokens(re.sub(r'\([^)]*\)', '', row['metric']))) - {'total', 'the', 'and', 'of', 'to', 'in', 'primary', 'product', 'operational'}
        if len(words) >= 2 and words.issubset(question_tokens):
            matches.setdefault(row['metric'], []).append(row)
    if len(matches) != 1:
        return None
    rows = next(iter(matches.values()))
    unit = requested_output_unit(query)
    if unit and any(row['unit'] != unit for row in rows):
        # Unit conversion/arithmetic must use the audited calculation route.
        return {'status': 'unavailable', 'answer': unavailable(lang), 'references': []}
    # A request to distinguish bases must not itself turn a contracted-volume
    # question into a realized-removal request.
    subject = re.split(r'[?.!]', query, maxsplit=1)[0]
    if any(unsupported_scope(subject, row['metric']) for row in rows):
        return {'status': 'unavailable', 'answer': unavailable(lang), 'references': []}
    if ('contracted' in rows[0]['metric'].lower()
            and re.search(r'\b(realized|delivered|retired)\b|gerçekleş|fiili', subject.lower())):
        return {'status': 'unavailable', 'answer': unavailable(lang), 'references': []}
    references, lines = [], []
    for period in periods:
        candidates = [row for row in rows if period in row['periods']]
        if len(candidates) != 1:
            return {'status': 'unavailable', 'answer': unavailable(lang), 'references': []}
        row = candidates[0]
        value = row['periods'][period]
        if value == '[NOT REPORTED]' or (re.search(r'\bexact\b|kesin|tam olarak', query.lower())
                                        and not re.fullmatch(r'-?\d+(?:\.\d+)?', value)):
            return {'status': 'unavailable', 'answer': unavailable(lang), 'references': []}
        # Literal audited disclosure preserves "more than" rather than turning
        # a qualified commitment into an exact or realized quantity.
        lines.append(f"{period} — {row['metric']}: {value}.\n{row['source']}")
        lines.extend(row['qualifications'])
        references.append({'evidence_id': row['evidence_id'], 'period': period})
    return {'status': 'source_bound', 'answer': '\n\n'.join(dict.fromkeys(lines)), 'references': references}


def generate_grounded_narrative(query, chunks, lang, model):
    direct = source_narrative(query, chunks, lang)
    if direct is not None:
        return direct
    system, prompt = build_rag_prompts(build_evidence_context(chunks), query, lang)
    draft = model(system, prompt, temperature=.1, max_tokens=1024)
    if not isinstance(draft, str) or has_numeric_claim(draft):
        return {'status': 'numeric_claim_rejected', 'answer': unavailable(lang),
                'references': [], 'draft': draft}
    return {'status': 'qualitative_unverified', 'answer': draft, 'references': []}
