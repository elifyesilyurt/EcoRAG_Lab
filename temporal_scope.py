"""Shared temporal constraints for answer routing and report retrieval.

Report publication year is not fiscal year. Fiscal data may be restated in
later publications, so an FY request must not be mapped to one report year.
"""
import re

REPORT_YEARS = ('2024', '2025', '2026')
STATIC_INTENTS = {
    'carbon_commitments', 'carbon_trend_scope', 'carbon_removal',
    'zero_waste_circularity', 'packaging_plastic', 'water_stewardship',
}


def requested_fiscal_years(query):
    """Accept FY24, FY 24, FY2024 and fiscal ranges without counting targets."""
    q = (query or '').lower()
    years = {int(match) % 100 for match in re.findall(r'\bfy\s*(20\d{2}|\d{2})\b', q)}
    for start, end in re.findall(r'\bfy\s*(20\d{2}|\d{2})\s*[-–—]\s*(?:fy\s*)?(20\d{2}|\d{2})\b', q):
        lo, hi = sorted((int(start) % 100, int(end) % 100))
        years.update(range(lo, hi + 1))
    return tuple(f'FY{year:02d}' for year in sorted(years))


def requested_report_years(query):
    """Only publication wording establishes a report-year constraint.

    Bare calendar years remain ambiguous; 2030/2050 targets do not select a
    publication. Do not reinterpret FY2024 as publication year 2024.
    """
    q = re.sub(r'\bfy\s*(?:20\d{2}|\d{2})\b', '', (query or '').lower())
    if not re.search(r'\b(?:reports?|rapor\w*|factsheet|fact sheet|publication|yayın\w*)\b', q):
        return ()
    years = set(re.findall(r'\b20\d{2}\b', q))
    for start, end in re.findall(r'\b(20\d{2})\s*[-–—]\s*(20\d{2})\b', q):
        years.update(str(year) for year in range(min(int(start), int(end)), max(int(start), int(end)) + 1))
    # Goal years in a report question are targets unless explicitly attached
    # to publication wording (e.g. "2030 report").
    for target in ('2030', '2050'):
        if not re.search(rf'{target}\s+(?:reports?|rapor\w*)|(?:reports?|rapor\w*)\s+{target}', q):
            years.discard(target)
    return tuple(sorted(years))


def has_temporal_request(query):
    return bool(re.search(r'\bfy\s*(?:20\d{2}|\d{2})\b|\b20\d{2}\b', (query or '').lower()))


def temporal_clarification(query, lang='tr'):
    q = re.sub(r'\bfy\s*(?:20\d{2}|\d{2})\b', '', (query or '').lower())
    calendar = set(re.findall(r'\b20\d{2}\b', q)) - {'2030', '2050'}
    if calendar and not requested_report_years(query):
        if lang == 'tr':
            return ('Belirttiğiniz yıl mali yıl mı (ör. FY24), yoksa raporun yayın yılı mı '
                    '(ör. 2024 raporu)? Bunlar farklı dönemlerdir; lütfen hangisini istediğinizi belirtin.')
        return ('Do you mean the fiscal year (e.g. FY24) or the report publication year '
                '(e.g. the 2024 report)? These are different periods; please specify which one.')
    return None


def temporal_intent(query, intent, year_filter=None):
    """All dated topic answers use question-specific evidence, not FY25 text."""
    if intent in STATIC_INTENTS and (has_temporal_request(query) or year_filter):
        return 'general_rag'
    return intent


def retrieval_report_years(query, year_filter=None):
    """None means unconstrained; () means unavailable/conflicting scope."""
    requested = requested_report_years(query)
    if any(year not in REPORT_YEARS for year in requested):
        return ()
    if year_filter:
        selected = str(year_filter).strip()
        if selected not in REPORT_YEARS or (requested and selected not in requested):
            return ()
        # A UI filter must not silently drop one side of a comparison.
        if requested and set(requested) != {selected}:
            return ()
        return (selected,)
    return requested or None


def select_temporal_chunks(scores, report_years, max_k, relative_drop, fiscal_years=(), minimum_score=0):
    """Require evidence for every explicitly requested publication.

    Thresholds are computed within each year, so a high score from a different
    year cannot suppress the requested year. No cross-year fallback is allowed.
    """
    if not scores or len(fiscal_years) > max_k:
        return []
    if fiscal_years:
        groups = []
        for fiscal in fiscal_years:
            number = fiscal[2:]
            pattern = rf'\bfy\s*(?:20)?{number}\b'
            group = [item for item in scores if re.search(pattern, item['content'], re.IGNORECASE)]
            if not group or group[0]['score'] < minimum_score:
                return []
            groups.append(group)
        per_period = max(1, max_k // len(fiscal_years))
        chosen = {}
        for group in groups:
            cutoff = group[0]['score'] * relative_drop
            for item in group[:per_period]:
                if item['score'] >= cutoff:
                    chosen[item['id']] = item
        scores = sorted(chosen.values(), key=lambda item: item['score'], reverse=True)
        # Never let final truncation remove the evidence for a requested FY.
        if not report_years:
            return scores
    if report_years:
        selected = []
        per_year = max(1, max_k // len(report_years))
        for year in report_years:
            group = [item for item in scores if str(item['year']) == year]
            if not group or group[0]['score'] < minimum_score:
                return []
            cutoff = group[0]['score'] * relative_drop
            selected.extend(item for item in group[:per_year] if item['score'] >= cutoff)
        for fiscal in fiscal_years:
            if not any(re.search(rf'\bfy\s*(?:20)?{fiscal[2:]}\b', item['content'], re.IGNORECASE)
                       for item in selected):
                return []
        return selected
    cutoff = scores[0]['score'] * relative_drop
    return [item for item in scores[:max_k] if item['score'] >= cutoff]


def temporal_evidence_instruction(query):
    fiscal = ', '.join(requested_fiscal_years(query)) or 'as requested in the question'
    return (
        f'Requested fiscal periods: {fiscal}. Report publication year is not fiscal year. '
        'Use only explicitly labelled fiscal periods and units in the evidence. '
        'Do not substitute a different year or treat a future target as a realized result. '
        'If any requested period or metric is missing or ambiguous, state that it cannot '
        'be verified; do not infer a value. For comparisons, verify both periods separately.'
    )
