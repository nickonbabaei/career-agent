"""Paced, bounded retry support for research and outreach."""
import json
import os
import time
import requests
from agent.quota import QuotaError, quota_error


class ResearchError(RuntimeError):
    pass


class BudgetExhausted(ResearchError):
    pass


class Runtime:
    def __init__(self, rpm=10):
        if type(rpm) is not int or rpm < 1:
            raise ValueError('gemini-rpm must be positive.')
        self.interval = 60 / rpm
        self.next_start = 0

    def call(self, operation, errors, stage, retry_errors, model=False, consume=None):
        """Retry once; count attempts before calls, pace all model attempts."""
        for attempt in (1, 2):
            if consume:
                consume()
            if model:
                wait = max(0, self.next_start - time.monotonic())
                while wait > 0:
                    chunk = min(wait, 60)
                    time.sleep(chunk)
                    wait -= chunk
                self.next_start = time.monotonic() + self.interval
            try:
                return operation()
            except QuotaError as error:
                errors.append({'stage': stage, 'attempt': attempt, **error.details})
                delay = error.details.get('retry_after_seconds', 30)
                if attempt == 2 or delay > 60:
                    raise
                print(f'Gemini limited; waiting {delay:g}s before retry.')
                time.sleep(delay)
            except retry_errors as error:
                errors.append({'stage': stage, 'attempt': attempt, 'message': str(error)})
                if attempt == 2:
                    raise


def model_json(prompt, context, schema, *, api_key=None, max_output_tokens=2400):
    """One structured Gemini request. Caller owns pacing/budget/retries."""
    key = (api_key if api_key is not None else os.environ.get('GEMINI_API_KEY', '')).strip()
    if not key:
        raise ValueError('Set GEMINI_API_KEY.')
    try:
        response = requests.post(
            'https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent',
            headers={'x-goog-api-key': key}, timeout=60,
            json={'systemInstruction': {'parts': [{'text': prompt}]},
                  'contents': [{'role': 'user', 'parts': [{'text': json.dumps(context)}]}],
                  'generationConfig': {'responseMimeType': 'application/json',
                                       'responseJsonSchema': schema, 'maxOutputTokens': max_output_tokens}})
        response.raise_for_status()
    except requests.RequestException as error:
        if error.response is not None and error.response.status_code == 429:
            raise quota_error(error.response) from error
        status = error.response.status_code if error.response is not None else 'connection/timeout'
        raise ResearchError(f'Gemini research failed ({status}).') from error
    try:
        payload = response.json()
        if payload.get('promptFeedback', {}).get('blockReason'):
            raise ValueError('Blocked')
        candidates = payload['candidates']
        if len(candidates) != 1 or candidates[0].get('finishReason') != 'STOP':
            raise ValueError('Incomplete')
        text = ''.join(p['text'] for p in candidates[0]['content']['parts']
                       if 'text' in p and not p.get('thought'))
        result = json.loads(text)
        if not isinstance(result, dict):
            raise ValueError('Not an object')
        return result
    except (ValueError, KeyError, TypeError, AttributeError) as error:
        raise ResearchError('Invalid or incomplete research output.') from error
