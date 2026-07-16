# POC data snapshot

This folder contains a **frozen catalog export** for demonstrating the advisor without running live pulls.

| File | Description |
|---|---|
| `merged_live_and_ie_published.csv` | Merged catalog (live PAList + IE Published Request Master) |
| `stats.json` | Row counts and source breakdown |

For what columns are collected, how joins work, and how to refresh from Google Sheets / GitLab, see **[Data collection](../README.md#data-collection)** in the main README.

> After changing `RM_COLUMNS` or join logic, refresh this snapshot from a fresh `data/merged_live_and_ie_published.csv` so the POC matches the live schema.

## Refresh the snapshot

After updating live data:

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
}
Path('poc/stats.json').write_text(json.dumps(stats, indent=2))
print(json.dumps(stats, indent=2))
"
```
