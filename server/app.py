"""Loopback-only UI. Run with python -m server.app from an activated environment.

GET endpoints expose local profile/run data; token-protected POST endpoints
validate profile edits, launch one CLI worker, or save a separate review copy.
Invalid input returns 400; an active worker returns 409. No sending capability.
"""
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
import threading
from dataclasses import asdict
import yaml
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

from agent.profile import load_profile
from server.credentials import worker_environment, key_status, save_keys

ROOT = Path(__file__).resolve().parents[1]
TOKEN = secrets.token_urlsafe(32)
LOCK = threading.Lock()
PROCESS = None
LOG = ROOT / 'drafts/ui-worker.log'


def run_dir(name):
    if not isinstance(name, str) or not re.fullmatch(r'(run|outreach)-[a-f0-9]{32}', name):
        raise ValueError('Choose a saved run.')
    path = ROOT / 'drafts' / name
    if path.is_symlink() or not (path / 'results.json').is_file():
        raise ValueError('Run not found.')
    return path


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def start_run(data):
    global PROCESS
    with LOCK:
        if PROCESS is not None and PROCESS.poll() is None:
            raise RuntimeError('A run is already active. Wait for it to finish.')
        load_profile(ROOT / 'profile/profile.yaml')
        mode = data.get('mode')
        command = [sys.executable, '-u', '-m']
        required = ['GEMINI_API_KEY']
        if mode == 'search':
            count = data.get('max_jobs', 10)
            if type(count) is not int or not 1 <= count <= 100:
                raise ValueError('Assess between 1 and 100 jobs.')
            command += ['agent.cli', '--max-jobs', str(count), '--top-k', '3']
            required += ['OPENWEBNINJA_API_KEY']
        elif mode in ('research', 'resume'):
            source = run_dir(data.get('run')) / 'results.json'
            if mode == 'research':
                from agent.shortlist_outreach import selected_jobs
                selected_jobs(source)
                command += ['agent.shortlist_outreach', '--results', str(source)]
                required += ['TAVILY_API_KEY']
            else:
                command += ['agent.cli', '--resume-results', str(source), '--max-jobs', '100']
        else:
            raise ValueError('Unknown run action.')
        environment = worker_environment()
        missing = [key for key in required if not environment.get(key, '').strip()]
        if missing:
            raise ValueError('Add these keys in API setup: ' + ', '.join(missing))
        LOG.parent.mkdir(exist_ok=True)
        with LOG.open('w', encoding='utf-8') as log:
            PROCESS = subprocess.Popen(command, cwd=ROOT, env=environment, stdout=log, stderr=subprocess.STDOUT)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def reply(self, value, status=200, content_type='application/json'):
        body = (json.dumps(value) if content_type == 'application/json' else value).encode()
        self.send_response(status)
        self.send_header('Content-Type', content_type + '; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; frame-ancestors 'none'; base-uri 'none'")
        self.end_headers()
        self.wfile.write(body)

    def allowed(self, write=False):
        host = f'127.0.0.1:{self.server.server_port}'
        if self.headers.get('Host') != host:
            return False
        if write:
            return (self.headers.get('Origin') == f'http://{host}'
                    and secrets.compare_digest(self.headers.get('X-UI-Token', ''), TOKEN))
        return True

    def do_GET(self):
        if not self.allowed():
            return self.reply({'error': 'Use the local server URL.'}, 403)
        url = urlparse(self.path)
        try:
            if url.path == '/':
                return self.reply((ROOT / 'server/index.html').read_text().replace('__TOKEN__', TOKEN), content_type='text/html')
            if url.path == '/api/profile':
                path = ROOT / 'profile/profile.yaml'
                return self.reply({'profile': asdict(load_profile(path if path.exists() else ROOT / 'profile/profile.yaml.example'))})
            if url.path == '/api/state':
                runs = []
                for path in sorted((ROOT / 'drafts').glob('*/results.json'), key=lambda p: p.stat().st_mtime, reverse=True):
                    if not re.fullmatch(r'(run|outreach)-[a-f0-9]{32}', path.parent.name):
                        continue
                    try:
                        report = read_json(path)
                        runs.append({'id': path.parent.name, 'status': report.get('status'), 'date': report.get('created_at')})
                    except (ValueError, OSError):
                        continue
                return self.reply({'active': PROCESS is not None and PROCESS.poll() is None,
                                   'exit_code': PROCESS.poll() if PROCESS else None,
                                   'log': LOG.read_text()[-20000:] if LOG.exists() else '', 'runs': runs,
                                   'keys': key_status()})
            if url.path == '/api/report':
                directory = run_dir(parse_qs(url.query).get('run', [''])[0])
                report = read_json(directory / 'results.json')
                edits = directory / 'review-edits.json'
                return self.reply({'report': report, 'edits': read_json(edits) if edits.exists() else {}})
            return self.reply({'error': 'Not found'}, 404)
        except (ValueError, OSError) as error:
            return self.reply({'error': str(error)}, 400)

    def do_POST(self):
        if not self.allowed(write=True):
            return self.reply({'error': 'Invalid local request. Reload the page.'}, 403)
        if self.path == '/api/resume':
            return self.import_resume()
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 < size <= 200000:
                raise ValueError('Request is empty or too large.')
            data = json.loads(self.rfile.read(size))
            if not isinstance(data, dict):
                raise ValueError('Expected an object.')
            if self.path == '/api/start':
                start_run(data)
            elif self.path == '/api/keys':
                with LOCK:
                    save_keys(data)
            elif self.path == '/api/profile':
                with LOCK:
                    if PROCESS is not None and PROCESS.poll() is None:
                        raise RuntimeError('Wait for the active run before editing the profile.')
                    if not isinstance(data.get('profile'), dict):
                        raise ValueError('Expected profile fields.')
                    # Temporary private content stays beside the gitignored profile.
                    path = ROOT / 'profile/profile.yaml'
                    temporary = ROOT / 'drafts/ui-profile.tmp'
                    temporary.parent.mkdir(exist_ok=True)
                    try:
                        temporary.write_text(yaml.safe_dump(data['profile'], sort_keys=False, allow_unicode=True))
                        load_profile(temporary)
                        temporary.replace(path)
                    finally:
                        temporary.unlink(missing_ok=True)
            elif self.path == '/api/edit':
                directory = run_dir(data.get('run'))
                rank = data.get('rank')
                report = read_json(directory / 'results.json')
                if not any(e.get('rank') == rank and 'draft' in e for e in report.get('jobs', [])):
                    raise ValueError('Draft not found.')
                if any(not isinstance(data.get(k), str) or not data[k].strip() for k in ('subject', 'body')):
                    raise ValueError('Subject and message must be nonempty.')
                with LOCK:
                    path = directory / 'review-edits.json'
                    edits = read_json(path) if path.exists() else {}
                    edits[str(rank)] = {k: data[k] for k in ('subject', 'body')}
                    temp = directory / 'review-edits.json.tmp'
                    temp.write_text(json.dumps(edits, indent=2))
                    temp.replace(path)
            else:
                return self.reply({'error': 'Not found'}, 404)
            self.reply({'ok': True})
        except RuntimeError as error:
            self.reply({'error': str(error)}, 409)
        except (ValueError, OSError) as error:
            self.reply({'error': str(error)}, 400)

    def import_resume(self):
        from agent.resume import propose_background, MAX_BYTES
        from agent.research_runtime import ResearchError
        from agent.quota import QuotaError
        if not LOCK.acquire(blocking=False):
            return self.reply({'error': 'Another operation is active. Try again shortly.'}, 409)
        try:
            if PROCESS is not None and PROCESS.poll() is None:
                raise ValueError('Wait for the active run before importing a resume.')
            if self.headers.get('X-Resume-Consent') != 'yes':
                raise ValueError('Confirm sending resume text to Gemini before processing.')
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 < size <= MAX_BYTES:
                raise ValueError('Upload a PDF under 5 MB.')
            key = worker_environment().get('GEMINI_API_KEY', '').strip()
            if not key:
                raise ValueError('Add your Gemini key in API setup first.')
            result = propose_background(self.rfile.read(size), key)
            self.reply(result)
        except (ValueError, ResearchError, QuotaError) as error:
            self.reply({'error': str(error)}, 400)
        finally:
            LOCK.release()


def main():
    server = ThreadingHTTPServer(('127.0.0.1', 8765), Handler)
    print('Open http://127.0.0.1:8765 — local review only. Nothing sends.', flush=True)
    if '--open' in sys.argv:
        import webbrowser
        webbrowser.open('http://127.0.0.1:8765')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        if PROCESS is not None and PROCESS.poll() is None:
            PROCESS.terminate()
            PROCESS.wait()
        server.server_close()


if __name__ == '__main__':
    main()
