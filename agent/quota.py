"""Safe Gemini quota metadata and bounded workflow retry signals."""
import math
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime


class QuotaError(RuntimeError):
    def __init__(self, details):
        self.details = details
        super().__init__('Gemini quota/rate limit (429); ' + str(details))


def quota_error(response):
    """Extract allowlisted identifiers/timing, never raw response text or keys."""
    details = {'http_status': 429}
    delays = []
    def delay(value):
        try:
            number = float(str(value).removesuffix('s'))
            if math.isfinite(number) and number >= 0:
                delays.append(number)
        except (ValueError, TypeError):
            pass
    header = response.headers.get('Retry-After')
    if header:
        try:
            delay(max(0, (parsedate_to_datetime(header) - datetime.now(timezone.utc)).total_seconds()))
        except (ValueError, TypeError, OverflowError):
            delay(header)
    try:
        error = response.json().get('error', {})
        for item in error.get('details', []):
            if not isinstance(item, dict):
                continue
            if item.get('@type', '').endswith('RetryInfo'):
                delay(item.get('retryDelay'))
            if item.get('@type', '').endswith('QuotaFailure'):
                quotas = []
                for violation in item.get('violations', []):
                    if not isinstance(violation, dict):
                        continue
                    safe = {k: v for k in ('quotaMetric', 'quotaId')
                            if isinstance((v := violation.get(k)), str)
                            and re.fullmatch(r'[A-Za-z0-9_./-]{1,200}', v)}
                    if safe:
                        quotas.append(safe)
                if quotas:
                    details['quotas'] = quotas
    except (ValueError, AttributeError, TypeError):
        pass
    if delays:
        details['retry_after_seconds'] = max(delays)
    return QuotaError(details)
