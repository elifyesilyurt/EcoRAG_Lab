"""Offline checks of the real-model runner's scoring, not model accuracy."""
import json
from pathlib import Path
import unittest

from answer_evaluation import answer_numbers, score_case
from answer_prompts import build_rag_prompts


class TestAnswerEvaluation(unittest.TestCase):
    def test_numeric_grouping_and_decimal(self):
        self.assertEqual(answer_numbers('21,927,370 mt; 4.2%; 0.07%'), [21927370, 4.2, .07])

    def test_wrong_final_math_cannot_pass_with_correct_intermediate(self):
        case = {'mode': 'math', 'expected_result': 5096000}
        self.assertFalse(score_case(case, {'math': {'success': True, 'result': 13.266, 'environment': {'difference': 5096000}}}))
        self.assertTrue(score_case(case, {'math': {'success': True, 'result': 5096000}}))

    def test_crash_is_not_abstention(self):
        case = {'mode': 'math_abstain'}
        self.assertFalse(score_case(case, {'error': 'Timeout', 'raw_code': 'cannot calculate'}))
        self.assertFalse(score_case(case, {'math': {'success': False}, 'raw_code': 'result = broken()'}))
        self.assertTrue(score_case(case, {'math': {'success': False}, 'raw_code': 'Cannot calculate: exact data unavailable.'}))

    def test_correct_number_alone_does_not_prove_qualified_answer(self):
        case = {'mode': 'narrative', 'required_numbers': [45], 'required_groups': [['more than'], ['contracted']]}
        self.assertFalse(score_case(case, {'answer': '45 million was actually removed.'}))
        self.assertTrue(score_case(case, {'answer': 'More than 45 million metric tons contracted.'}))

    def test_both_languages_use_scope_and_qualification_rules(self):
        for lang in ['tr', 'en']:
            system, prompt = build_rag_prompts('FY24: 5.4', 'FY24 packaging percentage?', lang)
            self.assertIn('not exact scalars', system)
            self.assertIn('not realized annual removals', system)
            self.assertIn('FY24', system)
            self.assertIn('FY24: 5.4', prompt)

    def test_fixture_coverage_and_independent_arithmetic(self):
        cases = json.loads(Path(__file__).with_name('tests').joinpath('fixtures/answer_evaluation.json').read_text())
        self.assertEqual(len({case['id'] for case in cases}), len(cases))
        self.assertEqual({case['lang'] for case in cases}, {'tr', 'en'})
        self.assertEqual({case['mode'] for case in cases}, {'math', 'math_abstain', 'narrative', 'no_evidence', 'out_of_domain'})
        expected = {case['id']: case.get('expected_result') for case in cases}
        self.assertEqual(expected['water-difference-en'], (13266 - 8170) * 1000)
        self.assertAlmostEqual(expected['waste-diversion-rate'], 36149 / 58868 * 100, places=2)


if __name__ == '__main__':
    unittest.main()
