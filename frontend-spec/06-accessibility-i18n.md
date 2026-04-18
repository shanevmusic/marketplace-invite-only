# Frontend Spec — 06 Accessibility & Internationalization

**Audience:** Frontend Engineer. Phase 8 is the baseline — the rules here must be true from the first screen shipped so we don't have to retrofit later.

---

## 1. Accessibility — Phase 8 baseline (non-negotiable)

### 1.1 Contrast — WCAG 2.1 AA

- All text vs its background: **≥ 4.5:1** for body text (`bodyMedium` and below), **≥ 3:1** for large text (`titleMedium` and above at 16 sp 700 weight, or 18 sp any weight).
- All interactive icons and focus indicators vs background: **≥ 3:1**.
- The design tokens in `01-design-tokens.md` are pre-checked for light and dark themes. New colors added after Phase 8 must be verified before merge (recommended CLI: `dart run axe_accessibility_checker` or manual check via the design tokens page in `flutter_storybook`).

### 1.2 Dynamic Type

- Never set a hard-coded `fontSize` outside `lightTheme()` / `darkTheme()` builders.
- Every screen must render cleanly at system text scale up to **200%** without text clipping or overflow on a 360×640 dp canvas.
- Buttons and list tiles grow vertically to accommodate scaled text — no fixed heights that clip. Use `min` heights, not `max`.
- At extreme scale (≥ 175%), the signup form scrolls rather than compressing; label-above-input wrapping is preserved.

### 1.3 Touch targets

- **Minimum interactive area: 44 × 44 dp** (iOS HIG and Android a11y guidance). Apply via `InkWell` wrapping with a padded hit region when the visual is smaller (e.g. a 20dp icon button renders inside a 44dp tap target).
- Adjacent interactive targets must have **≥ 8 dp** of separation — no fat-finger overlap.
- `AppButton.sm` is 36 dp tall *visually* but wraps in a 44 dp tap target internally.

### 1.4 Semantic labels

- Every interactive element has an accessible name:
  - `AppTextField`: the `label` prop IS the accessible name. Helper text is exposed as hint.
  - `AppButton`: the `label` prop. If the button is icon-only (Phase 9+), `semanticsLabel` is required (lint-enforced: custom `very_good_analysis` rule or a PR-checklist item).
  - `AppListTile`: `title` is the label; `subtitle` is appended in the semantics tree only if short; if long, it's readable on focus.
  - `AppAvatar` (interactive variant only): `semanticsLabel: "<name>, <role>"`.
  - `RoleBadge`: `excludeSemantics` when adjacent to a name (the name label already includes the role); standalone badges render their role as label.
- **Non-interactive decorative elements** (shimmer, dividers, brand mark on splash) use `ExcludeSemantics` so screen readers don't over-announce.
- Error text, when it appears, is wrapped in `Semantics(liveRegion: true, ...)` so VoiceOver / TalkBack announces it without the user re-focusing.
- `SemanticsService.announce("Your session expired", TextDirection.ltr)` on the one-shot toast after forced logout.

### 1.5 Focus & keyboard (web build futureproofing)

- All interactive widgets support keyboard focus (`Focus` / `FocusableActionDetector`).
- Focused elements display a **2 dp outline in `colorScheme.primary` with 2 dp offset** (token `elev0`, radius = widget's radius).
- Tab order on forms follows visual order; submit via Enter from the last field; Escape dismisses dialogs / bottom sheets.
- Not strictly required for Phase 8 mobile-only, but building it in now costs almost nothing and protects the web build path.

### 1.6 Motion & reduced motion

- Detect `MediaQuery.disableAnimations`. When true:
  - Collapse all `AppMotion` durations to 0.
  - Skeleton shimmer stops; show static placeholder color.
  - Page transitions become instant swaps.
- Never use flashing, parallax, or looping-animation decorations that can't be disabled.

### 1.7 Color independence

- No status is communicated by color alone. Success, error, warning each have:
  - A **color** (from tokens).
  - An **icon** (check, info, warning).
  - **Text** stating the state.
- Role badges pair color with a text label; the color carries no state information a screen-reader user would miss.

### 1.8 Form accessibility specifics

- Required fields: visible `*` **and** programmatic `Semantics(textField: true, ...)` with a hint that includes "required".
- Password strength indicator has a text companion ("Weak / Good / Strong") not just the colored bar.
- Radio group in signup role-choice: uses `Semantics.inMutuallyExclusiveGroup: true` on the wrapper, `Semantics.checked` on each option.
- Validation errors focus-shift to the first invalid field on submit and announce.

### 1.9 Testing

- Phase 8 tests include one `semantics` widget test per auth screen (Splash, Login, Signup, InviteLanding, Offline) asserting presence of expected labels.
- Manual smoke test checklist (lives in `docs/phase-8-notes.md` when the engineer writes it): run each auth flow with VoiceOver on iOS simulator and TalkBack on an Android emulator.

---

## 2. Internationalization — Phase 8 scaffold

Phase 8 ships **English only (en-US)** but the scaffolding is built so Phases 10–14 can add locales without refactoring.

### 2.1 Approach: Flutter `intl` + ARB files

- Use Flutter's built-in `flutter_localizations` + `intl` + generated `AppLocalizations` via `flutter_gen`.
- Config lives in `pubspec.yaml` under `flutter: generate: true` with an `l10n.yaml` at repo root:
  ```yaml
  arb-dir: lib/l10n/arb
  template-arb-file: app_en.arb
  output-localization-file: app_localizations.dart
  synthetic-package: false
  output-dir: lib/l10n/gen
  ```
- English strings live in `lib/l10n/arb/app_en.arb`. New locales add `app_es.arb`, `app_ar.arb`, etc.
- The generated `AppLocalizations.of(context)` is accessed via an extension `context.l10n`.

### 2.2 String externalization rules

- **No hard-coded user-facing string** in a widget. If the engineer types a literal, CI lint (`flutter analyze` + a custom `must_be_externalized` rule or a pre-commit grep for `Text\\(\"[A-Za-z]`) flags it.
- Exception: developer-only debug text behind `if (kDebugMode)` guards — still discouraged.
- Pluralization uses ICU MessageFormat (`{count, plural, =0{No orders} =1{1 order} other{# orders}}`).
- Date/number formatting via `intl` `DateFormat` and `NumberFormat`, passing `Localizations.localeOf(context)`.
- Currency per ADR-0005 (single platform currency, minor units): a single `AppCurrency.format(minorUnits, locale)` helper wraps `NumberFormat.currency`.

### 2.3 Locales planned

| Phase | Locales |
|---|---|
| 8 | en-US only |
| 10 | en-US, es-ES (Spanish translation scaffolded) |
| 14 | en-US, es-ES, ar-SA (RTL introduced) |

### 2.4 Right-to-left readiness (scaffold only in Phase 8)

- Use `Directionality`-aware widgets: `EdgeInsetsDirectional`, `AlignmentDirectional`, `PaddingDirectional`. **Never** use `EdgeInsets.only(left: ...)` — always `.start` / `.end`.
- Icons with handedness (back arrow, chevron) use `Icons.arrow_back` (which Flutter auto-mirrors) or the `_ios` variants with manual `Directionality` flip via `Transform`.
- Layout mixins (`Row` with text): don't assume LTR — test the signup screen in RTL once before Phase 14 lands.
- Phase 8 does not ship Arabic strings but the layout work should survive a `Directionality.rtl` wrapper test.

### 2.5 Accessibility × i18n overlap

- Screen-reader announcements respect locale: `SemanticsService.announce` takes a `TextDirection` — always pass `Directionality.of(context)`.
- Error messages are localized via the same `context.l10n` keys — never string-interpolated from API error codes in user-visible surfaces. The mapping is `errorCode → l10n key` in one central `errorMessages.dart`.

---

## 3. Lint rules / enforcement

Recommended `analysis_options.yaml` additions on top of `very_good_analysis`:

```yaml
linter:
  rules:
    - avoid_positional_boolean_parameters
    - use_build_context_synchronously
    - prefer_const_constructors
    - prefer_const_literals_to_create_immutables
    - require_trailing_commas
```

Project-specific custom rules (implemented as `custom_lint`):
- No raw hex in `.dart` files outside `lib/app/theme/`.
- No `Duration(milliseconds: …)` outside `AppMotion`.
- No `Text('...')` with alphabetic content outside `lib/l10n/` or test files.
- No import of `lib/features/tracking/internal/**` from `lib/features/tracking/customer/**` (ADR-0014 asymmetric-visibility guardrail).

These can be added incrementally; the last one (tracking separation) is **must-have** before Phase 10 code lands.

---

## 4. Checklist for every new screen

- [ ] All user-visible text comes from `context.l10n`.
- [ ] No hard-coded colors, radii, spacings, durations.
- [ ] All interactive elements have 44×44 hit area and semantic label.
- [ ] Focus order matches visual order; Enter submits primary form action.
- [ ] Loading, error, and empty states are all designed (not just the happy path).
- [ ] Tested at 200% text scale and in dark theme.
- [ ] `Directionality.rtl` wrapper test passes structurally (no left/right hard-coding).
- [ ] No plaintext message content or password appears in any log, exception message, or analytics event.
