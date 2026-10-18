# Development localization patches — not release-approved

These nine patches preserve the current work without changing any release lock,
installer, update feed, or previously published source archive. They apply after
the exact original full_native.py preparation recorded in each JSON manifest.

Photo, Vector, Film, PDF, Word and CAD receive 1,491 additive catalog entries from
unanimous exact-context/source donors. Existing translations remain unchanged.
Deck and Sound receive six-language UI plumbing, device-local preferences,
OS detection, native font fallback and stable window identity. Deck now has 1,050
catalog keys in all six languages, including presentation-specific editorial
translations and repaired dynamic menus, accessible labels and font notices.
Sound now has 1,560 keys in each of the six languages, including the actual
model/DSP presentation metadata, recovery and device-failure messages. Keyed
compound messages preserve filenames and nested arguments; language changes
retain the session. **No candidate is release-approved.**

Grid now has Vietnamese and independent Traditional Chinese choices, primary
choice ordering, device-local explicit/automatic preferences, native OS detection,
Traditional Chinese font priority and opaque keyed messages. Its 1,644 reviewed
source rows supplement original translations and conservative exact donors.
The 1,795-key static catalog now matches across all six languages, including all
runtime function descriptions. Grid remains incomplete: an additional engine
diagnostic audit found 345 templates, 340 needing translation or safe dynamic
routing. The separate runtime diagnostic gate must keep the job failing until
that work is completed. Static key parity does not certify every runtime screen.

To inspect a candidate in a fresh checkout:

```sh
python scripts/full_native.py prepare --app deck
python scripts/check_localization_candidate.py --app deck
python scripts/audit_localization.py --app deck --require-complete --output dist/deck-localization.json
```

The final command passes the current static inventory for Deck, Sound and Grid. It
does not certify every rendered screen or the remaining eleven editors.
The candidate checker validates input/output hashes and the exact allowed file
set. It does not update prepared.json, so ordinary release packaging continues to
reject the candidate tree. The separate native verification workflow has read-only
repository permission and never packages installers, changes the store, or publishes
a release. It builds the actual GUI and CLI executables as well as running tests.
Only jobs passing the strict catalog gate retain development executables as
clearly labeled, temporary Actions artifacts; these are not signed installers.

Local checks on macOS arm64: both GUI crates compile. Deck's 1,049-key candidate
passed 53/53 UI tests and Sound's 1,560-key candidate passed 120/120 UI tests,
with strict catalogs on both macOS and Windows in run 39149891494 (efa4fe0).
Sound follow-up 626da95 passed 121/121 and the strict catalog gate on both OSes
in run 39151404094. It fixes nested engine-status fragments, plugin window
captions and the reserved factory-preset label. Run 39159705763 (66be91c) built the actual GUI and CLI on both OSes; Deck
passed 53/53, Sound 121/121 and the older Grid 100/100 on Mac, 99/99 on Windows.
Grid correctly failed the then-incomplete catalog gate. The current Grid follow-up
requires its own matching CI results. It passes 104 UI tests locally, including
six-language runtime metadata, painted form captions, workbook/undo/input
preservation and preference migration; that does not imply a complete catalog. These counts refer to exact source revisions.
Actual window inspection found untranslated model modes and status fragments;
these were subsequently repaired. Deck's Vietnamese status counter and translated
gallery captions were repaired using actual glyph widths. Native screenshots
remain review evidence rather than a blanket full-GUI pass, and audio hardware,
installation and real-login tests remain separately recorded.

Translation data and scripts are in patches/localization-shared and scripts/.
The authored TSV has English, Vietnamese, Korean, Japanese, Traditional Chinese,
and Simplified Chinese columns; escaped newlines and placeholder names are kept.
No external translation service was used. Chinese catalogs are independent.
