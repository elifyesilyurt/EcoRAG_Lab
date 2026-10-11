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
        self.assertTrue(score_case(case, {'math': {'success': False, 'status': 'unavailable'}}))

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


class TestModelCodeFormatting(unittest.TestCase):
    def test_math_response_preserves_newlines_without_prose_trimming(self):
        import gc
        from types import SimpleNamespace
        from unittest.mock import Mock
        from test_baseline_regressions import load_app_functions
        code = '```python\na = 2 # source value in unit\nb = 3 # source value in unit\nresult = a + b\n```'
        response = SimpleNamespace(status_code=200, json=lambda: {'choices': [{'message': {'content': code}}]})
        session = Mock()
        session.__enter__ = Mock(return_value=session)
        session.__exit__ = Mock(return_value=False)
        session.post.return_value = response
        trim = Mock(side_effect=AssertionError('Code must not be prose-trimmed'))
        app = load_app_functions({'query_foundry'}, {'get_foundry_base_url': lambda: 'http://local',
                                 'MODEL_NAME': 'test', 'gc': gc, 'requests': SimpleNamespace(Session=lambda: session),
                                 'trim_repetition': trim})
        self.assertEqual(app['query_foundry']('system', 'question', preserve_format=True), code)
        trim.assert_not_called()


class TestRepetitionPerformance(unittest.TestCase):
    def test_nonoverlapping_repeat_and_punctuation(self):
        import re
        from test_baseline_regressions import load_app_functions
        trim = load_app_functions({'trim_repetition'}, {'re': re})['trim_repetition']
        self.assertEqual(trim('one two three four one two three four tail'), 'one two three four')
        self.assertEqual(trim('one two three four five'), 'one two three four five')
        text = ' '.join('token' + str(i) for i in range(2000))
        self.assertEqual(trim(text), text)


if __name__ == '__main__':
    unittest.main()
