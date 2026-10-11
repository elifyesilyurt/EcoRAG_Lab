"""Exercise the real app math-response function with a stub model stream."""
import unittest

from dynamic_math_engine import DynamicMathExecutor, format_math_execution_result, math_execution_failure_message
from test_baseline_regressions import load_app_functions


class TestMathResponseIntegration(unittest.TestCase):
    def setUp(self):
        self.model_calls = []

        def model_stream(system, prompt):
            self.model_calls.append((system, prompt))
            return iter(['model answer'])

        self.app = load_app_functions({'build_math_answer_response'}, {
            'format_math_execution_result': format_math_execution_result,
            'math_execution_failure_message': math_execution_failure_message,
            'stream_static_text': lambda text: iter([text]),
            'query_foundry_stream': model_stream,
        })

    def test_arithmetic_failure_never_calls_model(self):
        for language in ('tr', 'en'):
            result = DynamicMathExecutor.execute_code_lines('a = 10\nresult = a / 0')
            details, stream = self.app['build_math_answer_response'](result, 'difference?', language, 'system')
            self.assertIsNone(details)
            self.assertEqual(''.join(stream), math_execution_failure_message(language))
            self.assertEqual(self.model_calls, [])

    def test_success_passes_final_expression_to_model(self):
        for language in ('tr', 'en'):
            result = DynamicMathExecutor.execute_code_lines('withdrawal = 13.266\nconsumption = 8.170\nwithdrawal - consumption')
            details, stream = self.app['build_math_answer_response'](result, 'difference?', language, 'system')
            self.assertIn('Final result (_result)', details)
            self.assertIn(repr(result['result']), self.model_calls[-1][1])
            self.assertEqual(''.join(stream), 'model answer')
        self.assertEqual(len(self.model_calls), 2)
