---
description: How to build and run the mobile app using Capacitor
---

# Mobile App Development Workflow

## Prerequisites
- **Android:** Install [Android Studio](https://developer.android.com/studio)
- **iOS:** Install Xcode (macOS only)

## Development Flow

### 1. Run web app locally
// turbo
```
cd c:\Startup\GenAISample\RAG_HR_ASSISTANT\frontend
npm start
```

### 2. Build for mobile
// turbo
```
cd c:\Startup\GenAISample\RAG_HR_ASSISTANT\frontend
npm run build
```

### 3. Sync web assets to native projects
// turbo
```
cd c:\Startup\GenAISample\RAG_HR_ASSISTANT\frontend
npx cap sync
```

### 4. Open in Android Studio
```
cd c:\Startup\GenAISample\RAG_HR_ASSISTANT\frontend
npx cap open android
```

### 5. Open in Xcode (macOS only)
```
cd c:\Startup\GenAISample\RAG_HR_ASSISTANT\frontend
npx cap open ios
```

## Live Reload (Development)

To test with live reload on a device/emulator:

1. Uncomment the `url` line in `capacitor.config.ts`:
   ```ts
   server: {
     url: 'http://YOUR_LOCAL_IP:3001',  // <-- uncomment this
   }
   ```
2. Replace `YOUR_LOCAL_IP` with your machine's IP (e.g. `10.5.0.2`)
3. Run `npm start` on your machine
4. Run `npx cap sync` then `npx cap open android`
5. Run the app in Android Studio — it will load from your dev server with hot reload

## Production Build

1. Comment out the `url` line in `capacitor.config.ts`
2. Run `npm run build && npx cap sync`
3. Build the APK/AAB in Android Studio: Build → Generate Signed Bundle/APK
