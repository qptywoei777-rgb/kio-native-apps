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
Sound catalogs remain incomplete. **Neither candidate is release-approved.**

To inspect a candidate in a fresh checkout:

```sh
python scripts/full_native.py prepare --app deck
python scripts/check_localization_candidate.py --app deck
python scripts/audit_localization.py --app deck --require-complete --output dist/deck-localization.json
```

The final command passes Deck's current static inventory and fails Sound's
outstanding translation gaps. It does not certify every rendered screen.
The candidate checker validates input/output hashes and the exact allowed file
set. It does not update prepared.json, so ordinary release packaging continues to
reject the candidate tree. The separate native verification workflow has read-only
repository permission and never packages or publishes a release.

Local checks on macOS arm64: both GUI crates compile; updated Deck UI tests 52/52
pass; Sound UI tests 110 pass, one catalog-completeness failure. The preceding
candidate passed Deck 50/50 on Windows and macOS; updated Windows CI is separate.
Sound screenshots still show English text, and its horizontally scrollable toolbar
needs further inspection. Deck native screen capture exposed an overlapping
Vietnamese status counter, now laid out from actual glyph widths. Screenshots
remain review evidence rather than a blanket full-GUI pass.

Translation data and scripts are in patches/localization-shared and scripts/.
The authored TSV has English, Vietnamese, Korean, Japanese, Traditional Chinese,
and Simplified Chinese columns; escaped newlines and placeholder names are kept.
No external translation service was used. Chinese catalogs are independent.
