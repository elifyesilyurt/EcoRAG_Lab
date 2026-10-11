"""Arithmetic over selected audited evidence, never model-supplied numbers/code."""
import json
import math
import re
import unicodedata
from decimal import Decimal

from temporal_scope import requested_fiscal_years, requested_calendar_years

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
            + '\nRequired operation from question: ' + str(requested_operation(query))
            + '\nOperand objects have ONLY evidence_id and period, no unit or value. Python selects/converts output units; do not choose output_unit. For one source quantity/unit conversion use operation value and exactly one operand.')


def requested_output_unit(query):
    q = ''.join(c for c in unicodedata.normalize('NFD', query.lower().replace('ı', 'i'))
                if unicodedata.category(c) != 'Mn')
    patterns = [(r'percentage[ -]points?|yuzde puan', 'percentage points'),
                (r'million (?:m3|cubic met(?:er|re)s)|milyon (?:m3|metrekup)', 'million m3'),
                (r'cubic met(?:er|re)s|metrekup|\bm\^?3\b|m³', 'm3'),
                (r'\bkwh\b|kilowatt[ -]hours?', 'kWh'), (r'\bmwh\b|megawatt[ -]hours?', 'MWh'),
                (r'\bml\b|megalit(?:er|re)s?', 'ML'),
                (r'mtco2e|co2 equivalent', 'mtCO2e'), (r'metric tons?|metrik ton', 'mt'),
                (r'percentage|yuzde|\bpercent\b', '%')]
    return next((unit for pattern, unit in patterns if re.search(pattern, q)), None)


def requested_operation(query):
    q = ''.join(c for c in unicodedata.normalize('NFD', query.lower().replace('ı', 'i'))
                if unicodedata.category(c) != 'Mn')
    patterns = [(r'percentage[ -]points?|yuzde puan', 'percentage_point_change'),
                (r'(?:percentage|percent|yuzde).*(?:growth|change|artis|degisim)|(?:growth|change|artis|degisim).*(?:percentage|percent|yuzde)', 'percent_change'),
                (r'as a percentage|percentage of|percent of|yuzde.*oran|oran.*yuzde', 'percent_of'),
                (r'\bratio\b|kac kat|kac kat', 'ratio'),
                (r'\bminus\b|\bsubtract\w*|\bdifference\b|\bfark\w*', 'difference'),
                (r'\bsum\b|\badd\b|toplamını hesapla|topla', 'sum')]
    return next((operation for pattern, operation in patterns if re.search(pattern, q)), None)


def unsupported_scope(query, metric):
    q, label = query.lower(), metric.lower()
    limited = ['datacenter', 'data center', 'veri merkezi', 'watershed', 'havza',
               'groundwater', 'surface water', 'third-party water', 'water stress']
    if 'packaging' in label:
        limited += ['secondary packaging', 'transport packaging', 'shipping packaging',
                    'ikincil ambalaj', 'nakliye ambalaj', 'all packaging', 'all product packaging']
    if 'contracted' in label:
        limited += ['direct air capture', 'dac', 'beccs', 'biochar', 'forest', 'nature-based']
    if any(scope in q and scope not in label for scope in limited):
        return True
    permitted = {'microsoft', 'fy', 'million', 'cubic', 'metric', 'm3', 'mwh', 'kwh', 'ml',
                 'percent', 'percentage', 'calendar', 'fiscal', 'report', 'year', 'comparison', 'relation'}
    regions = re.findall(r"\bin\s+(?:the\s+)?([a-z][\w'-]*)", q)
    regions += re.findall(r"([\w]+)'(?:de|da|te|ta)(?:ki)?\b", q)
    return any(region not in permitted and not re.fullmatch(r'fy\d+', region)
               and region not in label for region in regions)


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
        op = requested_operation(query) or plan['operation']
        if op not in OPERATIONS or not isinstance(plan['operands'], list):
            return reject('invalid_plan', 'Unsupported operation.')
        refs = plan['operands']
        if (not refs or (op == 'value' and len(refs) != 1)
                or (op not in {'sum', 'value'} and len(refs) != 2) or len(refs) > 20):
            return reject('invalid_plan', f'{op} requires ' + ('exactly ONE source reference.' if op == 'value' else 'at least one source reference.' if op == 'sum' else 'exactly TWO source references, one for each input.'))
        catalog, operands, seen = audited_catalog(chunks), [], set()
        required_periods = set(requested_fiscal_years(query) + requested_calendar_years(query))
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
            if unsupported_scope(query, source['metric']):
                return reject('unavailable', 'The requested geographic, organizational or technology scope is not audited in this row.')
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
                and (operands[0]['metric'] != operands[1]['metric'] or operands[0]['period'][:2] != operands[1]['period'][:2] or operands[0]['period'] >= operands[1]['period'])):
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


def metric_tokens(text):
    text = ''.join(c for c in unicodedata.normalize('NFD', text.lower().replace('ı', 'i'))
                   if unicodedata.category(c) != 'Mn')
    aliases = {'su': 'water', 'cekim': 'withdrawal', 'tuket': 'consumption',
               'withdraw': 'withdrawal', 'consum': 'consumption', 'contract': 'contracted', 'remov': 'removal',
               'sozles': 'contracted', 'giderim': 'removal', 'uzaklast': 'removal',
               'karbon': 'carbon', 'atik': 'waste', 'diver': 'diverted', 'yonlend': 'diverted',
               'generat': 'generated', 'uretil': 'generated', 'elektrik': 'electricity',
               'operasyon': 'operational', 'plastic': 'plastics', 'packag': 'packaging', 'watershed': 'watershed', 'replenish': 'replenishment', 'yenile': 'replenishment', 'havza': 'watershed',
               'yenilenebilir': 'renewable', 'enerji': 'energy', 'tedarik': 'procurement',
               'yonetim': 'stewardship', 'politik': 'policy', 'veriml': 'efficiency',
               'sulama': 'irrigation', 'topluluk': 'community', 'ortaklik': 'partnership', 'partner': 'partnership'}
    tokens = []
    for word in re.findall(r'\w+', text):
        mapped = next((target for stem, target in sorted(aliases.items(), key=lambda item: len(item[0]), reverse=True)
                       if (word == stem if stem == 'su' else word.startswith(stem))), word)
        tokens.append(mapped)
    return tokens


def bind_explicit_metrics(query, chunks):
    """Bind unambiguous audited metric names/synonyms without model selection.

    Covers arbitrary rows/values with explicitly requested fiscal periods.
    Unknown/ambiguous names return None for the bounded model selector.
    """
    periods = list(requested_fiscal_years(query) + requested_calendar_years(query))
    if not periods:
        return None
    qtokens = metric_tokens(query)
    groups = {}
    for row in audited_catalog(chunks).values():
        name = row['metric']
        for unit in UNITS:
            name = name.replace(f'({unit})', '')
        words = set(metric_tokens(name)) - {'total', 'the', 'and', 'of', 'to'}
        if len(words) < 2 or not words.issubset(qtokens):
            continue
        position = max(qtokens.index(word) for word in words)
        key = row['metric']
        groups.setdefault(key, {'position': position, 'rows': []})['rows'].append(row)
    operation = requested_operation(query)
    if not operation and len(groups) == 1 and len(periods) == 1 and requested_output_unit(query):
        operation = 'value'
    if not operation:
        return None
    ordered = sorted(groups.values(), key=lambda g: g['position'])
    if operation in {'percent_change', 'percentage_point_change'}:
        if len(ordered) != 1 or len(periods) != 2:
            return None
        pairs = [(ordered[0], year) for year in sorted(periods)]
    elif operation in {'difference', 'ratio', 'percent_of'}:
        if len(ordered) == 2 and len(periods) == 1:
            pairs = [(group, periods[0]) for group in ordered]
        elif len(ordered) == 1 and len(periods) == 2 and operation == 'difference':
            # Only an explicit minus expression defines chronological ordering.
            return None
        else:
            return None
    elif operation in {'sum', 'value'} and len(periods) == 1:
        if not ordered or (operation == 'value' and len(ordered) != 1):
            return None
        pairs = [(group, periods[0]) for group in ordered]
    else:
        return None
    refs = []
    for group, period in pairs:
        rows = [row for row in group['rows'] if period in row['periods']]
        if len(rows) != 1:
            return None
        refs.append({'evidence_id': rows[0]['evidence_id'], 'period': period})
    return {'available': True, 'operation': operation, 'operands': refs}


def calculate_with_model(query, chunks, model_call):
    """One bounded schema-repair attempt; unavailable evidence is never retried."""
    bound = bind_explicit_metrics(query, chunks)
    if bound is not None:
        result = execute_audited_plan(bound, chunks, query)
        return result, [{'raw_plan': json.dumps(bound), 'status': result['status'],
                         'reason': result.get('reason'), 'selection': 'explicit_audited_metric_binding'}]
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
