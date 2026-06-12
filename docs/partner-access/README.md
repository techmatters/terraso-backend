# Partner soil-ID access

How to call the Terraso soil-ID API as a partner, with runnable Python and
shell examples.

## How it works

Terraso soil-ID is an **HTTPS GraphQL API**, so you can call it from any
language — the examples in this directory (Python and shell) are just one way.

**Authentication.** The Terraso team supplies you with a long-lived *refresh
token*. You don't send that token on every request; instead you exchange it for
a short-lived *access token*, then send the access token as a
`Bearer` credential on each API call. When the access token expires, you
exchange the refresh token again for a new one. (The example scripts do this
automatically and cache the access token for reuse.)

**Making a request.** You send a GraphQL `soilMatches` query with, at minimum, a
**latitude and longitude**. You may optionally include **soil data** — slope,
surface cracks, and, per depth interval, texture, rock-fragment volume, and
color. The response is a ranked set of soil matches with a variety of
information about each. **The more soil data you supply, the more accurate the
match.**

## Files

| File | Role |
| --- | --- |
| `soil_id_query_params.json` | The lookup input (latitude/longitude + optional soil `data`). Edit this to change the query. |
| `soil_id_query.py` | Python example (standard library only). |
| `soil_id_query.sh` | Shell example (requires `curl` + `jq`). Same behavior as the Python script. |

Both scripts are equivalent — they run the query, automatically exchange your
refresh token for an access token when needed, cache that access token, and
print the result to stdout. Use whichever you prefer, or treat them as a
reference for your own implementation. By default they talk to
`https://api.terraso.org`.

## Setup

Put the refresh token you were supplied into a tokens file, kept outside this
repository:

```sh
mkdir -p ~/secrets/terraso
cat > ~/secrets/terraso/tokens.json <<'EOF'
{ "refresh_token": "<your-partner-refresh-token>" }
EOF
chmod 600 ~/secrets/terraso/tokens.json
```

The scripts read the refresh token from this file and write the access token
back into it as `access_token`, so subsequent runs reuse it until it expires.

## Run

The response is printed to **stdout**; status/progress messages go to **stderr**,
so the output stays clean for piping or redirecting:

```sh
python3 soil_id_query.py | jq             # or: ./soil_id_query.sh | jq
python3 soil_id_query.py > response.json  # save the response to a file
```

Each run:

1. Reads the cached `access_token` from the tokens file and POSTs the
   `soilMatches` query (requesting every available field) to `/graphql/`.
2. If the call is rejected because the access token is missing or expired, it
   exchanges the `refresh_token` at `/auth/tokens` for a fresh access token,
   **writes that token back to the tokens file**, and retries once.
3. Prints the response to stdout (status messages to stderr).

## Request fields

`soil_id_query_params.json` holds the variables for the query. Only `latitude` and
`longitude` are required; everything else is optional, and the more you supply
the more accurate the match. These are the only inputs the soil-ID algorithm
accepts — there are no other fields.

```json
{
  "latitude": -0.85497,
  "longitude": 36.84891,
  "data": {
    "slope": 0.5,
    "surfaceCracks": "NO_CRACKING",
    "depthDependentData": [
      {
        "depthInterval": { "start": 0, "end": 10 },
        "texture": "CLAY",
        "rockFragmentVolume": "VOLUME_0_1",
        "colorLAB": { "L": 20, "A": 30, "B": 40 }
      },
      {
        "depthInterval": { "start": 10, "end": 30 },
        "texture": "SANDY_LOAM",
        "rockFragmentVolume": "VOLUME_1_15",
        "colorMunsell": "7.5YR 5/4"
      },
      {
        "depthInterval": { "start": 30, "end": 50 },
        "texture": "CLAY_LOAM",
        "rockFragmentVolume": "VOLUME_15_35",
        "colorMunsellNumeric": { "hue": 20, "value": 4, "chroma": 3 }
      }
    ]
  }
}
```

The three depths above each use a different color form (CIELAB, Munsell string,
numeric Munsell) to illustrate the options — use whichever you have.

| Field | Required | Notes |
| --- | --- | --- |
| `latitude`, `longitude` | yes | Decimal degrees (WGS84). A location-only lookup with no `data` is valid. |
| `data.slope` | no | Slope, in percent. |
| `data.surfaceCracks` | no | Enum (see below). |
| `data.depthDependentData` | no | A list — one object per depth interval; add as many as you have. |

Each object in `data.depthDependentData`:

| Field | Required | Notes |
| --- | --- | --- |
| `depthInterval` | yes | `{ "start": <cm>, "end": <cm> }`. |
| `texture` | no | Enum (see below). |
| `rockFragmentVolume` | no | Enum (see below). |
| `colorLAB` | no | CIELAB color `{ "L": <float>, "A": <float>, "B": <float> }` — all three required if present. |
| `colorMunsell` | no | Munsell color as a string, e.g. `"7.5YR 5/4"` or `"N 5/"` (neutral). |
| `colorMunsellNumeric` | no | Munsell color as numbers: `{ "hue": <0–100>, "value": <float>, "chroma": <float> }`. |

**Color.** Provide it in whichever form you have. If you supply more than one,
they are used in this order: `colorLAB`, then `colorMunsell`, then
`colorMunsellNumeric`. A Munsell value that can't be converted to a known color
is ignored — that depth is treated as having no color (the request still
succeeds). **Most callers should use the `colorMunsell` string form** (e.g.
`"7.5YR 5/4"`); the numeric form below exists mainly for data already stored
that way.

**Numeric Munsell hue (`colorMunsellNumeric.hue`).** Only relevant if you use
the numeric form. The hue is a single number on a 0–100 scale: the ten Munsell
hue families in order, ten units each. Compute it as `family_index × 10 +
substep`, where `substep` is the number written before the family letters
(`2.5`, `5`, `7.5`, or `10`):

| Family | R | YR | Y | GY | G | BG | B | PB | P | RP |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Index | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 |

Examples: `7.5YR → 1×10 + 7.5 = 17.5`; `10R → 0×10 + 10 = 10`;
`2.5Y → 2×10 + 2.5 = 22.5`; `10YR → 1×10 + 10 = 20`. For a neutral color, use the
string form (`"N 5/"`) or set `chroma` to `0`.

**Enum values**

- `surfaceCracks`: `NO_CRACKING`, `SURFACE_CRACKING_ONLY`, `DEEP_VERTICAL_CRACKS`.
- `texture`: `SAND`, `LOAMY_SAND`, `SANDY_LOAM`, `SILT_LOAM`, `SILT`, `LOAM`,
  `SANDY_CLAY_LOAM`, `SILTY_CLAY_LOAM`, `CLAY_LOAM`, `SANDY_CLAY`, `SILTY_CLAY`,
  `CLAY`.
- `rockFragmentVolume`: `VOLUME_0_1` (0–1%), `VOLUME_1_15` (1–15%),
  `VOLUME_15_35` (15–35%), `VOLUME_35_60` (35–60%), `VOLUME_60` (>60%).

## Notes

- **Keep tokens secret.** Treat both the refresh token and the access token as
  credentials: don't print or log them, don't commit them, and don't paste them
  into the JSON files in this directory. These examples keep them only in the
  tokens file (written `chmod 600`) and in memory — do the same in your own
  code.
- **Refresh-token rotation.** `/auth/tokens` returns a new `refresh_token`
  alongside the `access_token`. Keep using your *original* long-lived refresh
  token; the examples deliberately preserve it rather than the rotated one.
- **Configuration.** `TERRASO_API_BASE_URL` (default `https://api.terraso.org`)
  is the only setting; the tokens-file path is fixed at
  `~/secrets/terraso/tokens.json`.
- **Result shape.** `soilMatches` returns either `SoilMatches` (with
  `dataRegion` and a ranked list of `matches`) or `SoilIdFailure` (with a
  `reason` such as `DATA_UNAVAILABLE`). Each match's `soilInfo.soilSeries`
  carries the soil `name` and `description`, plus `management` guidance on
  global (non-US) matches; locations in the US also populate the US-only fields
  (`slope`, `ecologicalSite`, `landCapabilityClass`).
- **Inspecting a token (optional).** Purely for debugging or curiosity, you can
  paste a token into <https://jwt.io> to see its decoded contents — there's no
  need to do this for normal use. Hovering over the `exp` field shows when that
  token expires. (jwt.io decodes in your browser, but it's still a third-party
  site, so avoid pasting a token you consider sensitive.)
