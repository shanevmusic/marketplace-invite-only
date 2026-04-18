# iOS signing — App Store Connect API key workflow

## One-time setup

1. In App Store Connect → Users and Access → Keys, generate an API key
   with App Manager role.  Download the `.p8` file (you cannot re-download).
2. Note the `issuer_id` (top of the Keys page) and the `key_id` (on the
   row of the key you just made).
3. Export your distribution certificate as `.p12` from Keychain Access.
4. Download the matching App Store provisioning profile from the
   developer portal.

## GitHub secrets

| Secret                            | Contents                              |
|-----------------------------------|---------------------------------------|
| `APPSTORE_API_ISSUER_ID`          | Issuer ID from ASC                    |
| `APPSTORE_API_KEY_ID`             | Key ID of the .p8                     |
| `APPSTORE_API_PRIVATE_KEY`        | Contents of the .p8 file              |
| `IOS_CERT_P12_B64`                | `base64 < dist.p12`                   |
| `IOS_CERT_PASSWORD`               | Password used on the .p12 export      |
| `IOS_PROVISIONING_PROFILE_B64`    | `base64 < profile.mobileprovision`    |

## Local build

```bash
cd frontend
flutter build ipa --release \
  --export-options-plist=ios/ExportOptions.plist
```

Then upload with Transporter.app or `xcrun altool --upload-app`.

## ExportOptions.plist

Edit `REPLACE_TEAM_ID` and `REPLACE_PROFILE_NAME` in
`frontend/ios/ExportOptions.plist` to match your Apple team and the
provisioning profile name you downloaded.  Everything else (method,
signing style) is already set for App Store submission.

## Notes

- The iOS job in `.github/workflows/mobile-release.yml` is disabled by
  default (`if: false`).  Flip it on after you've run a manual upload
  once and verified the credentials work.
- macOS runner minutes are billed at ~10× Linux rates — keep the job
  manual-dispatch only.
