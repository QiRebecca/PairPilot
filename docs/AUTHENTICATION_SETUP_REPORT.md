# PairPilot authentication setup report

Updated: 2026-08-29 (Asia/Shanghai)

## Project and provider

- Google Cloud project: `pairpilot-agentic-ecb84a` (`120073530735`)
- Firebase project state: `ACTIVE`
- Identity tenant mode: not enabled
- Firebase Authentication: initialized
- Enabled P0 sign-in method: Email/Password (`enabled=true`, `passwordRequired=true`)
- Passwordless email link: intentionally not enabled for P0
- Google Analytics: intentionally not enabled during Firebase initialization

## Web application

- Display name: `PairPilot Public Beta Web`
- App ID: `1:120073530735:web:b7d42bb211c98f938d0c9a`
- Auth domain: `pairpilot-agentic-ecb84a.firebaseapp.com`
- Messaging sender ID: `120073530735`
- Storage bucket: `pairpilot-agentic-ecb84a.firebasestorage.app`
- The browser API key is non-secret Firebase client configuration. Its value is not copied into this report; deployment reads it from the Firebase Management API.

Authorized domains at this stage:

- `localhost`
- `pairpilot-agentic-ecb84a.firebaseapp.com`
- `pairpilot-agentic-ecb84a.web.app`
- `pairpilot-orchestrator-ew4hz5g3la-nw.a.run.app`
- `personal-os---pairpilot-orchestrator-ew4hz5g3la-nw.a.run.app`
- `multi-user-beta---pairpilot-orchestrator-ew4hz5g3la-nw.a.run.app`

## Email actions

- Sign-up calls Firebase `sendEmailVerification` with a return URL under the current application origin.
- The verification route handles `oobCode`, reloads the provider user, and includes a client-side 60-second resend guard.
- Password reset uses Firebase `sendPasswordResetEmail` and returns to `/sign-in`.
- Production templates and clean-browser link behavior remain candidate-E2E evidence, not yet passed.

## SDKs and server identity

- Frontend Firebase Web SDK: `12.18.0`
- Backend Firebase Admin SDK: `7.5.0`
- Cloud Run uses the attached `pairpilot-runtime` service account and Application Default Credentials.
- No service-account key was created or downloaded.
- ID tokens are verified with revocation checking enabled.

Non-secret runtime variables:

- `GOOGLE_CLOUD_PROJECT`
- `PAIRPILOT_FIREBASE_API_KEY`
- `PAIRPILOT_FIREBASE_AUTH_DOMAIN`
- `PAIRPILOT_FIREBASE_APP_ID`
- `PAIRPILOT_FIREBASE_MESSAGING_SENDER_ID`
- `PAIRPILOT_FIREBASE_STORAGE_BUCKET`

## Test accounts

Two controlled Firebase test accounts were created with different UIDs and `emailVerified=true`. Their random passwords exist only as Secret Manager versions and were never printed or committed. They passed the authenticated API E2E. Provider-delivered verification links must still be tested through secure human inbox interaction before launch.

## Operational notice

The Firebase Console displayed a requirement for the signed-in project account to enable Google-account MFA by 2026-08-29. This is an account-access requirement, not an application tenant-mode setting.
