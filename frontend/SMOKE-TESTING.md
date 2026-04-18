# Smoke testing — Phase 8

Manual paths to exercise on a real device before cutting a build.

## Pre-flight

1. Backend running locally at `API_BASE_URL`.
2. Clean app state (uninstall and reinstall, or clear app data).
3. A fresh invite token for each run (they are single-use).

## 1. Unauth cold start

- Launch app → briefly see `/splash`, then land on `/login`.
- Inputs: email, password, "Sign in" button.
- Submit disabled until email matches `.+@.+\..+` and password is non-empty.

## 2. Login — happy path

- Enter existing credentials, tap **Sign in**.
- Expect: route transitions to `/home/<role>` for your role.
- Bottom nav + profile avatar render the user's role badge color.

## 3. Login — invalid credentials

- Wrong password → inline error "Incorrect email or password." on password field. No banner.

## 4. Login — network error

- Turn off wifi + cellular → top banner "Can't reach the server. Check your connection."

## 5. Login — rate limited

- Hit 10 failed logins quickly → banner "Too many attempts. Try again in a minute."

## 6. Expired session (mid-session refresh failure)

- Log in. Delete the refresh token on the backend (or wait past expiry).
- Pull any protected endpoint from within the app (e.g. open a tab that fetches).
- Expect: silent 401 → refresh attempt fails → redirected to `/login` with toast "Your session expired. Please sign in again."

## 7. Invite — unauth flow

- Tap `marketplace://invite/<token>` link (or paste into a URL handler).
- Expect: `/invite/:token` loading spinner → success → `/signup?invite_token=...`.
- Signup screen prefills invite token; if type is `seller_referral`, "Which kind of account do you want?" card-pair is visible.
- Successful signup → route to `/home/<role>`.

## 8. Invite — authed flow

- While signed in, tap an invite link.
- Expect: confirmation dialog "Use this invite?" with Primary ("Use this invite") + Secondary ("Stay signed in").
- Primary → logout + navigate to `/invite/:token`. Secondary → dismiss, no route change.

## 9. Invite — invalid / expired / used

- Tap a consumed or expired link.
- Expect: invite landing screen shows empty state per §4.1 ("Ask for a new invite…"), CTA "Close" → back to `/login`.

## 10. Role guard

- While logged in as a customer, manually deep-link to `/home/seller/chat`.
- Expect: redirect to `/home/customer` (role guard).

## 11. Deep link — cold start

- Close app completely. Tap invite link from another app.
- Expect: app launches, splash resolves, invite landing screen shows immediately (not `/login` first).

## 12. Persistence

- Log in. Background the app. Kill it. Reopen.
- Expect: splash → refresh succeeds → lands on `/home/<role>` without re-entering credentials.
- Repeat but revoke the refresh token server-side beforehand → lands on `/login` with expired-session toast.

## 13. Theme

- System dark mode on → dark palette applies.
- All text legible; no unreadable surfaces in either mode.
- Role badge colors match spec: customer=teal, seller=coral, driver=amber, admin=violet.

## 14. Accessibility

- Set iOS/Android largest font scale → no clipped buttons (heights are min 44dp but content wraps).
- VoiceOver/TalkBack reads button labels (custom `semanticsLabel` where provided).
- Form errors announce once via `Semantics(liveRegion: true)`.

## 15. Logout

- Profile tab → Logout → confirm dialog → signed out → `/login`.
- Token storage cleared (verified: reopen app, no auto-login).
