import unittest
from unittest.mock import Mock

from grounded_narrative import generate_grounded_narrative, has_numeric_claim, source_narrative
from test_audited_math import evidence


class TestGroundedNarrative(unittest.TestCase):
    def setUp(self):
        self.rows = [evidence(71, 'Water Withdrawal', 'million m3', {'FY24': '11.59', 'FY25': '13.266'}),
                     evidence(89, 'Single-use plastics in primary product packaging', '%', {'FY25': '4.2'}),
                     evidence(97, 'Single-use plastics in primary product packaging', '%', {'CY2025': '0.07'}),
                     evidence(103, 'Total Contracted Carbon Removal', 'mt', {'FY25': 'More than 45 million metric tons'})]

    def test_explicit_source_values_bypass_model_and_preserve_period(self):
        model = Mock(side_effect=AssertionError('Must not generate source numbers'))
        result = generate_grounded_narrative('What is FY24 water withdrawal?', self.rows, 'en', model)
        self.assertIn('11.59', result['answer'])
        self.assertNotIn('13.266', result['answer'])
        self.assertEqual(result['references'], [{'evidence_id': 71, 'period': 'FY24'}])
        model.assert_not_called()

    def test_arbitrary_source_value_and_id_are_not_fixture_answers(self):
        rows = [evidence(456, 'Water Withdrawal', 'million m3', {'FY24': '99.123'})]
        result = source_narrative('FY24 water withdrawal?', rows, 'en')
        self.assertIn('99.123', result['answer'])
        self.assertEqual(result['references'][0]['evidence_id'], 456)

    def test_fiscal_and_calendar_values_remain_separate(self):
        for period, expected, forbidden in [('FY25', '4.2', '0.07'), ('CY2025', '0.07', '4.2')]:
            result = source_narrative(f'{period} single-use plastics in primary product packaging?', self.rows, 'en')
            self.assertIn(expected, result['answer'])
            self.assertNotIn(forbidden, result['answer'])

    def test_missing_year_never_substitutes_current_value(self):
        result = source_narrative('FY99 water withdrawal?', self.rows, 'en')
        self.assertEqual(result['status'], 'unavailable')
        self.assertNotIn('13.266', result['answer'])

    def test_qualified_source_is_literal_and_not_exact(self):
        result = source_narrative('What was FY25 total contracted carbon removal?', self.rows, 'en')
        self.assertIn('More than 45 million', result['answer'])
        exact = source_narrative('Exact FY25 total contracted carbon removal?', self.rows, 'en')
        self.assertEqual(exact['status'], 'unavailable')

    def test_scope_mismatch_is_rejected(self):
        result = source_narrative('FY25 water withdrawal in Madrid?', self.rows, 'en')
        self.assertEqual(result['status'], 'unavailable')

    def test_model_numeric_prose_is_not_published_even_if_number_occurs_elsewhere(self):
        for draft in ['FY25 water consumption was 13.266.', 'The answer is forty five million.', 'Oran yüzde dört.', 'See page 7.']:
            result = generate_grounded_narrative('Explain the water strategy', self.rows, 'en', Mock(return_value=draft))
            self.assertEqual(result['status'], 'numeric_claim_rejected')
            self.assertNotEqual(result['answer'], draft)

    def test_qualitative_output_is_explicitly_not_certified(self):
        result = generate_grounded_narrative('Explain the water strategy', self.rows, 'en', Mock(return_value='The strategy discusses water stewardship.'))
        self.assertEqual(result['status'], 'qualitative_unverified')

    def test_duplicate_source_metric_period_is_ambiguous(self):
        rows = self.rows + [evidence(555, 'Water Withdrawal', 'million m3', {'FY24': '12.0'})]
        self.assertEqual(source_narrative('FY24 water withdrawal?', rows, 'en')['status'], 'unavailable')

    def test_numbers_units_and_spelled_values_are_detected(self):
        for value in ['0.07%', 'FY25', 'ninety percent', 'beş milyon', '123', 'zero removals', 'sıfır atık', 'half the total']:
            self.assertTrue(has_numeric_claim(value))
        self.assertFalse(has_numeric_claim('Water stewardship is discussed.'))
    def test_conversion_is_not_silently_ignored_in_narrative(self):
        result = source_narrative('FY25 water withdrawal in cubic meters?', self.rows, 'en')
        self.assertEqual(result['status'], 'unavailable')

    def test_production_buffers_then_validates_before_display(self):
        import ast
        from pathlib import Path
        tree = ast.parse(Path(__file__).with_name('app.py').read_text())
        calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Name) and node.func.id == 'generate_grounded_narrative']
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].args[0].id, 'query_to_run')
        self.assertEqual(calls[0].args[3].id, 'query_foundry')
        self.assertTrue(any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                            and n.func.id == 'stream_static_text' and n.args
                            and isinstance(n.args[0], ast.Subscript)
                            and isinstance(n.args[0].value, ast.Name) and n.args[0].value.id == 'narrative'
                            for n in ast.walk(tree)))

    def test_short_metric_name_and_explicit_calendar_end_date(self):
        result = source_narrative('Compare single-use plastic packaging percentages for FY25 and calendar year ended December 31, 2025.', self.rows, 'en')
        self.assertEqual(result['status'], 'source_bound')
        self.assertIn('FY25', result['answer'])
        self.assertIn('CY2025', result['answer'])
        self.assertIn('4.2', result['answer'])
        self.assertIn('0.07', result['answer'])
        self.assertIn('primary product packaging', result['answer'])
        result = source_narrative('FY25 single-use plastic secondary packaging percentage?', self.rows, 'en')
        self.assertEqual(result['status'], 'unavailable')



if __name__ == '__main__':
    unittest.main()
