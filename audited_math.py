"""Arithmetic over selected audited evidence, never model-supplied numbers/code."""
import json
import math
import re
from decimal import Decimal

from temporal_scope import requested_fiscal_years

UNITS = {'mt': ('mass', Decimal(1)), 'mtCO2e': ('emissions', Decimal(1)),
         'million m3': ('volume', Decimal(1000000)), 'm3': ('volume', Decimal(1)),
         'ML': ('volume', Decimal(1000)), 'MWh': ('energy', Decimal(1)),
         'kWh': ('energy', Decimal('.001')), '%': ('percentage', Decimal(1))}
OPERATIONS = {'value', 'sum', 'difference', 'ratio', 'percent_of', 'percent_change', 'percentage_point_change'}
PLAN_PROMPT = '''Select audited source rows and periods for the question. Return only JSON; no Python or numeric values.
Difference example (TWO inputs): {"available": true, "operation": "difference", "operands": [{"evidence_id": 1, "period": "FY25"}, {"evidence_id": 2, "period": "FY25"}]}.
Value/conversion example (ONE input): {"available": true, "operation": "value", "operands": [{"evidence_id": 1, "period": "FY25"}]}.
The example IDs are placeholders; use actual IDs from the catalog. Allowed operation names: value, difference, sum, ratio, percent_of, percent_change, percentage_point_change.
Value: select ONE source row for a quantity or unit conversion; no subtraction. Difference: first minus second. Percent_of: first divided by second times 100. Percent_change: (second minus first) / first times 100, chronological old then new. Percentage_point_change: second minus first, both source percentages. Ratio: first divided by second. Sum: add all operands.
Choose the exact metric, scope and requested period; include each needed input exactly once. Python owns the requested output unit and all conversion. Allowed units: mt, mtCO2e, million m3, m3, ML, MWh, kWh, %, ratio, percentage points.
Qualified disclosures are NOT exact values. Contracted commitments are not realized removals. If data/operation is unavailable or ambiguous, return {"available": false}. Never invent an evidence ID or a source value.''' 


def audited_catalog(chunks):
    catalog = {}
    for chunk in chunks:
        if chunk.get('chunk_type') != 'audited_table':
            continue
        metric = re.search(r'^Metric: (.+)$', chunk['content'], re.MULTILINE)
        if not metric:
            continue
        unit = next((unit for unit in sorted(UNITS, key=len, reverse=True)
                     if metric.group(1).endswith(f'({unit})')), None)
        if unit is None:
            continue
        values = dict(re.findall(r'^(FY\d{2}|CY\d{4}): (.+)$', chunk['content'], re.MULTILINE))
        catalog[chunk['id']] = {'evidence_id': chunk['id'], 'metric': metric.group(1),
                                'unit': unit, 'periods': values, 'source': chunk['title'],
                                'qualifications': re.findall(r'^(?:Basis|Inventory scope): (.+)$', chunk['content'], re.MULTILINE)}
    return catalog


def plan_user_prompt(query, chunks):
    return ('Audited rows:\n' + json.dumps(list(audited_catalog(chunks).values()), ensure_ascii=False)
            + '\nQuestion: ' + query + '\nPython output unit: ' + str(requested_output_unit(query))
            + '\nOperand objects have ONLY evidence_id and period, no unit or value. Python selects/converts output units; do not choose output_unit. For one source quantity/unit conversion use operation value and exactly one operand.')


def requested_output_unit(query):
    q = query.lower()
    patterns = [(r'percentage[ -]points?|yüzde puan', 'percentage points'),
                (r'million (?:m3|cubic met(?:er|re)s)|milyon (?:m3|metreküp)', 'million m3'),
                (r'cubic met(?:er|re)s|metreküp|\bm\^?3\b|m³', 'm3'),
                (r'\bkwh\b|kilowatt[ -]hours?', 'kWh'), (r'\bmwh\b|megawatt[ -]hours?', 'MWh'),
                (r'\bml\b|megalit(?:er|re)s?', 'ML'),
                (r'mtco2e|co2 equivalent', 'mtCO2e'), (r'metric tons?|metrik ton', 'mt'),
                (r'percentage|yüzde|\bpercent\b', '%')]
    return next((unit for pattern, unit in patterns if re.search(pattern, q)), None)


def execute_audited_plan(raw, chunks, query):
    def reject(status, reason):
        return {'success': False, 'status': status, 'reason': reason, 'result': None, 'operands': []}
    try:
        if isinstance(raw, str):
            raw = raw.strip()
            if raw.startswith('```json\n') and raw.endswith('\n```'):
                raw = raw[8:-4]
            plan = json.loads(raw)
        else:
            plan = raw
        if not isinstance(plan, dict) or type(plan.get('available')) is not bool:
            return reject('invalid_plan', 'Expected a boolean availability field.')
        if not plan['available']:
            if set(plan) != {'available'}:
                return reject('invalid_plan', 'Unavailable plan must not contain a calculation.')
            return reject('unavailable', 'Exact data or an unambiguous operation is unavailable.')
        if (not {'available', 'operation', 'operands'}.issubset(plan)
                or set(plan) - {'available', 'operation', 'operands', 'output_unit'}):
            return reject('invalid_plan', 'Only source references, operation and output unit are permitted.')
        op = plan['operation']
        if op not in OPERATIONS or not isinstance(plan['operands'], list):
            return reject('invalid_plan', 'Unsupported operation.')
        refs = plan['operands']
        if (not refs or (op == 'value' and len(refs) != 1)
                or (op not in {'sum', 'value'} and len(refs) != 2) or len(refs) > 20):
            return reject('invalid_plan', f'{op} requires ' + ('exactly ONE source reference.' if op == 'value' else 'at least one source reference.' if op == 'sum' else 'exactly TWO source references, one for each input.'))
        catalog, operands, seen = audited_catalog(chunks), [], set()
        required_periods = set(requested_fiscal_years(query))
        for ref in refs:
            if not isinstance(ref, dict) or set(ref) != {'evidence_id', 'period'}:
                return reject('invalid_plan', 'Model-supplied values/units are forbidden.')
            key, period = ref['evidence_id'], ref['period']
            if type(key) is not int or not isinstance(period, str) or key not in catalog:
                return reject('invalid_plan', 'Unknown audited evidence reference.')
            if required_periods and period not in required_periods:
                return reject('invalid_plan', 'Operand period does not match requested fiscal years.')
            if (key, period) in seen:
                return reject('invalid_plan', 'Duplicate operand.')
            seen.add((key, period))
            source = catalog[key]
            if ('Contracted' in source['metric']
                    and re.search(r'\b(realized|delivered|retired)\b|gerçekleş|fiili|teslim edilen', query.lower())):
                return reject('unavailable', 'Contracted commitments cannot answer a realized/delivered removal request.')
            text = source['periods'].get(period, '')
            if not re.fullmatch(r'-?\d+(?:\.\d+)?', text):
                return reject('unavailable', 'Exact source value unavailable; qualified or missing data cannot be used.')
            value = Decimal(text)
            dim, scale = UNITS[source['unit']]
            operands.append(dict(source, period=period, value=text, base_value=value * scale, dimension=dim))
        if required_periods and {o['period'] for o in operands} != required_periods:
            return reject('invalid_plan', 'All requested fiscal periods must be represented.')
        if len({o['dimension'] for o in operands}) != 1:
            return reject('invalid_plan', 'Incompatible dimensions.')
        if (op in {'percent_change', 'percentage_point_change'}
                and (operands[0]['metric'] != operands[1]['metric'] or operands[0]['period'] >= operands[1]['period'])):
            return reject('invalid_plan', 'Temporal change requires the same metric, oldest period first.')
        # Output units come from the human question/operation, never model metadata.
        default_unit = ('ratio' if op == 'ratio' else '%' if op in {'percent_of', 'percent_change'}
                        else 'percentage points' if op == 'percentage_point_change' else operands[0]['unit'])
        target = requested_output_unit(query) or default_unit
        values = [o['base_value'] for o in operands]
        if op in {'ratio', 'percent_of'}:
            if not values[1]:
                return reject('unavailable', 'Division by zero.')
            if target != ('ratio' if op == 'ratio' else '%'):
                return reject('invalid_plan', 'Wrong dimensionless output unit.')
            result = values[0] / values[1] * (100 if op == 'percent_of' else 1)
        elif op == 'percent_change':
            if target != '%':
                return reject('invalid_plan', 'Percent change requires % output.')
            if not values[0]:
                return reject('unavailable', 'Percent change has a zero baseline.')
            result = (values[1] - values[0]) / values[0] * 100
        elif op == 'percentage_point_change':
            if target != 'percentage points' or operands[0]['dimension'] != 'percentage':
                return reject('invalid_plan', 'Percentage-point change requires percentage inputs.')
            result = values[1] - values[0]
        else:
            if target not in UNITS or UNITS[target][0] != operands[0]['dimension']:
                return reject('invalid_plan', 'Output unit is incompatible with inputs.')
            numerator = values[0] if op == 'value' else sum(values) if op == 'sum' else values[0] - values[1]
            result = numerator / UNITS[target][1]
        if not result.is_finite() or not math.isfinite(float(result)):
            return reject('invalid_plan', 'Non-finite result.')
        clean = [{k: v for k, v in o.items() if k not in {'base_value', 'dimension', 'periods'}} for o in operands]
        return {'success': True, 'status': 'computed', 'result': float(result), 'result_text': format(result, 'f'),
                'result_name': 'result', 'unit': target, 'operation': op, 'operands': clean}
    except (ValueError, TypeError, KeyError, ArithmeticError) as exc:
        return reject('invalid_plan', f'Invalid calculation plan: {exc}')


def render_audited_result(result, lang='en'):
    if not result['success']:
        return ('Doğrulanmış verilerle bu hesaplama yapılamadı. ' if lang == 'tr' else
                'This calculation could not be completed using validated evidence. ') + result['reason']
    lines = [f"{result['result_text']} {result['unit']}", f"Operation: {result['operation']}"]
    for item in result['operands']:
        lines.append(f"{item['metric']} — {item['period']}: {item['value']} {item['unit']}; {item['source']}")
    notes = dict.fromkeys(note for item in result['operands'] for note in item.get('qualifications', []))
    lines.extend(notes)
    return '\n\n'.join(lines)


def calculate_with_model(query, chunks, model_call):
    """One bounded schema-repair attempt; unavailable evidence is never retried."""
    prompt = plan_user_prompt(query, chunks)
    attempts = []
    for attempt in range(2):
        raw = model_call(PLAN_PROMPT, prompt, temperature=0.0, preserve_format=True)
        result = execute_audited_plan(raw, chunks, query)
        attempts.append({'raw_plan': raw, 'status': result['status'], 'reason': result.get('reason')})
        if result['status'] != 'invalid_plan' or attempt == 1:
            return result, attempts
        prompt = (plan_user_prompt(query, chunks) + '\nPrevious invalid plan:\n' + raw
                  + '\nValidation error: ' + result['reason']
                  + '\nCorrect the JSON schema, requested output unit and source references. Do not add operand units/values. Return only valid JSON.')
    raise AssertionError('Unreachable')
