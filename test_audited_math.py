import unittest
from audited_math import execute_audited_plan, plan_user_prompt, render_audited_result


def evidence(key, metric, unit, values, kind='audited_table'):
    return {'id': key, 'chunk_type': kind, 'title': 'Source.pdf (p.7)',
            'content': f'Metric: {metric} ({unit})\n' + '\n'.join(f'{year}: {value}' for year, value in values.items())}


def plan(op, unit, refs):
    return {'available': True, 'operation': op, 'output_unit': unit,
            'operands': [{'evidence_id': key, 'period': period} for key, period in refs]}


class TestAuditedMath(unittest.TestCase):
    def setUp(self):
        self.rows = [evidence(1, 'Water Withdrawal', 'million m3', {'FY24': '11.59', 'FY25': '13.266'}),
                     evidence(2, 'Water Consumption', 'million m3', {'FY24': '6.693', 'FY25': '8.17'}),
                     evidence(3, 'Total Waste Generated', 'mt', {'FY25': '58868'}),
                     evidence(4, 'Total Operational Waste Diverted', 'mt', {'FY25': '36149'})]

    def test_difference_converts_source_units_for_both_languages(self):
        for query in ['Calculate FY25 water withdrawal minus consumption in cubic meters.',
                      'FY25 su çekimi ile tüketimi farkını metreküp olarak hesapla.']:
            result = execute_audited_plan(plan('difference', 'm3', [(1, 'FY25'), (2, 'FY25')]), self.rows, query)
            self.assertTrue(result['success'])
            self.assertEqual(result['result'], 5096000)
            self.assertEqual(result['result_text'], '5096000.000')
            self.assertIn('m3', render_audited_result(result))
            self.assertEqual([o['evidence_id'] for o in result['operands']], [1, 2])

    def test_unit_alias_preserves_dimension_and_scale(self):
        candidate = plan('percent_of', 'percent', [(4, 'FY25'), (3, 'FY25')])
        result = execute_audited_plan(candidate, self.rows, 'FY25 waste diversion percentage')
        self.assertTrue(result['success'])
        self.assertEqual(result['unit'], '%')
        candidate['output_unit'] = 'p'
        self.assertEqual(execute_audited_plan(candidate, self.rows, 'FY25 waste diversion percentage')['unit'], '%')

    def test_human_requested_output_unit_overrides_untrusted_model_metadata(self):
        result = execute_audited_plan(plan('difference', 'million m3', [(1, 'FY25'), (2, 'FY25')]),
                                     self.rows, 'FY25 water difference in cubic meters')
        self.assertTrue(result['success'])
        self.assertEqual(result['result'], 5096000)
        self.assertEqual(result['unit'], 'm3')

    def test_percentage_calculated_from_source_not_model_numbers(self):
        result = execute_audited_plan(plan('percent_of', '%', [(4, 'FY25'), (3, 'FY25')]),
                                     self.rows, 'FY25 waste diversion percentage')
        self.assertAlmostEqual(result['result'], 36149 / 58868 * 100)

    def test_model_supplied_values_and_unknown_ids_rejected(self):
        candidate = plan('difference', 'm3', [(1, 'FY25'), (2, 'FY25')])
        candidate['operands'][0]['value'] = 9000
        self.assertFalse(execute_audited_plan(candidate, self.rows, 'FY25 water')['success'])
        self.assertFalse(execute_audited_plan(plan('sum', 'm3', [(900, 'FY25')]), self.rows, 'FY25 water')['success'])
        candidate = plan('sum', 'm3', [(True, 'FY25')])
        self.assertFalse(execute_audited_plan(candidate, self.rows, 'FY25 water')['success'])

    def test_wrong_period_and_partial_comparison_rejected(self):
        for refs in [[(1, 'FY24'), (2, 'FY24')], [(1, 'FY25'), (2, 'FY25')]]:
            query = 'FY25 water difference' if refs[0][1] == 'FY24' else 'Compare FY24 and FY25 water'
            self.assertFalse(execute_audited_plan(plan('difference', 'm3', refs), self.rows, query)['success'])

    def test_missing_qualified_non_audited_data_rejected(self):
        for value in ['[NOT REPORTED]', 'More than 45 million', 'NaN', 'inf']:
            rows = [evidence(5, 'Removal', 'mt', {'FY25': value}), self.rows[2]]
            result = execute_audited_plan(plan('difference', 'mt', [(5, 'FY25'), (3, 'FY25')]), rows, 'FY25')
            self.assertEqual(result['status'], 'unavailable')
        rows = [evidence(1, 'Water', 'million m3', {'FY25': '9000'}, kind='text')]
        self.assertNotIn('9000', plan_user_prompt('FY25 water', rows))

    def test_incompatible_units_duplicate_inputs_and_zero_division(self):
        bad = [plan('sum', 'm3', [(1, 'FY25'), (3, 'FY25')]),
               plan('sum', 'm3', [(1, 'FY25'), (1, 'FY25')])]
        for candidate in bad:
            self.assertFalse(execute_audited_plan(candidate, self.rows, 'FY25')['success'])
        rows = self.rows + [evidence(5, 'Zero Waste', 'mt', {'FY25': '0'})]
        self.assertFalse(execute_audited_plan(plan('ratio', 'ratio', [(3, 'FY25'), (5, 'FY25')]), rows, 'FY25')['success'])

    def test_energy_conversion_and_percentage_point_change(self):
        rows = [evidence(1, 'Electricity', 'MWh', {'FY24': '100', 'FY25': '250'}),
                evidence(2, 'Share', '%', {'FY24': '40', 'FY25': '50'})]
        result = execute_audited_plan(plan('difference', 'kWh', [(1, 'FY25'), (1, 'FY24')]), rows,
                                     'FY24 and FY25 electricity difference in kWh')
        self.assertEqual(result['result'], 150000)
        result = execute_audited_plan(plan('percentage_point_change', 'percentage points', [(2, 'FY24'), (2, 'FY25')]),
                                     rows, 'FY24 to FY25 percentage point change')
        self.assertEqual(result['result'], 10)
        result = execute_audited_plan(plan('percent_change', '%', [(2, 'FY24'), (2, 'FY25')]), rows,
                                     'FY24 to FY25 percentage change')
        self.assertEqual(result['result'], 25)

    def test_temporal_change_rejects_swapped_periods_and_different_metrics(self):
        candidate = plan('percent_change', '%', [(1, 'FY25'), (1, 'FY24')])
        self.assertFalse(execute_audited_plan(candidate, self.rows, 'FY24 to FY25 percentage change')['success'])
        candidate = plan('percent_change', '%', [(1, 'FY24'), (2, 'FY25')])
        self.assertFalse(execute_audited_plan(candidate, self.rows, 'FY24 to FY25 percentage change')['success'])

    def test_commitments_cannot_substitute_for_realized_removals(self):
        rows = [evidence(1, 'Total Contracted Carbon Removal', 'mt', {'FY24': '21927370'})]
        candidate = plan('value', 'mt', [(1, 'FY24')])
        for query in ['FY24 realized carbon removal in metric tons', 'FY24 gerçekleşen karbon giderimi']:
            self.assertEqual(execute_audited_plan(candidate, rows, query)['status'], 'unavailable')

    def test_scope_qualifications_survive_rendering(self):
        row = evidence(1, 'Total Waste Generated', 'mt', {'FY24': '41290', 'FY25': '58868'})
        row['content'] += '\nInventory scope: FY25 includes cloud packaging; prior years were not adjusted.'
        result = execute_audited_plan(plan('percent_change', '%', [(1, 'FY24'), (1, 'FY25')]), [row],
                                     'Calculate FY24 to FY25 percentage change in waste generated')
        self.assertTrue(result['success'])
        self.assertIn('prior years were not adjusted', render_audited_result(result))

    def test_python_never_executed_and_false_plan_has_no_calculation(self):
        self.assertFalse(execute_audited_plan('result = 1 + 2', self.rows, 'FY25')['success'])
        self.assertEqual(execute_audited_plan({'available': False}, self.rows, 'FY25')['status'], 'unavailable')
        self.assertFalse(execute_audited_plan({'available': False, 'result': 9000}, self.rows, 'FY25')['success'])


class TestBoundedPlanRepair(unittest.TestCase):
    def test_retry_corrects_schema_without_accepting_model_numbers(self):
        import json
        from unittest.mock import Mock
        from audited_math import calculate_with_model
        rows = [evidence(1, 'Water Withdrawal', 'million m3', {'FY25': '13.266'}),
                evidence(2, 'Water Consumption', 'million m3', {'FY25': '8.17'})]
        bad = plan('difference', 'million m3', [(1, 'FY25'), (2, 'FY25')])
        bad['operands'][0]['value'] = 9000
        good = plan('difference', 'm3', [(1, 'FY25'), (2, 'FY25')])
        model = Mock(side_effect=[json.dumps(bad), json.dumps(good)])
        result, attempts = calculate_with_model('FY25 water difference in cubic meters', rows, model)
        self.assertEqual(result['result'], 5096000)
        self.assertEqual(len(attempts), 2)
        self.assertIn('Validation error', model.call_args.args[1])
        self.assertNotIn('5096000', model.call_args.args[1])

    def test_repeated_invalid_and_unavailable_stop(self):
        from unittest.mock import Mock
        from audited_math import calculate_with_model
        model = Mock(return_value='{"available": true, "value": 9000}')
        result, attempts = calculate_with_model('FY25 water', [], model)
        self.assertFalse(result['success'])
        self.assertEqual(len(attempts), 2)
        model = Mock(return_value='{"available": false}')
        result, attempts = calculate_with_model('FY25 water', [], model)
        self.assertEqual(result['status'], 'unavailable')
        self.assertEqual(len(attempts), 1)


if __name__ == '__main__':
    unittest.main()
