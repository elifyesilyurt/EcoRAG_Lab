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
            self.assertEqual(result['status'], 'unavailable')
            self.assertNotEqual(result['answer'], draft)

    def test_qualitative_output_is_explicitly_not_certified(self):
        result = generate_grounded_narrative('Explain the water strategy', self.rows, 'en', Mock(return_value='The strategy discusses water stewardship.'))
        self.assertEqual(result['status'], 'unavailable')

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


class TestSourceExcerpts(unittest.TestCase):
    def setUp(self):
        self.quote = 'Water stewardship does not mean that all watersheds have achieved replenishment.'
        self.rows = [{'id': 909, 'title': 'Report.pdf (p.12)', 'content': self.quote, 'chunk_type': 'text'}]
        self.query = 'Explain water stewardship'

    def test_whole_source_sentence_preserves_negation_and_provenance(self):
        model = Mock(return_value='{"references":[{"evidence_id":909,"sentence_index":0}]}')
        result = generate_grounded_narrative(self.query, self.rows, 'en', model)
        self.assertEqual(result['status'], 'source_excerpt')
        self.assertIn(self.quote, result['answer'])
        self.assertIn('Report.pdf (p.12)', result['answer'])
        self.assertTrue(model.call_args.kwargs['preserve_format'])

    def test_model_cannot_rewrite_or_add_unquoted_claims(self):
        for raw in ['Water stewardship is complete.', '{"references":[],"answer":"all watersheds succeeded"}',
                    '{"references":[{"evidence_id":909,"sentence_index":0,"text":"success"}]}']:
            result = generate_grounded_narrative(self.query, self.rows, 'en', Mock(return_value=raw))
            self.assertEqual(result['status'], 'qualitative_claim_rejected')
            self.assertNotIn('success', result['answer'])

    def test_unknown_duplicate_and_boolean_references_fail_closed(self):
        from grounded_narrative import excerpt_catalog, validate_excerpt_selection
        catalog = excerpt_catalog(self.query, self.rows)
        for refs in [[{'evidence_id':910,'sentence_index':0}],
                     [{'evidence_id':True,'sentence_index':0}],
                     [{'evidence_id':909,'sentence_index':0}] * 2]:
            self.assertEqual(validate_excerpt_selection({'references':refs}, catalog, 'en')['status'], 'qualitative_claim_rejected')

    def test_unlabelled_prose_cannot_answer_fiscal_question(self):
        model = Mock(side_effect=AssertionError('Must not infer fiscal period'))
        result = generate_grounded_narrative('Explain FY25 water stewardship', self.rows, 'en', model)
        self.assertEqual(result['status'], 'unavailable')
        model.assert_not_called()

    def test_numeric_and_unrelated_sentences_are_not_candidates(self):
        from grounded_narrative import excerpt_catalog
        rows = [dict(self.rows[0], content='Water stewardship achieved 90 percent. Energy policy focuses on electricity.')]
        self.assertEqual(excerpt_catalog(self.query, rows), [])

    def test_empty_evidence_does_not_call_model(self):
        model = Mock(side_effect=AssertionError('No evidence'))
        self.assertEqual(generate_grounded_narrative(self.query, [], 'tr', model)['status'], 'unavailable')
        model.assert_not_called()

    def test_source_sentence_ids_and_text_are_not_fixed(self):
        quote = 'Water stewardship is coordinated through community partnerships and watershed assessment.'
        row = dict(self.rows[0], id=818, content=quote)
        result = generate_grounded_narrative(self.query, [row], 'en', Mock(return_value='{"references":[{"evidence_id":818,"sentence_index":0}]}'))
        self.assertIn(quote, result['answer'])
        self.assertEqual(result['references'][0]['evidence_id'], 818)

    def test_overlong_or_visual_fragments_are_not_publishable(self):
        from grounded_narrative import excerpt_catalog
        for content in ['Water stewardship ' * 100, '[VISUAL DATA FRAGMENT] Water stewardship is discussed in this graph.']:
            self.assertEqual(excerpt_catalog(self.query, [dict(self.rows[0], content=content)]), [])

    def test_invalid_selector_has_only_one_repair_and_no_unchecked_fallback(self):
        good = '{"references":[{"evidence_id":909,"sentence_index":0}]}'
        model = Mock(side_effect=['Unsupported free prose.', good])
        result = generate_grounded_narrative(self.query, self.rows, 'en', model)
        self.assertEqual(result['status'], 'source_excerpt')
        self.assertEqual(model.call_count, 2)
        bad = Mock(return_value='Invented explanation.')
        result = generate_grounded_narrative(self.query, self.rows, 'en', bad)
        self.assertEqual(bad.call_count, 2)
        self.assertEqual(result['status'], 'qualitative_claim_rejected')
        self.assertNotIn('Invented', result['answer'])



if __name__ == '__main__':
    unittest.main()
