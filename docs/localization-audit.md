# Six-language native application verification

The required order is `vi`, `en`, `ko`, `ja`, `zh-TW`, `zh-CN`. Native package
availability and complete localization are separate properties. A successful
installer/engine build must never be described as complete six-language GUI QA.

Run with Python 3.11+ after preparing the actual sources:

```sh
python3 scripts/audit_localization.py --output qa/localization.json
python3 scripts/audit_localization.py --app launcher --require-complete --output qa/launcher-localization.json
python3 -m unittest discover -s tests -p test_localization_audit.py -v
```

The audit reads the real TSV, JSON, TOML and applicable Rust catalogs. It records
missing languages/keys, empty values, duplicates, mismatched placeholder counts,
untranslated English for review, and direct UI literals for contextual review.
Command IDs, paths, extensions, URLs, user document text and official product
names must remain unchanged. Only explicit, per-application official-name
exceptions suppress an untranslated-English finding. Traditional and Simplified
Chinese always remain independent catalogs.

Counts use the union of existing catalog keys plus literal translation calls.
This is an actionable static inventory; dynamic labels and direct widget calls
need source review and actual screen checks. A zero-key application is not
localized: Sound and Deck have no translation infrastructure in the pinned
workspaces and contain direct English UI strings. The audit must not give those
applications a false green result.

On 2026-10-18 all 14 public native applications had both operating-system
packages and matching source releases. The static audit found incomplete
six-language localization in every pinned editor; publishing their existing
installers did not establish localization completeness.

Launcher revision `0.4.1-kio.2` adds 308 matching keys for each required language,
including Vietnamese, Korean, Taiwan Traditional Chinese, tray text, messages,
plural forms and font recovery instructions. The original native locale API,
automatic preference, device settings, downloads, checksum validation and KIO
bundle identity are retained. Chinese region/script normalization now selects
Traditional Chinese for Taiwan, Hong Kong, Macau and Hant. Native font selection
uses installed regional Chinese/Korean fonts without redistributing them.
The selected language appears first; the other five retain the required order.

`scripts/launcher_six_languages.py` reproduces the authored additions from a
fixed key inventory. The six-language audit is a blocking native CI step for this
revision. Original full native core/backend/UI tests still run. Completion of a
source/catalog check alone must not claim native compilation, installation,
all-screen layout inspection, signing/notarization, or real account login.

KIO Tools is maintained in its own Python/C++/WebView repository. Studio remains
in its existing private owner-only distribution; never add its private installer,
source or credentials to this public repository or the public Launcher feed.

## Existing editor debt and regression gate

`manifests/localization-baseline.json` records the known findings from the first
suite-wide audit. The full native editor workflow runs `--baseline` after source
preparation. Any newly missing translation, broken variable, empty value,
untranslated English entry or direct UI literal fails that check. Moving a UI
line does not bypass or falsely trigger the check. This prevents new features
from adding localization debt while keeping the existing debt visible.

Passing this regression gate is **not** passing `--require-complete`. The latter
remains mandatory for Launcher, whose six required catalogs are complete. The
other editors must not be labelled fully localized until their existing findings
are resolved and their native screens are tested. Do not refresh the baseline to
hide new findings; proposed exceptions require source/context review.

## Development candidates (2026-10-18)

The additive candidates are reproducible, hash-pinned patches in
`patches/localization-candidates`. They do not modify the published source locks.
Deck has 1,049 keys and Sound has 1,560 keys in all six required languages. Both
pass `--require-complete` for the current static inventory; the other eleven
editors still have unresolved findings. A runtime metadata test in Sound also
checks built-in plugin parameters, choice labels, automation modes and note
values, because catalogs alone previously missed those dynamic labels.

The auditor recognizes source-keyed format contexts without inventing a duplicate
plain key. It ignores punctuation-only icons and does not confuse a parameter
after a zero-argument `.label()` call with interface text. Actual formatted prose,
dropdown selected values and links remain blocking findings.

Keyed compound Sound messages preserve user names and braces verbatim. Recovery
durations use language-specific complete phrases rather than English plural
suffixes. The automatic language choice can be restored from the same globe menu.
Built-in plugin captions are translated at their presentation boundary; hosted
plugin names, bus names and session data remain verbatim.

These candidates are development source, not new production installers. Static
coverage, native compilation, interactive screen review, audio hardware, signed
installation and real account authentication are distinct verification scopes.
