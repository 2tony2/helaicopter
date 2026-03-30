# iPhone Developer Mode Guide

This guide is for the specific goal of running Helaicopter on your own iPhone while the app is still in local development.

You do not need the App Store.
You do not need TestFlight.
You do need a Mac, Xcode, your iPhone, and the dev servers running on your Mac.

## What You Are Building

Helaicopter already has an iOS shell through Capacitor. The phone does not contain the whole app by itself. Instead:

1. your iPhone opens the Helaicopter web app inside a native iOS wrapper
2. the wrapper loads the app from your Mac
3. your Mac runs both the Next.js frontend and the FastAPI backend
4. the frontend forwards browser API calls through `/api/backend/*`, so the phone only needs the frontend URL

That means your Mac must be awake and running the dev servers while you test on the phone.

## Before You Start

You need all of these:

- a Mac with this repo checked out
- Node/npm dependencies installed
- Python/uv dependencies installed
- Xcode installed
- an iPhone connected to the same Tailscale tailnet as your Mac
- a Lightning or USB-C cable for the first install
- an Apple ID signed into Xcode

## One-Time Setup

### 1. Install dependencies

From the repo root:

```bash
npm install
uv sync --group dev
```

### 2. Install and sign into Xcode

Open Xcode once and make sure your Apple ID is added:

1. Open Xcode
2. Go to `Xcode` -> `Settings`
3. Open the `Accounts` tab
4. Sign in with your Apple ID if it is not already there

If you are not paying for the Apple Developer Program, that is fine for personal device testing. Apple documents that a Personal Team can sign apps for your own devices, but not for App Store submission.

## Every Time You Want To Test On Your Phone

### 1. Start the mobile dev servers on your Mac

From the repo root:

```bash
npm run dev:mobile
```

What this does:

- starts Next.js on a phone-reachable host
- starts FastAPI on a phone-reachable host
- uses a same-origin backend proxy so the phone app does not call `127.0.0.1`

Leave this terminal window running.

Look at the output and note the web port. It will look like this:

```text
[dev] starting Next.js frontend on http://0.0.0.0:32xxx
```

That `32xxx` number is the port your phone app needs.

### 2. Find your Mac hostname on Tailscale

On your Mac:

```bash
tailscale status
```

Find your Mac in the output. You want the Tailscale DNS name or hostname for your Mac.

It usually looks something like one of these:

- `my-mac`
- `my-mac.tailnet-name.ts.net`

If you are unsure, use the full Tailscale DNS name.

### 3. Build the exact URL the phone should open

Use this format:

```text
http://YOUR-MAC-HOSTNAME:WEB_PORT
```

Example:

```text
http://my-mac.tail-example.ts.net:32123
```

### 4. Test that URL in Safari on the iPhone first

Before touching Xcode, open Safari on your iPhone and visit the URL from step 3.

If this does not load, stop there and fix that first.

If Safari works, the Capacitor shell should also work once installed.

### 5. Tell Capacitor which URL to load

In the same terminal on your Mac:

```bash
export HELA_MOBILE_SERVER_URL=http://YOUR-MAC-HOSTNAME:WEB_PORT
```

Example:

```bash
export HELA_MOBILE_SERVER_URL=http://my-mac.tail-example.ts.net:32123
```

### 6. Sync the iOS project with that URL

```bash
npm run mobile:ios:sync
```

This updates the native iOS project so the app wrapper points at your Mac.

### 7. Open the iOS project in Xcode

```bash
npm run mobile:ios:open
```

Xcode should open the `ios` workspace for Helaicopter.

### 8. Connect your iPhone to the Mac

Use a cable for the first install. Wireless debugging can come later, but cable is simpler and less flaky.

On the iPhone, if you see a "Trust This Computer?" prompt, tap `Trust`.

### 9. Configure signing in Xcode

In Xcode:

1. Click the project in the left sidebar
2. Under `Targets`, click `App`
3. Open the `Signing & Capabilities` tab
4. Check `Automatically manage signing`
5. In `Team`, choose your Apple ID Personal Team

If Xcode complains about the bundle identifier already being taken, change it to something unique like:

```text
com.tony.helaicopter.dev
```

### 10. Select your iPhone as the run destination

Near the top of Xcode, choose your connected iPhone instead of a simulator.

### 11. Build and run the app

Press the Run button in Xcode.

The first install may take a minute.

If Xcode says the app installed but the phone blocks it, keep going with the next steps.

## iPhone Device Steps You May Need

### Enable Developer Mode

On newer iPhones, apps installed directly from Xcode may require Developer Mode.

If iOS prompts you, follow the on-screen steps. In general, the setting is under:

1. `Settings`
2. `Privacy & Security`
3. `Developer Mode`

Turn it on, then allow the phone to restart if asked.

After restart, confirm the Developer Mode prompt on the phone.

### Trust your signing identity

If the phone says the developer is not trusted:

1. Open `Settings`
2. Go to `General`
3. Go to `VPN & Device Management`
4. Find your Apple ID under Developer App
5. Tap `Trust`

Then open the app again.

## Expected Result

When everything is correct:

- the app opens on your iPhone
- you see the Helaicopter UI inside a native app shell
- navigation works
- data loads from your Mac
- if you stop `npm run dev:mobile`, the app stops working until you start it again

That last part is normal for this local developer setup.

## Daily Fast Path

After the first successful install, your normal loop is:

```bash
npm run dev:mobile
export HELA_MOBILE_SERVER_URL=http://YOUR-MAC-HOSTNAME:WEB_PORT
npm run mobile:ios:sync
npm run mobile:ios:open
```

Then press Run in Xcode.

## Troubleshooting

### Safari on the phone cannot open the URL

Check these first:

- Tailscale is connected on the Mac
- Tailscale is connected on the iPhone
- `npm run dev:mobile` is still running
- you used the web port from the dev output, not the API port
- you used `http://`, not `https://`

### The app opens but shows blank content

Check:

- the URL in `HELA_MOBILE_SERVER_URL` matches the web port, not the API port
- you ran `npm run mobile:ios:sync` after exporting the variable
- Xcode built the latest native config

### The app shell loads but data does not appear

Check:

- `npm run dev:mobile` is running
- the terminal shows both Next.js and FastAPI started
- Safari on the phone can still load the frontend URL
- the frontend is using the proxy path `/api/backend/*`

### Xcode says there is a signing problem

Check:

- your Apple ID is added in Xcode settings
- `Automatically manage signing` is enabled
- the bundle identifier is unique
- your iPhone is unlocked and trusted

### The phone says the app is not trusted

Go to:

- `Settings` -> `General` -> `VPN & Device Management`

Then trust the developer profile tied to your Apple ID.

## Useful Commands

```bash
# Start phone-reachable dev servers
npm run dev:mobile

# Show your Tailscale devices and hostnames
tailscale status

# Sync iOS project after changing HELA_MOBILE_SERVER_URL
npm run mobile:ios:sync

# Open the iOS project in Xcode
npm run mobile:ios:open
```

## Reference Links

- Apple Personal Team signing note: <https://developer.apple.com/library/archive/qa/qa1915/_index.html>
- Capacitor: <https://capacitorjs.com/>
