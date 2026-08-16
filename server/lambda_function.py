"""claudeusage community stats service.

Receives anonymous daily usage totals and returns the community average plus an
opt-in leaderboard. This is the entire server. Nothing else is stored.

What a report contains:
    install_id  a random UUID generated on the client, not derived from anything
    handle      optional display name, only if the user opted into the leaderboard
    days        {"YYYY-MM-DD": {"t": tokens, "c": equiv_cost, "p": prompts}}

What it never contains: file paths, project names, session ids, model names,
prompt text, response text, IP-derived identifiers, or anything else.

Routes (Lambda Function URL, no auth):
    POST /report   upsert this install's recent daily totals
    GET  /stats    community average + leaderboard
"""
import json
import os
import re
import time
from decimal import Decimal

import boto3

TABLE = os.environ.get('TABLE_NAME', 'ClaudeUsageCommunity')
_ddb = boto3.resource('dynamodb')
_table = _ddb.Table(TABLE)

KEEP_DAYS = 30          # per-install history retained
WINDOW_DAYS = 7         # trailing window the published averages use
LEADERBOARD_SIZE = 10

# Sanity clamps. A report outside these is treated as junk and dropped, so one
# bad or malicious client cannot move the community average.
MAX_TOKENS_DAY = 20_000_000_000
MAX_COST_DAY = 100_000.0
MAX_PROMPTS_DAY = 10_000

HANDLE_RE = re.compile(r'^[A-Za-z0-9_.-]{2,24}$')

# Latest published client version, surfaced on /stats so installs can tell the
# user an update exists. Bumped with `aws lambda update-function-configuration`
# at release time - no code deploy needed.
LATEST_VERSION = os.environ.get('LATEST_VERSION', '1.0.0')

# ---- handle moderation ------------------------------------------------------
# The leaderboard is public, so handles are screened here. This has to live on
# the server: a client-side filter is bypassed by anyone POSTing directly.
_LEET = str.maketrans({'4': 'a', '@': 'a', '3': 'e', '1': 'i', '!': 'i', '|': 'i',
                       '0': 'o', '5': 's', '$': 's', '7': 't', '+': 't', '8': 'b',
                       '9': 'g', '6': 'g', '2': 'z'})

# Tier 1: matched anywhere in the handle. Only strings that essentially never
# occur inside an innocent word belong here.
_BLOCK_ANY = frozenset("""
fuck fuk fck phuck motherfuck cocksuck dickhead asshole assfuck dumbass jackass
shit bullshit bitch cunt whore bastard wanker bollock arsehole
nigger nigga faggot fagot chink wetback beaner raghead tranny
paedo pedophile pedofile
kkk nazi hitler
""".split())

# Tier 2: matched only as the whole handle or as a separator-delimited token.
# These hide inside ordinary words - therapist, tycoon, spice, grape, analyst,
# cocktail, Sussex, arsenal - so substring matching would be unusable.
_BLOCK_TOKEN = frozenset("""
ass arse tit tits dick cock cum piss crap damn hell twat prick knob slut
sex porn anal penis vagina boob fag hoe retard
rape rapist molest coon spic gook kike paki nonce jihad isis heil
""".split())

# Ordinary words that happen to contain a tier-1 string.
_ALLOW = frozenset("""
shitake shiitake scunthorpe penistone clitheroe cockburn assassin assistant
classic
""".split())


def _collapse(s):
    """fuuuck -> fuck, without touching bass."""
    out, prev = [], None
    for ch in s:
        if ch != prev:
            out.append(ch)
        prev = ch
    return ''.join(out)


def _norm(s):
    return ''.join(ch for ch in s.lower().translate(_LEET) if ch.isalnum())


def is_clean_handle(handle):
    forms = {f for f in (_norm(handle),) if f}
    forms |= {_collapse(f) for f in forms}
    if forms & _ALLOW:
        return True

    for form in forms:
        if any(bad in form for bad in _BLOCK_ANY):
            return False

    # Separator-delimited tokens, plus the whole handle, for the ambiguous tier.
    tokens = {t for t in (_norm(p) for p in re.split(r'[_.\-]+', handle)) if t}
    tokens |= forms
    tokens |= {_collapse(t) for t in tokens}
    return not (tokens & _BLOCK_TOKEN)
UUID_RE = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')
DATE_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')

_cache = {'at': 0.0, 'body': None}
CACHE_TTL = 300


def _resp(code, body):
    return {
        'statusCode': code,
        'headers': {'content-type': 'application/json',
                    'cache-control': 'no-store'},
        'body': json.dumps(body),
    }


def _clean_days(raw):
    """Validate and clamp the submitted day map, newest KEEP_DAYS entries."""
    if not isinstance(raw, dict):
        return None
    out = {}
    for date, v in list(raw.items())[:100]:
        if not (isinstance(date, str) and DATE_RE.match(date) and isinstance(v, dict)):
            continue
        try:
            t, c, p = int(v.get('t', 0)), float(v.get('c', 0.0)), int(v.get('p', 0))
        except (TypeError, ValueError):
            continue
        if not (0 <= t <= MAX_TOKENS_DAY and 0 <= c <= MAX_COST_DAY and 0 <= p <= MAX_PROMPTS_DAY):
            continue
        out[date] = {'t': t, 'c': Decimal(str(round(c, 4))), 'p': p}
    if not out:
        return None
    return {d: out[d] for d in sorted(out)[-KEEP_DAYS:]}


def _report(payload):
    install_id = payload.get('install_id')
    if not (isinstance(install_id, str) and UUID_RE.match(install_id)):
        return _resp(400, {'error': 'install_id must be a lowercase uuid4'})

    days = _clean_days(payload.get('days'))
    if days is None:
        return _resp(400, {'error': 'days must hold at least one plausible day'})

    handle = payload.get('handle')
    if handle is not None:
        if not (isinstance(handle, str) and HANDLE_RE.match(handle)):
            return _resp(400, {'error': 'handle must be 2-24 chars of [A-Za-z0-9_.-]'})
        if not is_clean_handle(handle):
            return _resp(400, {'error': 'that handle is not allowed on the leaderboard'})

    item = {'install_id': install_id, 'days': days, 'updated_at': int(time.time())}
    if handle:
        item['handle'] = handle
    _table.put_item(Item=item)
    return _resp(200, {'ok': True, 'days_recorded': len(days)})


def _avg_of(days):
    """Mean daily tokens/cost/prompts over that install's trailing window."""
    recent = [days[d] for d in sorted(days)[-WINDOW_DAYS:]]
    if not recent:
        return None
    n = len(recent)
    return (sum(int(r['t']) for r in recent) / n,
            sum(float(r['c']) for r in recent) / n,
            sum(int(r['p']) for r in recent) / n)


def _collect():
    """Scan every install and reduce to community averages + leaderboard."""
    rows, kwargs = [], {'ProjectionExpression': 'install_id, handle, #d',
                        'ExpressionAttributeNames': {'#d': 'days'}}
    while True:
        page = _table.scan(**kwargs)
        rows.extend(page.get('Items', []))
        if 'LastEvaluatedKey' not in page or len(rows) > 50_000:
            break
        kwargs['ExclusiveStartKey'] = page['LastEvaluatedKey']

    per_install = []
    for row in rows:
        avg = _avg_of(row.get('days') or {})
        if avg:
            per_install.append((row['install_id'], row.get('handle'), avg))

    if not per_install:
        return {'installs': 0, 'avg_tokens_day': 0, 'avg_cost_day': 0.0,
                'avg_prompts_day': 0.0, 'leaderboard': []}

    n = len(per_install)
    ranked = sorted(per_install, key=lambda r: -r[2][0])
    return {
        'installs': n,
        'avg_tokens_day': round(sum(r[2][0] for r in per_install) / n),
        'avg_cost_day': round(sum(r[2][1] for r in per_install) / n, 4),
        'avg_prompts_day': round(sum(r[2][2] for r in per_install) / n, 2),
        # Ranks are computed over everyone; only handled installs are listed.
        '_ranked_ids': [r[0] for r in ranked],
        'leaderboard': [
            {'rank': i + 1, 'handle': h, 'tokens_day': round(a[0]),
             'cost_day': round(a[1], 2), 'prompts_day': round(a[2], 1)}
            for i, (_, h, a) in enumerate(ranked) if h
        ][:LEADERBOARD_SIZE],
    }


def _stats(install_id):
    now = time.time()
    if _cache['body'] is None or now - _cache['at'] > CACHE_TTL:
        _cache['body'], _cache['at'] = _collect(), now
    body = dict(_cache['body'])
    ranked = body.pop('_ranked_ids', [])
    body['your_rank'] = (ranked.index(install_id) + 1) if install_id in ranked else None
    body['latest_version'] = LATEST_VERSION
    return _resp(200, body)


def lambda_handler(event, context):
    ctx = (event.get('requestContext') or {}).get('http') or {}
    method = ctx.get('method', 'GET').upper()
    path = ctx.get('path', '/').rstrip('/') or '/'

    try:
        if method == 'POST' and path.endswith('/report'):
            raw = event.get('body') or '{}'
            if len(raw) > 64_000:
                return _resp(413, {'error': 'payload too large'})
            return _report(json.loads(raw))

        if method == 'GET' and path.endswith('/check-handle'):
            qs = event.get('queryStringParameters') or {}
            handle = qs.get('handle') or ''
            if not HANDLE_RE.match(handle):
                return _resp(200, {'ok': False,
                                   'reason': 'must be 2-24 chars of A-Z a-z 0-9 _ . -'})
            if not is_clean_handle(handle):
                return _resp(200, {'ok': False,
                                   'reason': 'that handle is not allowed on the leaderboard'})
            return _resp(200, {'ok': True})

        if method == 'GET' and (path.endswith('/stats') or path == '/'):
            qs = event.get('queryStringParameters') or {}
            return _stats(qs.get('install_id'))

        return _resp(404, {'error': 'use POST /report, GET /stats or GET /check-handle'})
    except json.JSONDecodeError:
        return _resp(400, {'error': 'body must be json'})
    except Exception as exc:                                  # noqa: BLE001
        print('error:', repr(exc))
        return _resp(500, {'error': 'internal error'})
