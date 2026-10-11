"""Source-backed water/energy checks; no model or UI process required."""
import ast
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import pandas as pd

from esg_tables import get_energy_metrics_df, get_water_metrics_df, get_water_replenishment_projects_df
from test_baseline_regressions import load_app_functions
from ingest_all_reports import audited_source_chunks

ROOT = Path(__file__).resolve().parent
FIXTURE = json.loads(ROOT.joinpath('tests/fixtures/resource_metrics_2026.json').read_text())
APP = load_app_functions({'compute_water_summary', 'compute_carbon_commitments_summary', 'compute_water_dashboard_metrics', 'get_esg_impact_insight'}, {
    'get_water_metrics_df': get_water_metrics_df, 'get_energy_metrics_df': get_energy_metrics_df, 'pd': pd,
})


class TestResourceMetrics(unittest.TestCase):
    def test_water_source_values_and_conversion(self):
        frame = get_water_metrics_df().set_index('Metric')
        for metric, values in FIXTURE['water_ml'].items():
            for year, value in zip(FIXTURE['years'], values):
                with self.subTest(metric=metric, year=year):
                    self.assertAlmostEqual(frame.loc[metric, year], value / 1000)
        self.assertEqual(set(frame.index), set(FIXTURE['water_ml']) | {'Water Replenishment (million m3)'})
        self.assertEqual(set(frame['Unit']), {'million m3'})

    def test_replenishment_is_annual_not_lifetime(self):
        frame = get_water_metrics_df().set_index('Metric')
        for year, value in zip(FIXTURE['years'], FIXTURE['annual_replenishment_m3']):
            self.assertAlmostEqual(frame.loc['Water Replenishment (million m3)', year], value / 1_000_000)
        self.assertFalse(any('Target' in metric or 'Achievement' in metric for metric in frame.index))

    def test_energy_source_values_and_missing_baseline(self):
        frame = get_energy_metrics_df().set_index('Metric')
        self.assertEqual(set(frame.index), set(FIXTURE['energy']))
        for metric, values in FIXTURE['energy'].items():
            for year, value in zip(FIXTURE['years'], values):
                with self.subTest(metric=metric, year=year):
                    if value is None:
                        self.assertTrue(pd.isna(frame.loc[metric, year]))
                    else:
                        self.assertEqual(frame.loc[metric, year], value)
        self.assertEqual(frame.loc['Total Electricity Consumption', 'Unit'], 'MWh')
        self.assertEqual(frame.loc['Direct Renewable Electricity Share (%)', 'Unit'], '%')
        # Table 5 excludes grid mix; Table 6 includes it. They are distinct metrics.
        ratio = frame.loc['Total Matched Renewable Electricity', 'FY25'] / frame.loc['Total Electricity Consumption', 'FY25'] * 100
        self.assertLess(ratio, 100)
        self.assertEqual(frame.loc['Direct Renewable Electricity Share (%)', 'FY25'], 100)

    def test_unverified_project_breakdown_is_not_numeric_evidence(self):
        self.assertTrue(get_water_replenishment_projects_df().empty)

    def test_water_summary_matches_source_and_units(self):
        for language in ('tr', 'en'):
            summary = APP['compute_water_summary'](language)
            self.assertIn('13.266', summary)
            self.assertIn('8.170', summary)
            self.assertIn('14.278782', summary)
            self.assertIn('5.096', summary)
            self.assertIn('https://aka.ms/SustainabilityFactsheet2026', summary)
            self.assertNotIn('7,800', summary)
            self.assertNotIn('82.1', summary)
            self.assertNotIn('125.0', summary)

    def test_energy_summary_does_not_claim_renewables_are_hourly_cfe(self):
        for language in ('tr', 'en'):
            summary = APP['compute_carbon_commitments_summary'](language)
            self.assertIn('37,026,353', summary)
            self.assertIn('34,534,392', summary)
            self.assertIn('100', summary)
            self.assertNotIn('43.8', summary)
            self.assertNotIn('41.6', summary)
            self.assertNotIn('95.0%', summary)

    def test_water_summary_uses_changed_table(self):
        frame = get_water_metrics_df()
        frame.loc[frame['Metric'] == 'Water Withdrawal (million m3)', 'FY25'] = 20
        with patch.dict(APP, {'get_water_metrics_df': lambda: frame}):
            for language in ('tr', 'en'):
                self.assertIn('20.000', APP['compute_water_summary'](language))


class TestResourceConsumers(unittest.TestCase):
    def test_water_dashboard_reads_realized_annual_volume(self):
        for language in ('tr', 'en'):
            kpi = APP['compute_water_dashboard_metrics'](language)
            self.assertTrue(kpi['value'].startswith('14.28'))
            self.assertTrue(kpi['delta'].startswith('+7.67'))
        frame = get_water_metrics_df()
        frame.loc[frame['Metric'] == 'Water Replenishment (million m3)', 'FY25'] = 20
        with patch.dict(APP, {'get_water_metrics_df': lambda: frame}):
            self.assertTrue(APP['compute_water_dashboard_metrics']('en')['value'].startswith('20.00'))
        # Check actual dashboard wiring without starting Streamlit.
        tree = ast.parse(ROOT.joinpath('app.py').read_text())
        calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
        water_cards = [node for node in calls if any(
            kw.arg == 'label' and isinstance(kw.value, ast.Subscript)
            and ast.unparse(kw.value) == "T['kpi_water_title']" for kw in node.keywords)]
        self.assertEqual(len(water_cards), 1)
        card = {kw.arg: ast.unparse(kw.value) for kw in water_cards[0].keywords}
        self.assertEqual(card['value'], "water_kpi['value']")
        self.assertEqual(card['delta'], "water_kpi['delta']")

    def test_ingestion_uses_shared_source_audited_water_rows(self):
        title = "Microsoft_2026_Environmental_Data_Fact_Sheet.pdf"
        digest = FIXTURE['source_pdf_sha256']
        chunks = audited_source_chunks(title, digest)
        inventory = '\n'.join(c['content'] for c in chunks if c['page'] == 7)
        self.assertIn('13.266', inventory)
        self.assertIn('8.17', inventory)
        self.assertIn('million m3', inventory)
        self.assertNotIn('Water Replenishment', inventory)
        frame = get_water_metrics_df()
        frame.loc[frame['Metric'] == 'Water Withdrawal (million m3)', 'FY24'] = 10.123
        with patch('ingest_all_reports.get_water_metrics_df', return_value=frame):
            inventory = '\n'.join(c['content'] for c in audited_source_chunks(title, digest) if c['page'] == 7)
            self.assertIn('FY24: 10.123', inventory)

    def test_energy_summary_uses_changed_values_and_missing_marker(self):
        frame = get_energy_metrics_df()
        frame.loc[frame['Metric'] == 'Total Electricity Consumption', 'FY25'] = 40_000_000
        with patch.dict(APP, {'get_energy_metrics_df': lambda: frame}):
            for language in ('tr', 'en'):
                summary = APP['compute_carbon_commitments_summary'](language)
                self.assertIn('40,000,000', summary)
                self.assertNotIn('37,026,353', summary)
                self.assertIn('—', summary)
                self.assertNotIn('nan', summary.lower())


class TestWaterInsight(unittest.TestCase):
    def test_insight_uses_annual_values_and_withdrawal_target(self):
        for language in ('tr', 'en'):
            card = APP['get_esg_impact_insight']('water replenishment', 'water', language)
            self.assertIn('14.278782', card['actions'])
            self.assertIn('13.266', card['actions'])
            self.assertNotIn('125M', card['actions'])
            self.assertIn('Çekilenden' if language == 'tr' else 'Withdrawn', card['target'])


class TestPackagingPeriods(unittest.TestCase):
    def test_restated_fiscal_values(self):
        from esg_tables import get_packaging_metrics_df
        frame = get_packaging_metrics_df().set_index('Metric')
        expected = {
            'Product packaging recyclability': [94.3, 93.7, 94.6, 95.8],
            'Single-use plastics in primary product packaging': [4.7, 4.6, 5.4, 4.2],
        }
        for metric, values in expected.items():
            for year, value in zip(['FY22', 'FY23', 'FY24', 'FY25'], values):
                with self.subTest(metric=metric, year=year):
                    self.assertEqual(frame.loc[metric, year], value)
        self.assertEqual(set(frame['Unit']), {'%'})
        self.assertNotIn('FY26', frame.columns)

    def test_calendar_actual_is_separate_series(self):
        from esg_tables import get_packaging_calendar_metrics_df, get_packaging_metrics_df
        calendar = get_packaging_calendar_metrics_df()
        self.assertEqual(calendar.iloc[0]['CY2025'], 0.07)
        self.assertNotIn('FY25', calendar.columns)
        self.assertNotIn('CY2025', get_packaging_metrics_df().columns)

    def test_bilingual_summaries_explain_periods_and_no_fabricated_certification(self):
        from esg_tables import get_packaging_calendar_metrics_df, get_packaging_metrics_df
        functions = load_app_functions({'compute_packaging_summary'}, {
            'get_packaging_metrics_df': get_packaging_metrics_df,
            'get_packaging_calendar_metrics_df': get_packaging_calendar_metrics_df,
        })
        for lang in ['tr', 'en']:
            answer = functions['compute_packaging_summary'](lang)
            self.assertIn('FY24', answer)
            self.assertIn('5.4', answer)
            self.assertIn('4.2', answer)
            self.assertIn('0.07', answer)
            self.assertIn('FY26', answer)
            self.assertIn('Table 11', answer)
            self.assertNotIn('100% FSC', answer)
            self.assertNotIn('UL Solutions Audit', answer)

    def test_summary_reads_shared_values(self):
        from esg_tables import get_packaging_calendar_metrics_df, get_packaging_metrics_df
        def changed():
            frame = get_packaging_metrics_df()
            frame.loc[1, 'FY25'] = 3.1
            return frame
        functions = load_app_functions({'compute_packaging_summary'}, {
            'get_packaging_metrics_df': changed,
            'get_packaging_calendar_metrics_df': get_packaging_calendar_metrics_df,
        })
        self.assertIn('3.1', functions['compute_packaging_summary']('en'))
