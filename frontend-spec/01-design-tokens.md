# Frontend Spec — 01 Design Tokens

**Audience:** Frontend Engineer translating tokens 1:1 into Flutter `ThemeData`, `ColorScheme`, `TextTheme`, and const value classes under `lib/app/theme/`.

All tokens are named to map directly onto Material 3 `ColorScheme` / `TextTheme` fields. Hex values are AA-compliant against their companion `onX` surface. Do not tweak hex without re-checking contrast.

---

## 1. Color Palette

### 1.1 Semantic role

The brand uses **deep indigo** as primary (trust, seriousness, not "fun startup blue") and **warm amber** as secondary (used sparingly — accents, badges, seller highlights). Neutrals are tuned slightly warm so screens don't feel clinical.

> **Open question (flag to Orchestrator):** final brand primary is a placeholder. A brand designer may override; all tokens are scoped so a single variable swap updates the app.

### 1.2 Light theme

| Token (Flutter `ColorScheme`) | Hex | Usage |
|---|---|---|
| `primary` | `#3F3D9E` | Primary buttons, active states, brand accents |
| `onPrimary` | `#FFFFFF` | Text/icons on primary |
| `primaryContainer` | `#E2E1FF` | Soft backgrounds of primary elements (chips, selected tiles) |
| `onPrimaryContainer` | `#0E0B5C` | Text/icons on primary container |
| `secondary` | `#B87333` | Secondary accents (seller badge, FABs where appropriate) |
| `onSecondary` | `#FFFFFF` | Text/icons on secondary |
| `secondaryContainer` | `#FBE6CC` | Soft backgrounds of secondary elements |
| `onSecondaryContainer` | `#3A2210` | Text/icons on secondary container |
| `tertiary` | `#2F6E5C` | Informational accents (delivery status, tertiary chips) |
| `onTertiary` | `#FFFFFF` | — |
| `error` | `#B3261E` | Error text, destructive button |
| `onError` | `#FFFFFF` | — |
| `errorContainer` | `#F9DEDC` | Error banner backgrounds |
| `onErrorContainer` | `#410E0B` | — |
| `success` (custom ext) | `#2E7D32` | Snackbar success, delivered state |
| `onSuccess` (custom ext) | `#FFFFFF` | — |
| `warning` (custom ext) | `#B26A00` | Snackbar warning, retention-countdown warnings |
| `onWarning` (custom ext) | `#FFFFFF` | — |
| `surface` | `#FFFBFE` | Cards, sheets, dialogs |
| `onSurface` | `#1C1B1F` | Primary body text |
| `surfaceVariant` | `#F3EFF4` | Secondary surfaces (input backgrounds, dividers-with-tint) |
| `onSurfaceVariant` | `#49454F` | Secondary body text, helper text |
| `background` | `#FFFBFE` | Scaffold background |
| `onBackground` | `#1C1B1F` | — |
| `outline` | `#79747E` | Borders, dividers |
| `outlineVariant` | `#CAC4D0` | Subtle dividers inside cards |
| `shadow` | `#000000` | Elevation shadow color (used at 8% opacity) |
| `scrim` | `#000000` | Modal scrim (used at 40% opacity) |
| `inverseSurface` | `#313033` | Snackbar background |
| `onInverseSurface` | `#F4EFF4` | Snackbar text |

### 1.3 Dark theme

| Token | Hex |
|---|---|
| `primary` | `#BDBBFF` |
| `onPrimary` | `#1C1A70` |
| `primaryContainer` | `#2C2A86` |
| `onPrimaryContainer` | `#E2E1FF` |
| `secondary` | `#F1BB80` |
| `onSecondary` | `#4A2A10` |
| `secondaryContainer` | `#683F20` |
| `onSecondaryContainer` | `#FBE6CC` |
| `tertiary` | `#9BD5BF` |
| `onTertiary` | `#00382E` |
| `error` | `#F2B8B5` |
| `onError` | `#601410` |
| `errorContainer` | `#8C1D18` |
| `onErrorContainer` | `#F9DEDC` |
| `success` (custom ext) | `#A5D6A7` |
| `warning` (custom ext) | `#FFCC80` |
| `surface` | `#1C1B1F` |
| `onSurface` | `#E6E1E5` |
| `surfaceVariant` | `#49454F` |
| `onSurfaceVariant` | `#CAC4D0` |
| `background` | `#1C1B1F` |
| `onBackground` | `#E6E1E5` |
| `outline` | `#938F99` |
| `outlineVariant` | `#49454F` |
| `inverseSurface` | `#E6E1E5` |
| `onInverseSurface` | `#313033` |

### 1.4 Role-badge colors (semantic, not part of ColorScheme)

Defined as `ThemeExtension<RoleBadgeColors>`:

| Role | Light bg / fg | Dark bg / fg |
|---|---|---|
| `admin` | `#410E0B` / `#FFFFFF` | `#F9DEDC` / `#410E0B` |
| `seller` | `#FBE6CC` / `#3A2210` | `#683F20` / `#FBE6CC` |
| `driver` | `#C7E7DF` / `#00382E` | `#2F6E5C` / `#E0F2EE` |
| `customer` | `#E2E1FF` / `#0E0B5C` | `#2C2A86` / `#E2E1FF` |

---

## 2. Typography Scale

Font families: **system defaults only** in Phase 8.
- iOS: SF Pro Text / SF Pro Display (Flutter picks via `CupertinoTheme` fallback; we just set `fontFamily: '.SF Pro Text'` implicitly via platform default by leaving `fontFamily` null in `TextTheme`).
- Android: Roboto.
- Do **not** bundle a custom font in Phase 8. Phase 14 can revisit brand typography.

Scale maps directly onto Material 3 `TextTheme`:

| Flutter role | Size (sp) | Weight | Letter-spacing | Line-height (px) | Usage |
|---|---|---|---|---|---|
| `displayLarge` | 57 | 400 | -0.25 | 64 | Not used in Phase 8; reserve for future splash hero |
| `displayMedium` | 45 | 400 | 0 | 52 | — |
| `displaySmall` | 36 | 400 | 0 | 44 | — |
| `headlineLarge` | 32 | 600 | 0 | 40 | Auth screen titles ("Welcome back") |
| `headlineMedium` | 28 | 600 | 0 | 36 | Empty-state headline |
| `headlineSmall` | 24 | 600 | 0 | 32 | Section headers |
| `titleLarge` | 22 | 600 | 0 | 28 | App bar title, card title |
| `titleMedium` | 16 | 600 | 0.15 | 24 | List tile title, button label (large) |
| `titleSmall` | 14 | 600 | 0.1 | 20 | Tab labels, subtle titles |
| `bodyLarge` | 16 | 400 | 0.5 | 24 | Primary body text, paragraph |
| `bodyMedium` | 14 | 400 | 0.25 | 20 | Default body, list subtitle |
| `bodySmall` | 12 | 400 | 0.4 | 16 | Timestamps, metadata |
| `labelLarge` | 14 | 600 | 0.1 | 20 | Button labels, chip labels |
| `labelMedium` | 12 | 600 | 0.5 | 16 | Badge labels, form field labels |
| `labelSmall` | 11 | 600 | 0.5 | 16 | Smallest captions (never interactive) |

All sizes respect `MediaQuery.textScaler`. No `TextStyle` should set an absolute `fontSize` outside `TextTheme` construction — widgets use `Theme.of(context).textTheme.<role>` exclusively.

---

## 3. Spacing Scale

| Token | Value (dp) | Typical use |
|---|---|---|
| `space1` | 4 | Icon ↔ label tight gap |
| `space2` | 8 | Small gap inside a row |
| `space3` | 12 | Default form field internal padding |
| `space4` | 16 | Card padding, default screen side gutter |
| `space5` | 24 | Section separation, dialog internal padding |
| `space6` | 32 | Large block separation |
| `space7` | 48 | Top-of-screen breathing room (auth hero) |

Expose as `class Spacing { static const s1 = 4.0; ... }` — **never** use magic numbers.

---

## 4. Radius Scale

| Token | Value (dp) | Usage |
|---|---|---|
| `radiusXs` | 4 | Badge, chip |
| `radiusSm` | 8 | Input, small button |
| `radiusMd` | 12 | Card, dialog, list tile container |
| `radiusLg` | 16 | Bottom sheet top corners |
| `radiusPill` | 999 | Pill button, avatar, role badge |

---

## 5. Elevation Scale

| Token | Value | Shadow |
|---|---|---|
| `elev0` | 0 | No shadow — flush surfaces |
| `elev1` | 1 | Default card — `BoxShadow(0, 1, 2, color=shadow@8%)` |
| `elev2` | 2 | App bar on scroll, pressed card |
| `elev4` | 4 | Dialog, bottom sheet, snackbar |

On Android, set `Material` `elevation` directly; on iOS-feel screens, fall back to 1dp hairline borders using `outlineVariant` where elevation feels heavy.

---

## 6. Motion

| Token | Duration | Curve | Usage |
|---|---|---|---|
| `motionQuick` | 150 ms | `Curves.easeOut` | Default for color, opacity, and small translate animations |
| `motionStandard` | 250 ms | `Curves.easeOutCubic` | Modal enter, page transitions, bottom-sheet reveal |
| `motionEmphasized` | 400 ms | `Curves.easeOutExpo` | First-run celebratory moments only (e.g. "welcome" hero); not for Phase 8 |

Page transitions default to a 250 ms fade+slide from bottom 8 dp. Modal dismiss uses `motionStandard` reverse.

Respect `MediaQuery.disableAnimations == true` → durations collapse to 0, curves become linear.

---

## 7. Iconography

- **Icon set (Phase 8):** Material Icons (ships with Flutter) — no new asset pipeline.
- **Sizes:** 20 (inline), 24 (default interactive), 28 (app bar trailing), 32 (empty-state hero).
- **Color:** inherit from text color unless semantic (error → `colorScheme.error`, success → `success` extension).

> **Open question (flag):** move to a custom icon set (Phosphor, Lucide) in Phase 10 for brand consistency on chat/tracking affordances. Not decided.

---

## 8. Implementation Notes for the Frontend Engineer

- Create `lib/app/theme/tokens.dart` with `const` classes: `AppColors`, `AppSpacing`, `AppRadius`, `AppElevation`, `AppMotion`.
- Create `lib/app/theme/theme.dart` with `lightTheme()` and `darkTheme()` builders that return `ThemeData` wired from the tokens.
- Custom semantic colors (`success`, `warning`, role badges) go through `ThemeExtension<T>` — never as static constants read outside the theme.
- Expose `context.colors`, `context.spacing`, `context.radii`, `context.motion` extension getters on `BuildContext` so widgets read tokens without importing `tokens.dart` everywhere.
- System theme mode is the default (`themeMode: ThemeMode.system`); user override stored in `secureStorageProvider` is Phase 9+.
