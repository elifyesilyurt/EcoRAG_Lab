"""Model-independent table evidence and transactional index replacement."""
import hashlib
import json
import math
import numbers
from pathlib import Path
import re
import sqlite3
import unicodedata

from temporal_scope import requested_calendar_years, requested_fiscal_years, retrieval_report_years

INDEX_VERSION = 'column-row-evidence-v3'


def cell_text(value):
    # Zero is a reported value; only None represents an absent cell.
    if value is None:
        return ''
    return re.sub(r'\s+', ' ', str(value)).replace('|', r'\|').strip()


def table_row_evidence(table, chunk_size=900):
    """Keep every value attached to its metric and original column header.

    No implicit header/metric filling, numeric conversion or unit inference.
    Unresolved structure is retained for review, not claimed to be verified.
    Short real rows are evidence; narrative length thresholds do not apply.
    """
    if not table or len(table) < 2:
        return []
    rows = [[cell_text(cell) for cell in row] for row in table if row is not None]
    if len(rows) < 2:
        return []
    headers = rows[0]
    output = []
    for row in rows[1:]:
        if not any(row):
            continue
        width = max(len(headers), len(row))
        if width < 2:
            continue
        metric = row[0] if row else ''
        pairs = []
        # Numeric-only first rows are data fragments, not column headers.
        ambiguous = not metric or len(row) != len(headers) or any(
            header and re.fullmatch(r'[\d\s,.%+−–\-()]+', header) for header in headers
        )
        for index in range(1, width):
            header = headers[index] if index < len(headers) else ''
            value = row[index] if index < len(row) else ''
            ambiguous = ambiguous or not header
            label = header or f'[UNRESOLVED COLUMN {index + 1}]'
            pairs.append(f'{label}: {value or "[NOT REPORTED]"}')
        tag = '[UNRESOLVED TABLE STRUCTURE]' if ambiguous else '[PARSED TABLE ROW]'
        row_header = headers[0] if headers else '[UNRESOLVED ROW HEADER]'
        prefix = f'{tag}\nHeader: {row_header}\nMetric: {metric or "[UNRESOLVED METRIC]"}\n'
        # Repeat the metric and a full column/value pair in every split.
        batch = []
        for pair in pairs:
            if batch and len(prefix) + len('\n'.join(batch + [pair])) > chunk_size:
                output.append(prefix + '\n'.join(batch))
                batch = []
            if len(prefix) + len(pair) > chunk_size:
                # A giant cell cannot be safely split into independent numbers.
                output.append('[OVERSIZED TABLE CELL]\n' + prefix + pair)
            else:
                batch.append(pair)
        if batch:
            output.append(prefix + '\n'.join(batch))
    return output


def source_hash(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def replace_index(db_path, chunks, embeddings, embedding_model, source_manifest):
    """Validate before opening the DB; replace documents in one transaction.

    An embedding, insert, validation or commit failure retains the prior index.
    Readers observe the old committed corpus or the complete new corpus.
    """
    if not chunks or len(chunks) != len(embeddings):
        raise ValueError('Chunk/embedding count mismatch or empty corpus')
    if not embedding_model or not source_manifest:
        raise ValueError('Embedding model and source manifest are required')
    records = []
    dimension = None
    for chunk, embedding in zip(chunks, embeddings):
        values = embedding.tolist() if hasattr(embedding, 'tolist') else list(embedding)
        if not values or any(isinstance(value, bool) or not isinstance(value, numbers.Real)
                             or not math.isfinite(value) for value in values):
            raise ValueError('Embeddings must be finite, nonempty numeric vectors')
        if dimension is None:
            dimension = len(values)
        if len(values) != dimension or not any(value != 0 for value in values):
            raise ValueError('Embedding dimensions differ or vector is zero')
        for key in ('year', 'title', 'content', 'type', 'source_sha256', 'page'):
            if key not in chunk or chunk[key] is None or chunk[key] == '':
                raise ValueError(f'Missing chunk provenance: {key}')
        if str(chunk['year']) not in ('2024', '2025', '2026'):
            raise ValueError('Unknown or unsupported report publication year')
        if not isinstance(chunk['page'], int) or chunk['page'] < 1:
            raise ValueError('Invalid PDF page')
        if chunk['source_sha256'] not in {source['sha256'] for source in source_manifest}:
            raise ValueError('Chunk source is absent from manifest')
        records.append((str(chunk['year']), chunk['title'], chunk['content'], json.dumps(values),
                        chunk['type'], chunk['page'], chunk['source_sha256']))

    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute('BEGIN IMMEDIATE')
        # SQLite DDL is transactional when BEGIN is explicit; no early commit.
        conn.execute('DROP TABLE IF EXISTS documents')
        conn.execute('''CREATE TABLE documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            year TEXT NOT NULL, title TEXT NOT NULL, content TEXT NOT NULL,
            embedding TEXT NOT NULL, chunk_type TEXT NOT NULL,
            page INTEGER NOT NULL, source_sha256 TEXT NOT NULL
        )''')
        conn.executemany('''INSERT INTO documents
            (year, title, content, embedding, chunk_type, page, source_sha256)
            VALUES (?, ?, ?, ?, ?, ?, ?)''', records)
        conn.execute('CREATE INDEX idx_documents_year ON documents(year)')
        conn.execute('CREATE TABLE IF NOT EXISTS index_metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
        metadata = {
            'index_version': INDEX_VERSION, 'embedding_model': embedding_model,
            'embedding_dimension': str(dimension), 'document_count': str(len(records)),
            'sources': json.dumps(source_manifest, ensure_ascii=False),
        }
        conn.execute('DELETE FROM index_metadata')
        conn.executemany('INSERT INTO index_metadata (key, value) VALUES (?, ?)', metadata.items())
        if conn.execute('SELECT COUNT(*) FROM documents').fetchone()[0] != len(chunks):
            raise ValueError('Stored corpus size mismatch')
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()
    return len(records)


def numeric_evidence_allowed(content):
    """Reject unsafe legacy injections and ambiguous/visual numeric fragments."""
    return not any(marker in content for marker in (
        '[VERIFIED TABLE]', '[UNRESOLVED TABLE STRUCTURE]', '[OVERSIZED TABLE CELL]',
        '[VISUAL REFERENCE]', '[VISUAL DATA FRAGMENT]',
    ))


def prioritize_audited_evidence(scores, query, minimum_score=0):
    """Prefer relevant audited metric rows over explanatory references.

    Require at least two matching metric/unit tokens; generic topic mentions do
    not promote unrelated audited rows. A trusted stored type is required.
    """
    aliases = {'su': 'water', 'cekim': 'withdrawal', 'withdrawal': 'withdrawal',
               'tuketim': 'consumption', 'yenileme': 'replenishment',
               'enerji': 'energy', 'elektrik': 'electricity', 'emisyon': 'emissions',
               'emission': 'emissions', 'kategori': 'cat', 'category': 'cat',
               'atik': 'waste', 'atık': 'waste', 'karbon': 'carbon', 'giderim': 'removal', 'uzaklast': 'removal', 'sozlesme': 'contracted', 'yonlendir': 'diverted', 'bertaraf': 'disposal',
               'uretil': 'generated', 'onlen': 'prevented', 'operasyonel': 'operational'}
    def tokens(text):
        normalized = ''.join(char for char in unicodedata.normalize('NFD', text.lower())
                             if unicodedata.category(char) != 'Mn')
        normalized = re.sub(r'\b(scope|cat)(?=\d)', r'\1 ', normalized)
        result = set()
        for token in re.findall(r'\b\w+\b', normalized):
            mapped = next((value for stem, value in aliases.items() if token.startswith(stem)), token)
            result.add(mapped)
        return result - {'metric', 'unit', 'the', 'and', 'in', 'of', 'for', 'to'}
    query_tokens = tokens(query)
    ranked = []
    for item in scores:
        priority = 0
        if item.get('chunk_type') == 'audited_table' and item['score'] >= minimum_score:
            match = re.search(r'^Metric: (.+)$', item['content'], re.MULTILINE)
            if match:
                metric_tokens = tokens(match.group(1))
                overlap = metric_tokens & query_tokens
                if len(overlap) >= 2:
                    priority = len(overlap) / len(metric_tokens)
        ranked.append({**item, 'source_priority': priority})
    return sorted(ranked, key=lambda item: (item['source_priority'] > 0,
                                          item['source_priority'], item['score']), reverse=True)


def select_evidence_chunks(chunks, max_characters=12000, scope_query=None, year_filter=None):
    """Include complete chunks or omit them; never cut a metric/year/value row."""
    selected = []
    length = 0
    for chunk in chunks:
        content = chunk['content']
        if not numeric_evidence_allowed(content):
            continue
        extra = len(content) + (5 if selected else 0)
        if length + extra > max_characters:
            continue
        selected.append(chunk)
        length += extra
    if scope_query is not None:
        for fiscal in requested_fiscal_years(scope_query):
            if not any(re.search(rf'\bfy\s*(?:20)?{fiscal[2:]}\b', chunk['content'], re.IGNORECASE)
                       for chunk in selected):
                return []
        for calendar in requested_calendar_years(scope_query):
            if not any(re.search(rf"\b{calendar}\b", chunk["content"], re.IGNORECASE) for chunk in selected):
                return []
        reports = retrieval_report_years(scope_query, year_filter)
        if reports == () or (reports and not set(reports).issubset({str(chunk['year']) for chunk in selected})):
            return []
    return selected


def build_evidence_context(chunks, max_characters=12000):
    return '\n---\n'.join(chunk['content'] for chunk in select_evidence_chunks(chunks, max_characters))
