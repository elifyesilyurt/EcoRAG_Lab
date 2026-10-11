"""Row evidence and rebuild safety across table shapes and failure points."""
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

import ingest_all_reports as ingestion
from ingestion_core import (
    INDEX_VERSION, build_evidence_context, numeric_evidence_allowed,
    replace_index, select_evidence_chunks, source_hash, table_row_evidence, prioritize_audited_evidence,
)

ROOT = Path(__file__).resolve().parent
FACT_SHEET = 'Microsoft_2026_Environmental_Data_Fact_Sheet.pdf'
REPORT = '2026-Microsoft-Environmental-Sustainability-Report-PDF.pdf'


class TestTableEvidence(unittest.TestCase):
    def test_zero_missing_and_units_are_distinct(self):
        chunks = table_row_evidence([
            ['Metric (ML)', 'FY24', 'FY25'], ['Withdrawals', 0, None], ['Consumption', 2, '–'],
        ])
        self.assertIn('Metric: Withdrawals', chunks[0])
        self.assertIn('FY24: 0', chunks[0])
        self.assertIn('FY25: [NOT REPORTED]', chunks[0])
        self.assertIn('FY25: –', chunks[1])
        # Unit lives in the first-column header and must survive conversion.
        self.assertIn('ML', chunks[0])

    def test_short_valid_tables_are_not_dropped(self):
        chunks = ingestion.table_to_structured_reprs([['m3', 'FY24'], ['Water', 5]], min_length=200)
        self.assertEqual(len(chunks), 1)
        self.assertIn('FY24: 5', chunks[0])

    def test_extra_cells_are_preserved_and_marked_ambiguous(self):
        chunks = table_row_evidence([['Metric', 'FY24'], ['Water', 5, 9]])
        self.assertIn('[UNRESOLVED COLUMN 3]: 9', chunks[0])
        self.assertFalse(numeric_evidence_allowed(chunks[0]))

    def test_short_rows_do_not_shift_columns_or_invent_values(self):
        chunks = table_row_evidence([['Metric', 'FY23', 'FY24', 'FY25'], ['Water', 4, 5]])
        self.assertIn('FY24: 5', chunks[0])
        self.assertIn('FY25: [NOT REPORTED]', chunks[0])
        self.assertFalse(numeric_evidence_allowed(chunks[0]))

    def test_numeric_first_row_is_not_interpreted_as_headers(self):
        chunks = table_row_evidence([['100', '200', '300'], ['150', '250', '350']])
        self.assertTrue(chunks)
        self.assertTrue(all(not numeric_evidence_allowed(chunk) for chunk in chunks))

    def test_merged_or_missing_headers_and_metrics_are_not_filled(self):
        for table in (
            [['Metric', 'FY24', None], ['Water', 1, 2]],
            [['Metric', 'FY24'], [None, 2]],
            [['Metric', 'FY24'], ['Water', 1], [None, 2]],
        ):
            chunks = table_row_evidence(table)
            self.assertFalse(numeric_evidence_allowed(chunks[-1]))
        self.assertEqual(table_row_evidence([]), [])
        self.assertEqual(table_row_evidence([['Metric']]), [])

    def test_split_rows_repeat_metric_and_keep_column_value_pairs(self):
        chunks = table_row_evidence([
            ['Metric', 'FY20 (MWh)', 'FY23 (MWh)', 'FY24 (MWh)', 'FY25 (MWh)'],
            ['Electricity', '11,000', '22,000', '33,000', '44,000'],
        ], chunk_size=120)
        self.assertGreater(len(chunks), 1)
        for chunk in chunks:
            self.assertIn('Metric: Electricity', chunk)
            self.assertLessEqual(len(chunk), 120)
        for period, value in (('FY20', '11,000'), ('FY23', '22,000'), ('FY24', '33,000'), ('FY25', '44,000')):
            self.assertTrue(any(f'{period} (MWh): {value}' in chunk for chunk in chunks))

    def test_oversized_cells_are_preserved_but_not_numeric_evidence(self):
        value = '9' * 1000
        chunks = table_row_evidence([['Metric', 'FY24'], ['Water', value]], chunk_size=80)
        self.assertIn(value, chunks[0])
        self.assertFalse(numeric_evidence_allowed(chunks[0]))


class TestContextEvidence(unittest.TestCase):
    def test_full_row_is_not_cut_at_500_characters(self):
        content = 'Source: p.7\n' + 'x' * 510 + '\nMetric: Water (ML)\nFY24: 11,590'
        self.assertEqual(build_evidence_context([{'content': content}]), content)

    def test_budget_omits_whole_chunks_and_keeps_provenance_in_sync(self):
        chunks = [{'id': 1, 'content': 'first'}, {'id': 2, 'content': 'second'}]
        selected = select_evidence_chunks(chunks, max_characters=6)
        self.assertEqual([chunk['id'] for chunk in selected], [1])
        self.assertEqual(build_evidence_context(chunks, max_characters=6), 'first')

    def test_budget_must_not_drop_one_side_of_fiscal_comparison(self):
        chunks = [{'year': '2025', 'content': 'FY24: 5'}, {'year': '2026', 'content': 'FY25: 6'}]
        self.assertEqual(select_evidence_chunks(chunks, max_characters=8, scope_query='FY24 and FY25'), [])
        self.assertEqual(len(select_evidence_chunks(chunks, scope_query='FY24 and FY25')), 2)

    def test_legacy_visual_and_ambiguous_rows_cannot_enter_model_context(self):
        for marker in ('[VERIFIED TABLE]', '[VISUAL REFERENCE]', '[VISUAL DATA FRAGMENT]',
                       '[UNRESOLVED TABLE STRUCTURE]', '[OVERSIZED TABLE CELL]'):
            self.assertEqual(build_evidence_context([{'content': marker + ' FY25: 100'}]), '')

    def test_relevant_audited_metrics_are_prioritized_across_languages(self):
        from temporal_scope import select_temporal_chunks
        rows = [
            {'id': 1, 'year': '2026', 'score': 10, 'content': 'FY24 FY25 water methodology', 'chunk_type': 'text'},
            {'id': 2, 'year': '2026', 'score': .3,
             'content': '[SOURCE AUDITED TABLE]\nMetric: Water Withdrawal (million m3)\nFY24: 11.59\nFY25: 13.266',
             'chunk_type': 'audited_table'},
            {'id': 3, 'year': '2026', 'score': .5,
             'content': '[SOURCE AUDITED TABLE]\nMetric: Electricity (MWh)\nFY24: 5\nFY25: 6',
             'chunk_type': 'audited_table'},
        ]
        for query in ('Compare FY24 and FY25 water withdrawal', 'FY24 FY25 su çekimini karşılaştır'):
            ranked = prioritize_audited_evidence(rows, query)
            self.assertEqual(ranked[0]['id'], 2)
            self.assertEqual(ranked[-1]['source_priority'], 0)
            selected = select_temporal_chunks(ranked, None, 6, .7, ('FY24', 'FY25'), .15)
            self.assertIn(2, [item['id'] for item in selected])
        # A marker in plain PDF text does not confer audited provenance.
        rows[1]['chunk_type'] = 'text'
        self.assertTrue(all(item['source_priority'] == 0 for item in prioritize_audited_evidence(rows, 'water withdrawal')))
        rows[1]['chunk_type'] = 'audited_table'
        rows[1]['score'] = .1
        self.assertTrue(all(item['source_priority'] == 0 for item in
                            prioritize_audited_evidence(rows, 'water withdrawal', minimum_score=.15)))
        self.assertTrue(all(item['source_priority'] == 0 for item in prioritize_audited_evidence(rows, 'water policy')))


class IndexFixture:
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'index.db'
        with sqlite3.connect(self.path) as conn:
            conn.execute('CREATE TABLE documents (id INTEGER PRIMARY KEY, year TEXT, title TEXT, content TEXT, embedding TEXT)')
            conn.execute("INSERT INTO documents VALUES (1, '2024', 'Old source', 'Old evidence', '[1, 0]')")
        self.digest = 'a' * 64
        self.manifest = [{'filename': '2026.pdf', 'sha256': self.digest}]
        self.chunks = [{'year': '2026', 'title': 'New source (p.3)', 'content': 'FY25: 7 MWh',
                        'type': 'table', 'page': 3, 'source_sha256': self.digest}]

    def tearDown(self):
        self.tmp.cleanup()

    def replace(self, chunks=None, vectors=None):
        return replace_index(self.path, self.chunks if chunks is None else chunks,
                             [[1, 0]] if vectors is None else vectors, 'test-model', self.manifest)

    def assert_old_index(self):
        with sqlite3.connect(self.path) as conn:
            self.assertEqual(conn.execute('SELECT content FROM documents').fetchall(), [('Old evidence',)])
            self.assertEqual(len(conn.execute('PRAGMA table_info(documents)').fetchall()), 5)

class TestAtomicIndex(IndexFixture, unittest.TestCase):
    def test_success_replaces_all_rows_and_records_manifest(self):
        self.assertEqual(self.replace(), 1)
        with sqlite3.connect(self.path) as conn:
            self.assertEqual(conn.execute('SELECT content, page, source_sha256 FROM documents').fetchone(),
                             ('FY25: 7 MWh', 3, self.digest))
            metadata = dict(conn.execute('SELECT key, value FROM index_metadata'))
            self.assertEqual(metadata['index_version'], INDEX_VERSION)
            self.assertEqual(metadata['embedding_dimension'], '2')
            self.assertEqual(json.loads(metadata['sources']), self.manifest)
            self.assertEqual(conn.execute('PRAGMA integrity_check').fetchone()[0], 'ok')

    def test_count_mismatch_and_empty_corpus_retain_old_index(self):
        for chunks, vectors in ((self.chunks, []), ([], []), (self.chunks * 2, [[1, 0]])):
            with self.assertRaises(ValueError):
                self.replace(chunks, vectors)
            self.assert_old_index()

    def test_invalid_embeddings_retain_old_index(self):
        for vector in ([float('nan'), 1], [float('inf'), 1], [], [0, 0], [True, 1], [[1], 2]):
            with self.subTest(vector=vector), self.assertRaises(ValueError):
                self.replace(vectors=[vector])
            self.assert_old_index()
        with self.assertRaises(ValueError):
            self.replace(self.chunks * 2, [[1, 0], [1, 0, 0]])
        self.assert_old_index()

    def test_missing_or_unknown_provenance_retains_old_index(self):
        for key in ('year', 'title', 'content', 'type', 'source_sha256', 'page'):
            chunk = dict(self.chunks[0]); del chunk[key]
            with self.assertRaises(ValueError):
                self.replace([chunk])
            self.assert_old_index()
        for change in ({'year': 'Unknown'}, {'page': 0}, {'source_sha256': 'b' * 64}):
            with self.assertRaises(ValueError):
                self.replace([{**self.chunks[0], **change}])
            self.assert_old_index()

    def test_database_failure_after_drop_and_insert_rolls_back_schema_and_data(self):
        conn = sqlite3.connect(self.path)
        conn.set_authorizer(lambda action, name, *_: sqlite3.SQLITE_DENY
                            if action == sqlite3.SQLITE_INSERT and name == 'index_metadata' else sqlite3.SQLITE_OK)
        with patch('ingestion_core.sqlite3.connect', return_value=conn), self.assertRaises(sqlite3.DatabaseError):
            self.replace()
        self.assert_old_index()

    def test_concurrent_reader_observes_old_index_until_publication(self):
        reader = sqlite3.connect(self.path)
        original_connect = sqlite3.connect
        conn = original_connect(self.path)
        observed = []
        def authorizer(action, name, *_):
            if action == sqlite3.SQLITE_INSERT and name == 'index_metadata':
                observed.append(reader.execute('SELECT content FROM documents').fetchone()[0])
            return sqlite3.SQLITE_OK
        conn.set_authorizer(authorizer)
        try:
            with patch('ingestion_core.sqlite3.connect', return_value=conn):
                self.replace()
            self.assertEqual(observed, ['Old evidence'])
            self.assertEqual(reader.execute('SELECT content FROM documents').fetchone()[0], 'FY25: 7 MWh')
        finally:
            reader.close()

    def test_repeat_rebuild_is_complete_and_does_not_duplicate(self):
        self.replace(); self.replace()
        with sqlite3.connect(self.path) as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM documents').fetchone()[0], 1)


class TestIngestionOrchestration(IndexFixture, unittest.TestCase):
    def test_source_or_embedding_failure_cannot_replace_existing_index(self):
        for failure_at in ('source', 'embedding'):
            with self.subTest(failure_at=failure_at):
                if failure_at == 'source':
                    with patch.object(ingestion, 'process_pdf', side_effect=RuntimeError('PDF failure')), \
                         self.assertRaises(RuntimeError):
                        ingestion.run_ingestion(['missing2026.pdf'], self.path)
                else:
                    embedder = unittest.mock.Mock()
                    embedder.encode.side_effect = RuntimeError('embedding failure')
                    with patch.object(ingestion, 'process_pdf', return_value=self.chunks), \
                         patch.object(ingestion, 'source_hash', return_value=self.digest), self.assertRaises(RuntimeError):
                        ingestion.run_ingestion(['2026.pdf'], self.path, embedder)
                self.assert_old_index()

    def test_no_sources_or_empty_source_cannot_publish_partial_corpus(self):
        with self.assertRaises(ValueError):
            ingestion.run_ingestion([], self.path)
        with patch.object(ingestion, 'process_pdf', side_effect=[self.chunks, []]), \
             patch.object(ingestion, 'source_hash', return_value=self.digest), self.assertRaises(ValueError):
            ingestion.run_ingestion(['2025.pdf', '2026.pdf'], self.path)
        self.assert_old_index()

    def test_full_pipeline_with_stub_embedder_publishes_index(self):
        embedder = unittest.mock.Mock()
        embedder.encode.return_value = np.array([[1.0, 0.0]])
        with patch.object(ingestion, 'process_pdf', return_value=self.chunks), \
             patch.object(ingestion, 'source_hash', return_value=self.digest):
            self.assertEqual(ingestion.run_ingestion(['2026.pdf'], self.path, embedder), 1)
        self.assertTrue(embedder.encode.call_args.kwargs['normalize_embeddings'])
        self.assertIn('search_document:', embedder.encode.call_args.args[0][0])


class TestPdfProcessing(unittest.TestCase):
    def fake_pdf(self, text='', tables=None):
        page = unittest.mock.Mock()
        page.extract_text.return_value = text
        page.extract_tables.return_value = tables or []
        pdf = unittest.mock.MagicMock()
        pdf.__enter__.return_value.pages = [page]
        return pdf

    def test_real_process_function_keeps_short_zero_row_and_source_metadata(self):
        pdf = self.fake_pdf(tables=[[['Metric (ML)', 'FY24'], ['Water', 0]]])
        with patch.object(ingestion.pdfplumber, 'open', return_value=pdf), \
             patch.object(ingestion, 'source_hash', return_value='a' * 64):
            chunks = ingestion.process_pdf('sample2026.pdf')
        self.assertEqual(len(chunks), 1)
        self.assertIn('FY24: 0', chunks[0]['content'])
        self.assertIn('ML', chunks[0]['content'])
        self.assertEqual(chunks[0]['page'], 1)
        self.assertEqual(chunks[0]['source_sha256'], 'a' * 64)

    def test_graph_text_is_marked_and_excluded_from_numeric_evidence(self):
        pdf = self.fake_pdf(text='Figure: water replenishment chart. ' * 10)
        with patch.object(ingestion.pdfplumber, 'open', return_value=pdf), \
             patch.object(ingestion, 'source_hash', return_value='a' * 64):
            chunks = ingestion.process_pdf('sample2026.pdf')
        self.assertTrue(chunks)
        self.assertTrue(all(not numeric_evidence_allowed(chunk['content']) for chunk in chunks))

    def test_axis_labels_mark_all_narrative_fragments_of_a_chart_page(self):
        text = '14M\n12M\n' + 'FY24 water withdrawal and consumption. ' * 60
        pdf = self.fake_pdf(text=text)
        with patch.object(ingestion.pdfplumber, 'open', return_value=pdf), \
             patch.object(ingestion, 'source_hash', return_value='a' * 64):
            chunks = ingestion.process_pdf('sample2026.pdf')
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all('[VISUAL DATA FRAGMENT]' in chunk['content'] for chunk in chunks))
        self.assertTrue(all(not numeric_evidence_allowed(chunk['content']) for chunk in chunks))


class TestAuditedSources(unittest.TestCase):
    def test_audited_fact_sheet_and_annual_water_keep_distinct_source_pages(self):
        fixture = json.loads((ROOT / 'tests/fixtures/resource_metrics_2026.json').read_text())
        self.assertEqual(source_hash(ROOT / 'docs' / FACT_SHEET), fixture['source_pdf_sha256'])
        self.assertEqual(source_hash(ROOT / 'docs' / REPORT), fixture['annual_replenishment_source']['sha256'])
        fact_chunks = ingestion.audited_source_chunks(FACT_SHEET, fixture['source_pdf_sha256'])
        annual_chunks = ingestion.audited_source_chunks(REPORT, fixture['annual_replenishment_source']['sha256'])
        self.assertEqual({chunk['page'] for chunk in fact_chunks}, {3, 6, 7, 8})
        self.assertEqual({chunk['page'] for chunk in annual_chunks}, {25, 32})
        self.assertTrue(all('Water Replenishment' not in chunk['content'] for chunk in fact_chunks))
        self.assertTrue(all('Water Replenishment' in chunk['content'] for chunk in annual_chunks if chunk['page'] == 25))
        self.assertTrue(all(numeric_evidence_allowed(chunk['content']) for chunk in fact_chunks + annual_chunks))

    def test_committed_index_matches_current_audited_rows_and_source_manifest(self):
        with sqlite3.connect(ROOT / 'rag_storage.db') as conn:
            metadata = dict(conn.execute('SELECT key,value FROM index_metadata'))
            self.assertEqual(metadata['index_version'], INDEX_VERSION)
            manifest = json.loads(metadata['sources'])
            self.assertEqual({source['filename'] for source in manifest},
                             {path.name for path in (ROOT / 'docs').glob('*.pdf')})
            expected = []
            for source in manifest:
                self.assertEqual(source_hash(ROOT / 'docs' / source['filename']), source['sha256'])
                expected.extend(ingestion.audited_source_chunks(source['filename'], source['sha256']))
            stored = conn.execute(
                "SELECT year,title,content,page,source_sha256 FROM documents WHERE chunk_type = 'audited_table'"
            ).fetchall()
            self.assertEqual(len(stored), len(expected))
            self.assertEqual(set(stored), {(chunk['year'],chunk['title'],chunk['content'],chunk['page'],
                                            chunk['source_sha256']) for chunk in expected})
            self.assertEqual(int(metadata['document_count']), conn.execute('SELECT COUNT(*) FROM documents').fetchone()[0])

    def test_modified_source_cannot_reuse_audited_values(self):
        for title in (FACT_SHEET, REPORT):
            with self.assertRaises(ValueError):
                ingestion.audited_source_chunks(title, 'f' * 64)


if __name__ == '__main__':
    unittest.main()
