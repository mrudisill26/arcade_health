# POC catalog snapshot

Frozen **merged catalog CSV** for offline use / handoff without live Google Sheet or GitLab pulls.

| File | Description |
|---|---|
| `merged_live_and_ie_published.csv` | Handoff-schema catalog (live PAList + IE Published RM) |
| `stats.json` | Row counts and source breakdown |

Consuming apps should treat this file the same as `data/merged_live_and_ie_published.csv`.

Full column list, join rules, and pull instructions: **[Handoff contract](../README.md#handoff-contract)** in the main README.

> After changing `RM_COLUMNS` or join logic, refresh from a fresh live merge so the snapshot matches production schema.

## Refresh

```bash
cp data/merged_live_and_ie_published.csv poc/
python3 -c "
import csv, json
from collections import Counter
from pathlib import Path

rows = list(csv.DictReader(Path('poc/merged_live_and_ie_published.csv').open()))
stats = {
    'row_count': len(rows),
    'sources': dict(Counter(r['source'] for r in rows)),
    'with_detail_page': sum(1 for r in rows if (r.get('DetailPage') or '').strip()),
    'rm_column_count': sum(1 for c in rows[0] if c.startswith('rm_')),
    'has_gemini_description': sum(
        1 for r in rows if (r.get('rm_Demo_Description_(Gemini_generated)') or '').strip()
    ),
}
Path('poc/stats.json').write_text(json.dumps(stats, indent=2) + '\n')
print(json.dumps(stats, indent=2))
"
```
