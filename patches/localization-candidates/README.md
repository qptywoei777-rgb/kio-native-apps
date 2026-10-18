# Development localization patches — not release-approved

These eight patches preserve the current work without changing any release lock,
installer, update feed, or previously published source archive. They apply after
the exact original full_native.py preparation recorded in each JSON manifest.

Photo, Vector, Film, PDF, Word and CAD receive 1,491 additive catalog entries from
unanimous exact-context/source donors. Existing translations remain unchanged.
Deck and Sound receive six-language UI plumbing, device-local preferences,
OS detection, native font fallback and stable window identity. Deck now has 1,047
catalog keys in all six languages, including presentation-specific editorial
translations and repaired dynamic menus, accessible labels and font notices.
Sound now has 1,508 keys in each of the six languages, including the actual
model/DSP presentation metadata, recovery and device-failure messages. Keyed
compound messages preserve filenames and nested arguments; language changes
retain the session. **Neither candidate is release-approved.**

To inspect a candidate in a fresh checkout:

```sh
python scripts/full_native.py prepare --app deck
python scripts/check_localization_candidate.py --app deck
python scripts/audit_localization.py --app deck --require-complete --output dist/deck-localization.json
```

The final command passes the current static inventory for Deck and Sound. It
does not certify every rendered screen or the remaining eleven editors.
The candidate checker validates input/output hashes and the exact allowed file
set. It does not update prepared.json, so ordinary release packaging continues to
reject the candidate tree. The separate native verification workflow has read-only
repository permission and never packages or publishes a release.

Local checks on macOS arm64: both GUI crates compile; Deck UI tests 53/53 and
Sound UI tests 118/118 pass. Deck's current candidate passed 53/53 and the strict
catalog gate on both macOS and Windows in run 39142452059. Sound's revised
candidate requires its own Windows run. The earlier Sound run failed correctly
for its then-missing catalog entries; it is not evidence against or for this
new source. Actual Sound window inspection found untranslated docking tabs,
model modes, note units and status fragments; these were subsequently repaired.
Deck's Vietnamese status counter and translated gallery captions were repaired
using actual glyph widths. Native screenshots remain review evidence rather
than a blanket full-GUI pass, and audio hardware/installation/real-login tests
remain separately recorded.

Translation data and scripts are in patches/localization-shared and scripts/.
The authored TSV has English, Vietnamese, Korean, Japanese, Traditional Chinese,
and Simplified Chinese columns; escaped newlines and placeholder names are kept.
No external translation service was used. Chinese catalogs are independent.
