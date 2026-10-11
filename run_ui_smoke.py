"""Opt-in real Streamlit script/widget checks; needs production dependencies/index."""
import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    from streamlit.testing.v1 import AppTest
    app = AppTest.from_file(str(Path(__file__).with_name('app.py')), default_timeout=120)
    records = []
    cases = [
        ('waste-source', 'What is the FY25 total operational waste generated in metric tons?', ['58868']),
        ('water-calculation', 'Calculate FY25 water withdrawal minus consumption in cubic meters.', ['5096000']),
        ('calendar-packaging', 'What is CY2025 single-use plastics in primary product packaging percentage?', ['0.07']),
        ('multi-source-narrative', 'Describe renewable electricity policy and grid planning.', ['source excerpts|Kaynakta yer alan']),
        ('scoped-water', 'Describe groundwater withdrawal in Madrid.', ['cannot|doğrulan|bulunamad|yetersiz']),
        ('ambiguous-year', '2025 packaging percentage?', ['fiscal|mali']),
    ]
    app.run()
    if app.exception:
        records.append({'case': 'startup', 'passed': False, 'errors': [e.message for e in app.exception]})
    else:
        records.append({'case': 'startup', 'passed': True})
        for name, query, required in cases:
            try:
                before = len(app.session_state['messages'])
                # AppTest's ButtonGroup serializer expects lists even for single-select pills.
                # Preserve each actual selection; no application behavior is mocked.
                for group in app.get('button_group'):
                    value = group.value
                    group.set_value(value if isinstance(value, list) else [] if value is None else [value])
                app.chat_input[0].set_value(query).run(timeout=120)
                messages = app.session_state['messages']
                answer = messages[-1] if messages else {}
                errors = [e.message for e in app.exception]
                passed = (not errors and len(messages) >= before + 2 and answer.get('role') == 'assistant'
                          and all(any(variant.lower() in answer.get('content', '').lower() for variant in term.split('|')) for term in required))
                if name == 'multi-source-narrative':
                    validation = answer.get('narrative_validation') or {}
                    refs = {ref['evidence_id'] for ref in validation.get('references', [])}
                    provenance = {chunk['id'] for chunk in answer.get('provenance', [])}
                    passed = passed and validation.get('status') == 'source_excerpt' and bool(refs) and refs == provenance
                if name in ('calendar-packaging', 'scoped-water'):
                    passed = passed and answer.get('intent') == 'general_rag'
                records.append({'case': name, 'query': query, 'passed': passed,
                                'answer': answer.get('content', ''), 'route': answer.get('route'),
                                'intent': answer.get('intent'), 'grounding': answer.get('narrative_validation'), 'errors': errors})
            except Exception as exc:
                import traceback
                traceback.print_exc()
                records.append({'case': name, 'passed': False, 'error': f'{type(exc).__name__}: {exc}'})
    report = {'kind': 'real_streamlit_script_and_widget_flow', 'cases': records,
              'passed': sum(row['passed'] for row in records), 'total': len(records),
              'limitations': 'AppTest does not certify browser visuals, all static routes or all model answers.'}
    Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: report[k] for k in ['passed', 'total']}))
    return 0 if report['passed'] == report['total'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
