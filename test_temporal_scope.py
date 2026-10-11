"""Temporal contracts across question families and the actual SQLite search."""
import ast
import gc
import json
from pathlib import Path
import re
import sqlite3
import tempfile
import unittest
from typing import Optional

import numpy as np

from ingestion_core import numeric_evidence_allowed, prioritize_audited_evidence, INDEX_VERSION
from temporal_scope import (
    STATIC_INTENTS, requested_calendar_years, requested_fiscal_years, requested_report_years,
    retrieval_report_years, select_temporal_chunks, temporal_clarification,
    temporal_evidence_instruction, temporal_intent,
)
from test_baseline_regressions import load_app_functions


class TestTemporalContracts(unittest.TestCase):
    def test_explicit_calendar_period_is_not_ambiguous_or_fiscal(self):
        for query in ('CY2025 packaging', 'calendar year 2025 packaging', 'takvim yılı 2025 ambalaj', 'calendar year ended December 31, 2025 packaging'):
            self.assertEqual(requested_calendar_years(query), ('CY2025',))
            self.assertEqual(requested_fiscal_years(query), ())
            self.assertIsNone(temporal_clarification(query))
        self.assertEqual(requested_calendar_years('2025 packaging'), ())
        self.assertIsNotNone(temporal_clarification('2025 packaging'))

    def test_calendar_evidence_gate_rejects_fiscal_substitution(self):
        from ingestion_core import select_evidence_chunks
        fiscal = {'content': 'Metric: packaging (%)\nFY25: 4.2', 'year': '2026'}
        calendar = {'content': 'Metric: packaging (%)\nCY2025: 0.07', 'year': '2026'}
        self.assertEqual(select_evidence_chunks([fiscal], scope_query='CY2025 packaging'), [])
        self.assertEqual(select_evidence_chunks([calendar], scope_query='calendar year 2025 packaging'), [calendar])

    def test_calendar_dates_force_period_specific_topic_routing(self):
        for intent in STATIC_INTENTS:
            for query in ('CY2025 packaging', 'calendar year ended December 31, 2025 packaging'):
                self.assertEqual(temporal_intent(query, intent), 'general_rag')

    def test_fiscal_spellings_ranges_and_targets(self):
        for query in ('FY24', 'FY 24', 'fy2024', 'FY 2024'):
            self.assertEqual(requested_fiscal_years(query), ('FY24',))
        self.assertEqual(requested_fiscal_years('FY23–FY25'), ('FY23', 'FY24', 'FY25'))
        self.assertEqual(requested_fiscal_years('FY2023-2025'), ('FY23', 'FY24', 'FY25'))
        self.assertEqual(requested_fiscal_years('FY25 and the 2030 target'), ('FY25',))
        self.assertEqual(requested_fiscal_years(None), ())

    def test_publication_is_distinct_from_fiscal_and_goal_year(self):
        cases = (
            ('FY2024 water', ()), ('2024 raporundaki su', ('2024',)),
            ('2024–2026 reports', ('2024', '2025', '2026')),
            ('Compare the 2026 report and FY24', ('2026',)),
            ('2026 report: 2030 carbon negative target', ('2026',)),
            ('What is the 2030 water target?', ()), ('2030 report water', ('2030',)),
        )
        for query, expected in cases:
            with self.subTest(query=query):
                self.assertEqual(requested_report_years(query), expected)

    def test_every_static_topic_obeys_dates_and_ui_filter(self):
        for intent in STATIC_INTENTS:
            for question in ('FY20', 'FY 23', 'FY2024', 'FY25', 'FY26',
                             'FY23-FY25', '2024 raporu', '2026 report', '2030 target'):
                with self.subTest(intent=intent, question=question):
                    self.assertEqual(temporal_intent(question, intent), 'general_rag')
            self.assertEqual(temporal_intent('Describe the topic', intent, '2024'), 'general_rag')
            self.assertEqual(temporal_intent('Describe the topic', intent), intent)
        for intent in ('out_of_domain', 'mathematical_query', 'general_rag'):
            self.assertEqual(temporal_intent('FY24', intent, '2024'), intent)

    def test_ui_filter_cannot_silently_override_question(self):
        self.assertEqual(retrieval_report_years('2024 report', '2026'), ())
        self.assertEqual(retrieval_report_years('2024 and 2026 reports', '2026'), ())
        self.assertEqual(retrieval_report_years('2024 report', '2024'), ('2024',))
        self.assertEqual(retrieval_report_years('2030 report'), ())
        self.assertEqual(retrieval_report_years('FY24'), None)
        self.assertEqual(retrieval_report_years('FY24', '2026'), ('2026',))
        self.assertEqual(retrieval_report_years('water', 'invalid'), ())

    def test_ambiguous_calendar_year_requires_clarification_in_both_languages(self):
        for query in ('2024 water consumption', '2025 su çekimi', 'FY24 versus 2025 electricity'):
            for language in ('tr', 'en'):
                with self.subTest(query=query, language=language):
                    self.assertIn('FY24', temporal_clarification(query, language))
        for query in ('FY24 water consumption', '2024 report water', '2030 water target', 'FY2024 energy'):
            self.assertIsNone(temporal_clarification(query))

    def test_missing_fiscal_period_does_not_use_another_year(self):
        scores = [{'id': 1, 'year': '2026', 'score': 5, 'content': 'FY25 water 10 m3'}]
        self.assertEqual(select_temporal_chunks(scores, None, 6, .5, ('FY24',)), [])
        self.assertEqual(select_temporal_chunks(scores, None, 6, .5, ('FY24', 'FY25')), [])

    def test_fiscal_values_can_be_restated_in_later_publication(self):
        scores = [
            {'id': 1, 'year': '2026', 'score': 10, 'content': 'FY25 water 10'},
            {'id': 2, 'year': '2026', 'score': 1, 'content': 'FY2024 water 5'},
        ]
        selected = select_temporal_chunks(scores, ('2026',), 6, .5, ('FY24',), .5)
        self.assertEqual([item['id'] for item in selected], [2])
        self.assertEqual(select_temporal_chunks(scores, None, 6, .5, ('FY24',), 2), [])

    def test_comparison_preserves_both_fiscal_periods(self):
        scores = [
            {'id': 1, 'year': '2026', 'score': 10, 'content': 'FY25 water 10'},
            {'id': 2, 'year': '2025', 'score': 1, 'content': 'FY24 water 5'},
        ]
        selected = select_temporal_chunks(scores, None, 6, .5, ('FY24', 'FY25'))
        self.assertEqual({item['id'] for item in selected}, {1, 2})
        # A multi-column evidence chunk should not be duplicated.
        scores[0]['content'] = 'FY24: 5; FY25: 10'
        selected = select_temporal_chunks(scores[:1], None, 6, .5, ('FY24', 'FY25'))
        self.assertEqual(len(selected), 1)

    def test_instructions_distinguish_missing_periods_units_and_targets(self):
        text = temporal_evidence_instruction('FY24 and FY25 water')
        for term in ('FY24', 'FY25', 'not fiscal year', 'units', 'future target', 'cannot be verified'):
            self.assertIn(term, text)

    def test_shared_period_chunks_do_not_leave_unused_evidence_slots(self):
        scores = [{'id': index, 'year': '2026', 'score': 1 - index * .01,
                   'content': f'Metric {index}: FY24: 5; FY25: 6'} for index in range(8)]
        selected = select_temporal_chunks(scores, None, 6, .7, ('FY24', 'FY25'))
        self.assertEqual([item['id'] for item in selected], list(range(6)))


class FakeEmbedder:
    def encode(self, query):
        return np.array([1.0, 0.0])


class TestActualTemporalSearch(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.tmp.name) / 'documents.db')
        with sqlite3.connect(self.path) as conn:
            conn.execute('CREATE TABLE documents (id INTEGER, year TEXT, title TEXT, content TEXT, embedding TEXT)')
            conn.executemany('INSERT INTO documents VALUES (?, ?, ?, ?, ?)', [
                (1, '2024', '2024 Report', 'FY23 water withdrawal: 4', json.dumps([1, 0])),
                (2, '2025', '2025 Report', 'FY24 water withdrawal: 5', json.dumps([1, 0])),
                (3, '2026', '2026 Report', 'FY25 water withdrawal: 6', json.dumps([1, 0])),
                (4, '2026', '2026 restatement', 'FY24 energy: 7 MWh', json.dumps([1, 0])),
            ])
        self.app = load_app_functions({'search_context_hybrid'}, {
            'Optional': Optional, 'sqlite3': sqlite3, 'DB_PATH': self.path,
            'embedder': FakeEmbedder(), 'np': np, 'json': json, 're': re, 'gc': gc,
            'MIN_SCORE_FLOOR': .1, 'MAX_K': 6, 'RELATIVE_DROP_RATIO': .5,
            'retrieval_report_years': retrieval_report_years,
            'select_temporal_chunks': select_temporal_chunks,
            'requested_fiscal_years': requested_fiscal_years,
            'numeric_evidence_allowed': numeric_evidence_allowed, 'INDEX_VERSION': INDEX_VERSION,
            'prioritize_audited_evidence': prioritize_audited_evidence,
        })

    def tearDown(self):
        self.tmp.cleanup()

    def search(self, *args, **kwargs):
        return self.app['search_context_hybrid'](*args, **kwargs)[0]

    def test_one_matching_chunk_is_enough_without_other_year_fallback(self):
        chunks = self.search('2024 report water withdrawal')
        self.assertEqual([item['id'] for item in chunks], [1])

    def test_report_comparison_contains_all_and_only_requested_publications(self):
        chunks = self.search('Compare 2024 and 2026 reports water')
        self.assertEqual({item['year'] for item in chunks}, {'2024', '2026'})

    def test_missing_publication_causes_no_answer_evidence(self):
        with sqlite3.connect(self.path) as conn:
            conn.execute("DELETE FROM documents WHERE year = '2024'")
        self.assertEqual(self.search('2024 report water'), [])
        self.assertEqual(self.search('Compare 2024 and 2026 reports water'), [])

    def test_missing_fiscal_period_causes_no_answer_evidence(self):
        self.assertEqual(self.search('FY22 water withdrawal'), [])
        self.assertEqual(self.search('FY22 and FY25 water withdrawal'), [])

    def test_fiscal_and_publication_requests_are_separate_constraints(self):
        chunks = self.search('FY24 energy in 2026 report')
        self.assertEqual([item['id'] for item in chunks], [4])
        chunks = self.search('FY24 water withdrawal')
        self.assertTrue(chunks)
        self.assertTrue(all('FY24' in item['content'] for item in chunks))

    def test_translation_does_not_change_original_temporal_scope(self):
        chunks = self.search('2026 report water', scope_query='2024 raporundaki su')
        self.assertEqual([item['id'] for item in chunks], [1])

    def test_undated_narrative_comparisons_preserve_multi_report_coverage(self):
        for query in ('Compare water policies', 'Su politikalarını karşılaştır', 'Describe the water trend'):
            with self.subTest(query=query):
                chunks = self.search(query)
                self.assertEqual({item['year'] for item in chunks}, {'2024', '2025', '2026'})

    def test_comparison_scope_keeps_per_year_scores_independent(self):
        with sqlite3.connect(self.path) as conn:
            conn.execute("UPDATE documents SET content = ? WHERE id = 3",
                         ('water energy carbon emission target packaging climate',))
        chunks = self.search('2024 and 2026 reports water energy carbon emission target packaging climate')
        self.assertEqual({item['year'] for item in chunks}, {'2024', '2026'})

    def test_ui_filter_conflict_returns_no_evidence(self):
        self.assertEqual(self.search('2024 report water', year_filter='2026'), [])

    def test_legacy_injections_and_continuations_never_win_retrieval(self):
        with sqlite3.connect(self.path) as conn:
            rows = [(10 + page, '2026',
                     f'2026-Microsoft-Environmental-Sustainability-Report-PDF.pdf (p.{page})',
                     'FY25 water withdrawal 99999', json.dumps([1, 0])) for page in (6, 25, 54)]
            rows.append((99, '2026', 'Other legacy source', '[VERIFIED TABLE] FY25 water withdrawal 99999', json.dumps([1, 0])))
            conn.executemany('INSERT INTO documents VALUES (?, ?, ?, ?, ?)', rows)
        chunks = self.search('FY25 water withdrawal')
        self.assertEqual([chunk['id'] for chunk in chunks], [3])

    def test_app_wires_temporal_policy_and_original_query(self):
        tree = ast.parse(Path(__file__).with_name('app.py').read_text())
        calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
        for name in ('temporal_intent', 'temporal_clarification', 'generate_grounded_narrative'):
            self.assertTrue(any(isinstance(node.func, ast.Name) and node.func.id == name for node in calls))
        prompt_tree = ast.parse(Path(__file__).with_name('answer_prompts.py').read_text())
        self.assertTrue(any(isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                            and node.func.id == 'temporal_evidence_instruction'
                            and isinstance(node.args[0], ast.Name) and node.args[0].id == 'query'
                            for node in ast.walk(prompt_tree)))
        translated = [node for node in calls if isinstance(node.func, ast.Name)
                      and node.func.id == 'search_context_hybrid' and node.args
                      and isinstance(node.args[0], ast.Name) and node.args[0].id == 'search_query']
        self.assertTrue(translated)
        self.assertTrue(all(any(kw.arg == 'scope_query' and isinstance(kw.value, ast.Name)
                                and kw.value.id == 'query_to_run' for kw in node.keywords) for node in translated))


if __name__ == '__main__':
    unittest.main()
