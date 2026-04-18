# Android signing — keystore workflow

## One-time: generate the upload keystore

```bash
keytool -genkey -v \
  -keystore ~/marketplace-upload.keystore \
  -alias marketplace-upload \
  -keyalg RSA -keysize 2048 -validity 10000
```

Record the passwords you pick — they must match the Gradle properties
below exactly.

## Local developer setup

Place the keystore at `~/marketplace-upload.keystore` and add to
`~/.gradle/gradle.properties` (NOT project-tracked):

```
MARKETPLACE_UPLOAD_STORE_FILE=/home/you/marketplace-upload.keystore
MARKETPLACE_UPLOAD_STORE_PASSWORD=...
MARKETPLACE_UPLOAD_KEY_ALIAS=marketplace-upload
MARKETPLACE_UPLOAD_KEY_PASSWORD=...
```

If the keystore is missing, release builds fall back to the debug signing
config — unsigned builds won't upload to Play, but `flutter run` and
debug APKs still work.

## CI (GitHub Actions)

Store the binary keystore as a base64 secret
(`ANDROID_KEYSTORE_B64`), plus `ANDROID_KEYSTORE_PASSWORD`,
`ANDROID_KEY_ALIAS`, `ANDROID_KEY_PASSWORD`.  See
`.github/workflows/mobile-release.yml` for the decode step.

The Play upload step uses the `PLAY_JSON_KEY` service-account JSON
stored as a GitHub secret.

## Rotating the upload key

Play Console supports upload key replacement: generate a new keystore,
submit the old + new signatures to Play support, update all four Gradle
properties, and rebuild.  The app signing key (held by Play) does not
change — only the upload-side key you sign with.
