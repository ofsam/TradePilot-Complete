# TradePilot Mobile

Expo (Android + iPhone) client for the cloud TradePilot API.

## Setup

```bash
cd mobile
cp .env.example .env
# set EXPO_PUBLIC_API_BASE_URL to your HTTPS VPS API
npm install
npx expo start
```

## Builds (EAS)

```bash
npm install -g eas-cli
eas login
eas build --platform android --profile preview
eas build --platform ios --profile preview
```

Replace `EXPO_PUBLIC_API_BASE_URL` in [`eas.json`](eas.json) with your real API host before production builds.

See [DEPLOY-VPS.md](DEPLOY-VPS.md) for the Windows + MT5 worker.
