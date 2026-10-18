# Development localization patches — not release-approved

These eight patches preserve the current work without changing any release lock,
installer, update feed, or previously published source archive. They apply after
the exact original full_native.py preparation recorded in each JSON manifest.

Photo, Vector, Film, PDF, Word and CAD receive 1,491 additive catalog entries from
unanimous exact-context/source donors. Existing translations remain unchanged.
Deck and Sound receive initial six-language UI plumbing, device-local preferences,
OS detection, native font fallback, stable window identity and partial catalogs.
**Deck and Sound catalogs are incomplete. Do not publish them as complete.**

To inspect a candidate in a fresh checkout:

```sh
python scripts/full_native.py prepare --app deck
python scripts/check_localization_candidate.py --app deck
python scripts/audit_localization.py --app deck --require-complete --output dist/deck-localization.json
```

The final command currently fails intentionally on outstanding translation gaps.
The candidate checker validates input/output hashes and the exact allowed file
set. It does not update prepared.json, so ordinary release packaging continues to
reject the candidate tree. The separate native verification workflow has read-only
repository permission and never packages or publishes a release.

Local checks on macOS arm64: both GUI crates compile; Deck UI tests 50/50 pass;
Sound UI tests 110 pass, one catalog-completeness failure. Six Sound main-window
screenshots were generated; English text and toolbar overflow are still visible.
Those screenshots are evidence of unfinished work, not a screen-pass claim.

Translation data and scripts are in patches/localization-shared and scripts/.
The authored TSV has English, Vietnamese, Korean, Japanese, Traditional Chinese,
and Simplified Chinese columns; escaped newlines and placeholder names are kept.
No external translation service was used. Chinese catalogs are independent.
