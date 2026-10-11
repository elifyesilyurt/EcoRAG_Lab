"""Offline baseline checks against real app functions, without importing its UI.

Known defects are expected failures until their corresponding implementation fix.
ECORAG_STRICT_REGRESSIONS=1 disables that marking to reproduce all failures.
This is a temporary bridge until the query engine is separated from Streamlit.
"""

import ast
import json
import os
from pathlib import Path
import re
import unittest

from dynamic_math_engine import DynamicMathExecutor, is_mathematical_query
from esg_tables import get_carbon_emissions_df


ROOT = Path(__file__).resolve().parent


def load_app_functions(names, dependencies):
    """Compile the original function bodies; never execute app's top-level code."""
    source = ROOT.joinpath("app.py").read_text(encoding="utf-8")
    tree = ast.parse(source, filename="app.py")
    functions = [
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in names
    ]
    found = {node.name for node in functions}
    if found != set(names):
        raise RuntimeError(f"App function coverage changed: missing {set(names) - found}")
    if any(node.decorator_list for node in functions):
        raise RuntimeError("Extracted functions must not execute decorators")
    namespace = dict(dependencies)
    exec(compile(ast.Module(body=functions, type_ignores=[]), "app.py", "exec"), namespace)
    return namespace


# Resolve this outside expected-failure tests so loader/import errors fail the suite.
APP = load_app_functions(
    {"detect_query_language", "is_esg_query", "classify_esg_intent",
     "compute_carbon_trend_summary"},
    {"re": re, "is_mathematical_query": is_mathematical_query,
     "get_carbon_emissions_df": get_carbon_emissions_df},
)
QUERIES = json.loads(ROOT.joinpath("tests/fixtures/baseline_queries.json").read_text())


def known_defect(test):
    """Unexpected success fails CI, requiring removal of the obsolete marker."""
    if os.environ.get("ECORAG_STRICT_REGRESSIONS") == "1":
        return test
    return unittest.expectedFailure(test)


class TestWorkingBaseline(unittest.TestCase):
    def test_fixture_language_detection(self):
        for item in QUERIES:
            with self.subTest(query=item["id"]):
                self.assertEqual(APP["detect_query_language"](item["question"]), item["language"])

    def test_fixture_routing(self):
        for item in QUERIES:
            with self.subTest(query=item["id"]):
                self.assertEqual(APP["classify_esg_intent"](item["question"]), item["current_intent"])

    def test_valid_multistep_calculation(self):
        result = DynamicMathExecutor.execute_code_lines(
            "withdrawals = 100\nconsumption = 60\ndifference = withdrawals - consumption"
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["environment"]["difference"], 40)

    def test_fy25_summary_matches_current_table(self):
        # Checks internal consistency, not independent PDF truth.
        frame = get_carbon_emissions_df()
        total = int(frame.loc[frame["Metric"].str.startswith("Total GHG"), "FY25"].iloc[0])
        for language in ("tr", "en"):
            with self.subTest(language=language):
                self.assertIn(f"{total:,}", APP["compute_carbon_trend_summary"](language))


class TestKnownRegressions(unittest.TestCase):
    @known_defect
    def test_failed_final_calculation_must_not_succeed(self):
        result = DynamicMathExecutor.execute_code_lines("a = 10\nresult = a / 0")
        self.assertFalse(result["success"], "A successful input assignment is not a successful calculation")

    @known_defect
    def test_water_difference_reaches_calculator(self):
        query = "FY25 su çekimi ile tüketimi arasındaki fark kaç metreküptür?"
        self.assertEqual(APP["classify_esg_intent"](query), "mathematical_query")

    @known_defect
    def test_sustainable_xbox_packaging_is_in_domain(self):
        self.assertTrue(APP["is_esg_query"]("Explain sustainable Xbox packaging"))

    def check_fy24_total_column(self, language):
        frame = get_carbon_emissions_df()
        expected = int(frame.loc[frame["Metric"].str.startswith("Total GHG"), "FY24"].iloc[0])
        summary = APP["compute_carbon_trend_summary"](language)
        rows = [line for line in summary.splitlines()
                if line.startswith("|") and ("Toplam Sera Gazı" in line or "Total GHG Emissions" in line)]
        self.assertEqual(len(rows), 1)
        cells = rows[0].split("|")
        self.assertIn(f"{expected:,}", cells[3], "FY24 column must use FY24's stored value")

    @known_defect
    def test_fy24_total_column_turkish(self):
        self.check_fy24_total_column("tr")

    @known_defect
    def test_fy24_total_column_english(self):
        self.check_fy24_total_column("en")


if __name__ == "__main__":
    unittest.main(verbosity=2)
