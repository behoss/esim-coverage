# Travel eSIM coverage by country

**Which mobile networks does a travel eSIM use in each country, and do you get 4G or 5G?** This is the open dataset that answers it, country by country, in CSV and JSON.

<!-- stats -->205 countries and territories, 237 mobile networks, 439 country-network rows. Last updated: 2026-11-20.<!-- /stats -->

**Search it in your browser:** [behoss.github.io/esim-coverage](https://behoss.github.io/esim-coverage/)

> Travelling soon? **[eSIMology](https://esimology.com)** has travel eSIMs for 200+ countries from £3.99, delivered by email in a minute. Popular picks: [Japan eSIM](https://esimology.com/esim/japan), [USA eSIM](https://esimology.com/esim/united-states), [Turkey eSIM](https://esimology.com/esim/turkey), [Thailand eSIM](https://esimology.com/esim/thailand) and [all destinations](https://esimology.com/esim).

## Sample

```json
{
  "iso2": "JP",
  "country": "Japan",
  "best_network": "5G",
  "operators": [
    {
      "name": "KDDI/au",
      "network_types": ["5G"]
    },
    {
      "name": "NTT docomo",
      "network_types": ["5G"]
    },
    {
      "name": "Rakuten Mobile",
      "network_types": ["5G"]
    },
    {
      "name": "SoftBank",
      "network_types": ["5G"]
    }
  ],
  "esim_url": "https://esimology.com/esim/japan",
  "regional_plans": [
    {
      "name": "Asia",
      "url": "https://esimology.com/esim/asia"
    }
  ]
}
```

## Files

| File | What it holds |
|---|---|
| [`data/coverage.json`](data/coverage.json) | One object per country: operators with their network types, the fastest network, the country's eSIM page and the regional plans that also cover it |
| [`data/coverage.csv`](data/coverage.csv) | One row per country and network, for spreadsheets |
| [`schema/coverage.schema.json`](schema/coverage.schema.json) | JSON Schema (draft 2020-12) for `coverage.json` |
| [`scripts/build.py`](scripts/build.py) | Rebuilds and validates everything from the live catalogue |

## Columns (CSV)

| Column | Example | Meaning |
|---|---|---|
| `iso2` | `JP` | ISO 3166-1 alpha-2 country code |
| `country` | `Japan` | Country or territory name in English |
| `operator` | `NTT docomo` | Mobile network the eSIM connects to |
| `network_types` | `4G/5G` | Network types listed for that operator |
| `best_network` | `5G` | Fastest network type in the country |
| `esim_url` | `https://esimology.com/esim/japan` | Travel eSIM page for the country (blank where only regional plans cover it) |

## Use it

```python
import json, urllib.request
url = "https://behoss.github.io/esim-coverage/coverage.json"
data = json.load(urllib.request.urlopen(url))
jp = next(c for c in data["countries"] if c["iso2"] == "JP")
print(jp["best_network"], [o["name"] for o in jp["operators"]])
```

## Rebuild and validate

Needs [uv](https://docs.astral.sh/uv/) and Python 3.12.

```sh
uv run scripts/build.py          # fetch the live catalogue and rebuild data/, docs/ and the stats above
uv run scripts/build.py --check  # validate the committed files (what CI runs on every push)
```

## Licence

- **Data** (`data/`, `docs/*.json`, `docs/*.csv`): [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Credit: "eSIM coverage data by Bez, [eSIMology](https://esimology.com)".
- **Code**: [MIT](LICENSE).

Made by [Bez](https://behoss.github.io). Coverage comes from the live travel eSIM catalogue at [eSIMology](https://esimology.com).
