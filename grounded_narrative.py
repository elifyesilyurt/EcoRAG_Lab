"""Fail-closed numeric narratives; source values never come from model prose."""
import json
import re

from audited_math import audited_catalog, metric_tokens, requested_operation, requested_output_unit, unsupported_scope
from ingestion_core import numeric_evidence_allowed
from temporal_scope import requested_calendar_years, requested_fiscal_years


def unavailable(lang):
    return ('İstenen bilgiyi metrik, dönem ve kapsamıyla kaynakta doğrulayamıyorum; güvenilir bir yanıt veremiyorum.'
            if lang == 'tr' else
            'The requested information cannot be verified for its metric, period and scope; no reliable source answer is available.')


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


def excerpt_catalog(query, chunks):
    """Only whole source sentences, without unverified numeric claims."""
    if requested_fiscal_years(query) or requested_calendar_years(query):
        return []  # Unlabelled prose must not inherit a fiscal/calendar period.
    ignored = {'the', 'and', 'of', 'to', 'in', 'for', 'a', 'an', 'is', 'what', 'how', 'does',
               'microsoft', 'explain', 'describe', 'strategy', 'approach', 'its'}
    wanted = set(metric_tokens(query)) - ignored
    candidates = []
    for chunk in chunks:
        if not numeric_evidence_allowed(chunk['content']):
            continue
        body = re.sub(r'^--- Document:.*?---\s*', '', chunk['content'])
        # PDF line breaks are layout, not sentence boundaries. Normalize only whitespace.
        body = re.sub(r'\s+', ' ', body).strip()
        sentences = re.split(r'(?<=[.!?])\s+', body)
        for index, sentence in enumerate(sentences):
            sentence = sentence.strip()
            if (len(sentence) < 35 or len(sentence) > 1200 or has_numeric_claim(sentence)
                    or not sentence[0].isupper() or sentence[-1] not in '.!?'
                    or sentence.startswith(('Metric:', 'Basis:', '[', 'Header:'))):
                continue
            if len(wanted & set(metric_tokens(sentence))) < 2 or unsupported_scope(query, sentence):
                continue
            candidates.append({'evidence_id': chunk['id'], 'sentence_index': index,
                               'text': sentence, 'source': chunk['title']})
    return candidates


def validate_excerpt_selection(raw, catalog, lang):
    try:
        selected = json.loads(raw) if isinstance(raw, str) else raw
        if not isinstance(selected, dict) or set(selected) != {'references'}:
            raise ValueError('Only source references are permitted')
        refs = selected['references']
        if not isinstance(refs, list) or not 1 <= len(refs) <= 5:
            raise ValueError('Select one to five complete source sentences')
        lookup = {(c['evidence_id'], c['sentence_index']): c for c in catalog}
        seen, lines = set(), []
        for ref in refs:
            if (not isinstance(ref, dict) or set(ref) != {'evidence_id', 'sentence_index'}
                    or any(type(v) is not int for v in ref.values())):
                raise ValueError('Invalid source reference')
            key = (ref['evidence_id'], ref['sentence_index'])
            if key not in lookup or key in seen:
                raise ValueError('Unknown or duplicate source sentence')
            seen.add(key)
            row = lookup[key]
            lines.append(f"{row['text']}\n{row['source']}")
        label = 'Kaynakta yer alan ilgili ifadeler:' if lang == 'tr' else 'Relevant source excerpts:'
        return {'status': 'source_excerpt', 'answer': label + '\n\n' + '\n\n'.join(lines),
                'references': refs}
    except (ValueError, TypeError, KeyError):
        return {'status': 'qualitative_claim_rejected', 'answer': unavailable(lang), 'references': []}


def generate_grounded_narrative(query, chunks, lang, model):
    direct = source_narrative(query, chunks, lang)
    if direct is not None:
        return direct
    catalog = excerpt_catalog(query, chunks)
    if not catalog:
        return {'status': 'unavailable', 'answer': unavailable(lang), 'references': []}
    system = ('Select complete source sentences relevant to the question. Return only JSON: '
              '{"references": [{"evidence_id": 1, "sentence_index": 0}]}. '
              'Use actual catalog IDs. Select up to five sentences. Do not write an answer, '
              'rewrite a quotation, omit negation, or add explanations. If unsupported, return {"references": []}.')
    prompt = json.dumps(catalog, ensure_ascii=False) + '\nQuestion: ' + query
    attempts = []
    for _ in range(2):
        draft = model(system, prompt, temperature=.1, max_tokens=512, preserve_format=True)
        result = validate_excerpt_selection(draft, catalog, lang)
        attempts.append({'draft': draft, 'status': result['status']})
        if result['status'] == 'source_excerpt':
            break
        prompt += '\nThe selection was invalid or empty. Return only the required JSON references to actual catalog sentences, or an empty references list if none support the question. No prose or additional brackets.'
    result['attempts'] = attempts
    return result
