"""
test_dynamic_math.py — Unit tests for DynamicMathExecutor & Program-of-Thoughts PAL
"""

import unittest
from dynamic_math_engine import (
    SafeMathEvaluator,
    DynamicMathExecutor,
    is_mathematical_query,
    format_math_execution_result,
    math_execution_failure_message,
)

class TestDynamicMathEngine(unittest.TestCase):

    def test_safe_math_evaluator_basic(self):
        """Temel aritmetik işlemlerin ALU doğruluğunu test eder."""
        self.assertEqual(SafeMathEvaluator.eval_expr("36.23 + 38.24"), 74.47)
        self.assertAlmostEqual(SafeMathEvaluator.eval_expr("74.47 - 22.04"), 52.43, places=2)
        self.assertEqual(SafeMathEvaluator.eval_expr("sum([1, 2, 3, 4])"), 10)
        self.assertAlmostEqual(
            SafeMathEvaluator.eval_expr("sum([3.39, 1.99, 0.05, 0.81, 1.22, 0.45, 14.05, 0.03, 0.05])"),
            22.04,
            places=2
        )

    def test_safe_math_evaluator_security(self):
        """Güvenli olmayan (os, sys, eval, open vb.) çağrıların engellendiğini doğrular."""
        with self.assertRaises(Exception):
            SafeMathEvaluator.eval_expr("__import__('os').system('ls')")
        with self.assertRaises(Exception):
            SafeMathEvaluator.eval_expr("open('rag_storage.db')")

    def test_dynamic_code_execution(self):
        """Çok adımlı PoT Python kod yürütümünü test eder."""
        code = """
        # Extracted metrics
        cat1 = 36.23
        cat2 = 38.24
        top2 = cat1 + cat2
        others = [3.39, 1.99, 0.05, 0.81, 1.22, 0.45, 14.05, 0.03, 0.05]
        top_others = sum(others)
        diff_points = top2 - top_others
        """
        res = DynamicMathExecutor.execute_code_lines(code)
        self.assertTrue(res["success"])
        env = res["environment"]
        self.assertEqual(env["top2"], 74.47)
        self.assertAlmostEqual(env["top_others"], 22.04, places=2)
        self.assertAlmostEqual(env["diff_points"], 52.43, places=2)

    def test_is_mathematical_query_signals(self):
        """Farklı matematiksel ve karşılaştırmalı sorgu sinyallerini test eder."""
        queries = [
            "toplam emisyon ne kadar arttı?",
            "Scope 1 ile Scope 2 arasındaki fark nedir?",
            "ilk iki upstream kategorinin yüzdesel oranları toplamı kaçtır?",
            "kaç yüzde puan daha fazladır?",
            "Calculate the percentage point difference between 2024 and 2025",
            "What is the ratio of water recycled?"
        ]
        for q in queries:
            self.assertTrue(is_mathematical_query(q), f"Sinyal yakalanamadı: {q}")

        # Matematiksel olmayan genel ESG soruları
        non_math = [
            "Microsoft'un yapay zeka ve sürdürülebilirlik vizyonu nedir?",
            "FIDO Tech akustik sensörleri nasıl çalışır?",
            "What is the company's carbon negative goal?"
        ]
        for q in non_math:
            self.assertFalse(is_mathematical_query(q), f"Yanlış matematik sinyali: {q}")


class TestMathExecutionReliability(unittest.TestCase):
    def test_error_stops_execution_and_discards_partial_values(self):
        programs = [
            ("a = 10\nresult = a / 0", 2),
            ("a = missing + 1\nresult = 12", 1),
            ("a = 10\nb = a / 0\nresult = 99", 2),
        ]
        for code, line in programs:
            with self.subTest(code=code):
                result = DynamicMathExecutor.execute_code_lines(code)
                self.assertFalse(result['success'])
                self.assertEqual(result['environment'], {})
                self.assertIsNone(result['result'])
                self.assertEqual(result['errors'][0]['line'], line)
                self.assertNotIn('result = 99', result['trace'])

    def test_unsupported_statements_are_not_silently_ignored(self):
        for statement in ['a[0] = 4', 'a = b = 4', 'import os', 'a += 1',
                          'a == 10', 'The final answer is 10', 'print(a)']:
            with self.subTest(statement=statement):
                result = DynamicMathExecutor.execute_code_lines('a = 10\n' + statement)
                self.assertFalse(result['success'])
                self.assertEqual(result['environment'], {})

    def test_final_result_must_be_finite_numeric_scalar(self):
        for expression in ["True", "'ten'", 'sum', '[1, 2]', '1e309', '(-1) ** 0.5']:
            with self.subTest(expression=expression):
                result = DynamicMathExecutor.execute_code_lines('a = 10\nresult = ' + expression)
                self.assertFalse(result['success'])
                self.assertEqual(result['environment'], {})

    def test_non_numeric_inputs_are_rejected(self):
        for code in ["a = True\nresult = a + 1", "a = '10'\nresult = int(a)",
                     "a = [1, True]\nresult = sum(a)", "a = 1e309\nresult = 10"]:
            with self.subTest(code=code):
                self.assertFalse(DynamicMathExecutor.execute_code_lines(code)['success'])

    def test_empty_or_comments_only_is_failure(self):
        for code in ['', '   ', '# no extracted numbers', '```python\n# none\n```']:
            with self.subTest(code=code):
                result = DynamicMathExecutor.execute_code_lines(code)
                self.assertFalse(result['success'])
                self.assertEqual(result['environment'], {})

    def test_final_expression_is_explicitly_available(self):
        result = DynamicMathExecutor.execute_code_lines('a = 10\nb = 4\na - b')
        self.assertTrue(result['success'])
        self.assertEqual(result['result'], 6)
        self.assertEqual(result['result_name'], '_result')
        self.assertEqual(result['environment']['_result'], 6)
        self.assertEqual(result['errors'], [])

    def test_fenced_multiline_list_and_inline_comments(self):
        code = '```python\nvalues = [\n    10,\n    4,\n]\nresult = sum(values)  # source inputs\n```'
        result = DynamicMathExecutor.execute_code_lines(code)
        self.assertTrue(result['success'])
        self.assertEqual(result['result'], 14)
        self.assertEqual(result['result_name'], 'result')

    def test_keyword_arguments_are_not_silently_dropped(self):
        # Previously round(1.234, ndigits=2) silently returned 1 instead of 1.23.
        result = DynamicMathExecutor.execute_code_lines('a = 10\nresult = round(1.234, ndigits=2)')
        self.assertFalse(result['success'])

    def test_zero_and_negative_results_are_successes(self):
        for expression, value in [('10 - 10', 0), ('4 - 10', -6), ('10 / 4', 2.5)]:
            with self.subTest(expression=expression):
                result = DynamicMathExecutor.execute_code_lines('result = ' + expression)
                self.assertTrue(result['success'])
                self.assertEqual(result['result'], value)


class TestMathResultPresentation(unittest.TestCase):
    def test_failed_runs_are_not_synthesis_input(self):
        result = DynamicMathExecutor.execute_code_lines('a = 10\nresult = a / 0')
        self.assertIsNone(format_math_execution_result(result))
        # Defense against a stale caller supplying an inconsistent result object.
        result.update(success=True, result=10, environment={'a': 10})
        self.assertIsNone(format_math_execution_result(result))

    def test_anonymous_and_precise_results_are_visible(self):
        for code in ('10 - 4', 'result = 1 / 8'):
            result = DynamicMathExecutor.execute_code_lines(code)
            details = format_math_execution_result(result)
            self.assertIn(repr(result['result']), details)
            self.assertIn('Final result', details)
        self.assertIn('0.125', format_math_execution_result(
            DynamicMathExecutor.execute_code_lines('result = 1 / 8')))

    def test_static_failure_messages_are_localized(self):
        self.assertIn('Hesaplama tamamlanamadı', math_execution_failure_message('tr'))
        self.assertIn('could not be completed', math_execution_failure_message('en'))


if __name__ == "__main__":
    unittest.main()
