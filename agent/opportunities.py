"""Fixed automatic first pass; persist child reports and a consolidated review."""
import argparse
import json
from pathlib import Path
from uuid import uuid4
from datetime import datetime, timezone
from agent.profile import load_profile
from agent.workflow import run_workflow
from agent.shortlist_outreach import run as research
from agent.reviewed_drafting import run as draft


def run(profile, max_jobs=30, source=None):
    directory = Path('drafts') / ('outreach-' + uuid4().hex)
    directory.mkdir(parents=True)
    report = dict(stage='opportunities', status='running', phase='Finding and ranking jobs',
                  created_at=datetime.now(timezone.utc).isoformat(), jobs=[], nothing_sent=True)
    def save():
        tmp=directory/'results.json.tmp'
        tmp.write_text(json.dumps(report, indent=2))
        tmp.replace(directory/'results.json')
    save()
    try:
        if source:
            previous=json.loads(Path(source).read_text())
            if previous.get('stage')!='opportunities' or previous.get('status')=='running':
                raise ValueError('Choose a finished opportunities run.')
            report.update({k:previous[k] for k in ('jobs','ranking','source_results','found','assessed','unassessed')})
            saved_edits=Path(source).parent/'review-edits.json'
            if saved_edits.exists():
                (directory/'review-edits.json').write_text(saved_edits.read_text())
        else:
            search_dir, found=run_workflow(profile,max_jobs,top_k=3)
            report.update(source_results=str(search_dir/'results.json'), jobs=found['jobs'],
                          ranking=found['ranking'], found=found['found'], assessed=found['assessed'],
                          unassessed=found['unassessed'], search_status=found['status'])
            if found['status'] in ('quota_limited','search_failed','ranking_failed'):
                report.update(status=found['status'],phase='Stopped; search progress saved')
                return directory,report
        entries={j['id']:j for j in report['jobs']}
        ids=[r['id'] for r in report['ranking'] if 'outreach' not in entries[r['id']]][:3]
        report['phase']='Researching contacts for strongest remaining matches';save()
        if ids:
            research_dir, researched=research(report['source_results'],profile,job_ids=ids,research_only=True)
            report['research_results']=str(research_dir/'results.json')
            for item in researched['jobs']:
                entries[item['rank']]['outreach']=item
            save()
            choices={str(j['rank']):{'mode':'researched' if j.get('research',{}).get('contact') and j['status']=='awaiting_recipient_choice' else 'skip'} for j in researched['jobs']}
            if researched['status']!='quota_limited' and any(c['mode']=='researched' for c in choices.values()):
                report['phase']='Preparing personalized drafts';save()
                choice_path=directory/'choices.json';choice_path.write_text(json.dumps(choices))
                draft_dir,drafted=draft(research_dir/'results.json',choice_path,profile)
                report['draft_results']=str(draft_dir/'results.json')
                for item in drafted['jobs']:
                    entries[item['rank']]['outreach'].update(item)
                if drafted['status']!='completed': report['status']=drafted['status']
            if researched['status']!='completed': report['status']=researched['status']
        if report['status']=='running': report['status']='completed'
        report['phase']='Ready for review'
        return directory,report
    except Exception as error:
        report.update(status='failed',phase='Stopped; progress saved',errors=[{'message':str(error)}])
        raise
    finally:
        save()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--max-jobs',type=int,default=30)
    parser.add_argument('--source')
    args=parser.parse_args()
    directory,report=run(load_profile('profile/profile.yaml'),args.max_jobs,args.source)
    print(f"Status: {report['status']}\nReview: {directory}\nNothing sent.")
    return 0 if report['status']=='completed' else 1

if __name__=='__main__': raise SystemExit(main())
