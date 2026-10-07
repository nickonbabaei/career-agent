"""Inspect public evidence before building automated contact selection."""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from agent.research_tools import search_web, read_page, ResearchToolError, prioritize_pages, contact_sections


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--query', required=True, help='Public company/role query; do not include private profile data')
    args = parser.parse_args()
    directory = Path('drafts') / f'research-{uuid4().hex}'
    directory.mkdir(parents=True)
    report = {'created_at': datetime.now(timezone.utc).isoformat(), 'query': args.query,
              'status': 'running', 'search_results': [], 'pages': [], 'errors': [],
              'contact': None, 'note': 'Evidence probe only; no contact selected or verified.'}
    def save():
        temp = directory / 'evidence.json.tmp'
        temp.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
        temp.replace(directory / 'evidence.json')
    def attempt(stage, operation):
        for number in (1, 2):
            try:
                return operation()
            except ResearchToolError as error:
                report['errors'].append({'stage': stage, 'attempt': number, 'message': str(error)})
                print(f'{stage} attempt {number}: {error}')
                save()
        return None
    save()
    try:
        results = attempt('search', lambda: search_web(args.query))
        report['search_results'] = results or []
        save()
        if results:
            # Two pages, each retried once: at most four page-read attempts.
            for row in prioritize_pages(results)[:2]:
                page = attempt('read', lambda: read_page(row['url'], {r['url'] for r in results}))
                if page:
                    page['contact_sections'] = contact_sections(page)
                    report['pages'].append(page)
                save()
        report['status'] = 'search_failed' if results is None else ('completed_with_errors' if report['errors'] else 'completed')
    except ValueError as error:
        report['status'] = 'configuration_error'
        report['errors'].append({'stage': 'configuration', 'message': str(error)})
    save()
    preview = ['# Research evidence previews', '',
               'Keyword-selected excerpts; not verified contacts. Full provider text is in evidence.json.', '']
    for page in report['pages']:
        preview.extend([f"## {page['url']}", '', f"Retained {len(page['text'])} characters in {len(page['sections'])} sections.", ''])
        for section in page['contact_sections']:
            preview.extend([f"### Section {section['id']} (characters {section['start']}–{section['end']})", '', section['text'], ''])
    (directory / 'evidence-preview.md').write_text('\n'.join(preview), encoding='utf-8')
    print(f"Status: {report['status']}\nEvidence: {(directory / 'evidence.json').resolve()}\nNo contact selected. Nothing sent.")
    return 0 if report['status'] == 'completed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
