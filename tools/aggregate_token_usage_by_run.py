#!/usr/bin/env python3
import re, json, sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1] / 'logs'
RECRUITER_LOG = BASE / 'recruiter_system.log'
TOKEN_LOG = BASE / 'token_usage.log'
OUT_JSON = BASE / 'token_usage_by_run.json'

if not RECRUITER_LOG.exists() or not TOKEN_LOG.exists():
    print('必要なログファイルが見つかりません。')
    print(RECRUITER_LOG, RECRUITER_LOG.exists())
    print(TOKEN_LOG, TOKEN_LOG.exists())
    sys.exit(1)

text = RECRUITER_LOG.read_text(encoding='utf-8')
# Split into run chunks by long separator lines (===...)
chunks = re.split(r"\n=+\n", text)

# Only keep chunks that contain at least one "レイヤー" or OpenAI line
run_chunks = []
for ch in chunks:
    if 'レイヤー①' in ch or '修正依頼処理 開始' in ch or 'OpenAI API呼び出し成功' in ch:
        run_chunks.append(ch)

# For each chunk, count successful OpenAI calls
success_pattern = re.compile(r'OpenAI API呼び出し成功')
# extract first timestamp in chunk
ts_pattern = re.compile(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3})")

runs = []
for ch in run_chunks:
    success_count = len(success_pattern.findall(ch))
    ts_match = ts_pattern.search(ch)
    ts = ts_match.group(1) if ts_match else None
    runs.append({'timestamp': ts, 'success_count': success_count, 'chunk_head': ch[:200]})

# Read token log lines
token_lines = [l.strip() for l in TOKEN_LOG.read_text(encoding='utf-8').strip().splitlines() if l.strip()]
tokens = [json.loads(l) for l in token_lines]

# Assign token entries to runs sequentially based on success_count
assignments = []
idx = 0
for i, r in enumerate(runs):
    n = r['success_count']
    if n <= 0:
        continue
    assigned = tokens[idx: idx + n]
    idx += n
    total_tokens = sum(t.get('total_tokens', 0) for t in assigned)
    prompt_tokens = sum(t.get('prompt_tokens', 0) for t in assigned)
    completion_tokens = sum(t.get('completion_tokens', 0) for t in assigned)
    per_call = [t.get('total_tokens', 0) for t in assigned]
    assignments.append({
        'run_index': i+1,
        'timestamp': r['timestamp'],
        'success_count': n,
        'total_tokens': total_tokens,
        'prompt_tokens': prompt_tokens,
        'completion_tokens': completion_tokens,
        'per_call_tokens': per_call
    })

# If token lines remain unassigned, add them to a trailing 'unassigned' group
if idx < len(tokens):
    remaining = tokens[idx:]
    assignments.append({
        'run_index': len(assignments)+1,
        'timestamp': None,
        'success_count': len(remaining),
        'total_tokens': sum(t.get('total_tokens',0) for t in remaining),
        'prompt_tokens': sum(t.get('prompt_tokens',0) for t in remaining),
        'completion_tokens': sum(t.get('completion_tokens',0) for t in remaining),
        'per_call_tokens': [t.get('total_tokens',0) for t in remaining],
        'note': 'remaining_unassigned'
    })

OUT_JSON.write_text(json.dumps(assignments, ensure_ascii=False, indent=2), encoding='utf-8')

# Print concise summary
print(f"Total token lines: {len(tokens)}")
for a in assignments:
    print('---')
    print(f"Run #{a['run_index']}  timestamp={a['timestamp']}  calls={a['success_count']}  total_tokens={a['total_tokens']}  avg_per_call={a['total_tokens']/a['success_count'] if a['success_count']>0 else 0:.1f}")

print('\n詳細は logs/token_usage_by_run.json を参照してください')
