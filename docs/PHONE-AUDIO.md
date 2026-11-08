# Phone audio while playing

The intended flow is to start a receiver, choose Nova as the output on the phone, return to Library and play. The phone keeps its existing music or podcast app. The frontend's Apps → Phone audio panel provides the route and setup explanation; an available receiver also adds a Settings row. B returns to the originating Apps or Settings screen.

## Capability boundary

An ordinary Android Bluetooth audio connection usually sends audio to speakers or headphones. Receiving phone audio requires an A2DP sink implementation enabled by the firmware; installing a player does not create it. Nova's sink capability has not been established. No rooting, flashing or Bluetooth-sink promise is part of this route. See [AOSP Bluetooth services](https://source.android.com/docs/core/connect/bluetooth/services).

For an iPhone, the prepared alternative is [Android AirPlay Server](https://github.com/jqssun/android-airplay-server), a Wi-Fi AirPlay/RAOP receiver based on UxPlay. The selected upstream release is [v0.0.36](https://github.com/jqssun/android-airplay-server/releases/tag/v0.0.36), source commit `a46cca0a6a1274e9e33c0e750f0f1c1eb1d881ea`, GPL-3.0. Its APK is not bundled, installed or started by Nova. The exact app package is `io.github.jqssun.airplay`; title matching is never sufficient to enable the launch action.

The receiver needs local network discovery and a background playback service. Same-network reception, hotspot discovery, game-audio mixing, headphones and interruption behavior require actual device tests. Android audio focus can affect concurrent playback; a configured app route is not mixing proof. See [Android audio focus](https://developer.android.com/media/optimize/audio-focus).

## Proposed receiver profile

These are reviewed setup intentions, not settings already applied:

- Name the receiver Nova. Require a pairing PIN, entered on the phone.
- Keep background playback enabled. Disable startup on boot and opening its activity when a phone connects, so it cannot take over a game.
- Disable keeping the display awake. Disable sender-to-system volume synchronization, so phone volume adjusts the incoming stream rather than Android's shared game/music volume.
- Advertise audio. Video/mirroring discovery can be disabled for an audio-focused setup.
- Do not grant the optional draw-over-other-apps permission. A visible foreground-service notification is separate.

Upstream defaults include automatic startup, automatic foregrounding and no pairing PIN. Configure the reviewed profile before exposing a receiver on the network. Installing this separate app, allowing its persistent notification/service access and starting the receiver require explicit device authorization. This document grants none of those permissions.

## Acceptance on the real Nova

Check phone → Nova playback, background game plus phone audio, separate phone stream volume and Nova master volume, speaker/headphone routing, disconnect/reconnect, game pause/return, sleep/wake and stopping the receiver. Verify no automatic foreground takeover, no boot startup and no overlay grant. Keep the PIN and private network details off logs and source.

Desktop QML checks cover exact-package routing, absent-app explanation, Apps/Settings entry and Back paths. They do not certify receiver operation or audible mixing.
