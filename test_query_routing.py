"""Route numerical operations before broad topic summaries, preserve narratives."""
import ast
import json
from pathlib import Path
import unittest

from dynamic_math_engine import is_mathematical_query
from query_routing import classify_esg_intent, is_esg_query

QUERIES = json.loads(Path(__file__).with_name('tests').joinpath('fixtures/routing_queries.json').read_text())


class TestQueryRouting(unittest.TestCase):
    def check_queries(self, intents):
        for item in QUERIES:
            if item['intent'] in intents:
                with self.subTest(query=item['id']):
                    self.assertEqual(classify_esg_intent(item['question']), item['intent'])

    def test_calculations_take_precedence_over_topics(self):
        self.check_queries({'mathematical_query'})

    def test_topic_narratives_preserve_their_routes(self):
        self.check_queries({'water_stewardship', 'carbon_commitments', 'carbon_removal',
                            'carbon_trend_scope', 'packaging_plastic', 'zero_waste_circularity', 'general_rag'})

    def test_domain_rejection_still_precedes_math(self):
        self.check_queries({'out_of_domain'})

    def test_narrative_words_do_not_force_math(self):
        for query in ['Compare water stewardship policies', 'Explain the difference between water withdrawal and consumption',
                      'Karbon negatif olma stratejilerini karşılaştır ve açıkla', 'Explain why emissions increased',
                      'What does renewable energy share mean?', 'What is the carbon negative goal?']:
            with self.subTest(query=query):
                self.assertFalse(is_mathematical_query(query))

    def test_math_detection_handles_empty_input(self):
        self.assertFalse(is_mathematical_query(''))
        self.assertFalse(is_mathematical_query(None))


class TestShortDomainSignals(unittest.TestCase):
    def test_substrings_are_not_domain_evidence(self):
        for query in ('Calculate 10 minus 4', 'Sum 10 and 4', 'Tell me about supercomputers'):
            with self.subTest(query=query):
                self.assertFalse(is_esg_query(query))

    def test_actual_short_domain_words_are_preserved(self):
        for query in ('Su çekimi nedir?', 'Explain UL certification', 'Explain REC procurement'):
            with self.subTest(query=query):
                self.assertTrue(is_esg_query(query))


class TestAppRouterWiring(unittest.TestCase):
    def test_app_uses_shared_classifier(self):
        tree = ast.parse(Path(__file__).with_name('app.py').read_text())
        imports = [node for node in tree.body if isinstance(node, ast.ImportFrom)
                   and node.module == 'query_routing']
        self.assertEqual(len(imports), 1)
        self.assertIn('classify_esg_intent', {alias.name for alias in imports[0].names})
        self.assertFalse(any(isinstance(node, ast.FunctionDef) and node.name == 'classify_esg_intent'
                             for node in tree.body))
        self.assertTrue(any(isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                            and node.func.id == 'classify_esg_intent' for node in ast.walk(tree)))
