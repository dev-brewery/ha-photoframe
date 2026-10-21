# Photoframe for Home Assistant

A Home Assistant integration for frames running
[dev-brewery/photoframe](https://github.com/dev-brewery/photoframe). It talks to
the frame's HTTP API (port 7777, HTTP Basic auth) and turns the frame into a
device with a screen switch, navigation buttons, settings, and, once the frame
supports it, an album picker for voice control.

It replaces hand-written `rest_command` + script packages: credentials are
entered once in the UI, and state comes from the frame instead of being guessed.

## Entities

| Entity | Type | Frame API |
|---|---|---|
| Photo frame (the screen) | switch | state `GET /details/display`, `GET /control/screenon\|screenoff` |
| Album | select | `GET /album`, `PUT /album/<albumId>\|all` (see below) |
| Next / Previous photo | button | `GET /control/nextImage\|prevImage` |
| Next / Previous album | button | `GET /control/nextAlbum\|prevAlbum` (see below) |
| Reboot | button (config) | `GET /maintenance/reboot` |
| Photo interval, Display on/off hour | number (config) | `PUT /setting/interval\|display-on\|display-off/<value>` |
| Image sizing, Power save, When offline | select (config) | `PUT /setting/<key>/<value>` |
| Shuffle photos, Photo cache | switch (config) | `PUT /setting/randomize_images\|enable-cache/<0\|1>` |
| Rotation, Overscan | select / switch (config, disabled by default; apply after reboot) | `PUT /rotation/<deg>`, `PUT /overscan/<bool>` |
| Network, Undervoltage / Throttled / Temperature limit since boot | binary sensor (diagnostic) | `GET /details/network`, `GET /details/hardware` |

The frame is polled every 30 seconds, and again right after every command.

### Album selection

The **Album** select and the album buttons appear only when the frame has the
active-album API proposed in
[dev-brewery/photoframe#80](https://github.com/dev-brewery/photoframe/issues/80#issuecomment-6306139246):
`GET /album` returning `{"active": {"albumId", "name"} | null, "albums": [{"albumId", "name", "assetCount"}]}`
and `PUT /album/<albumId>` / `PUT /album/all`. Until then `/album` returns 404 and
the integration leaves those entities out (`nextAlbum`/`prevAlbum` are no-ops on
current frame software). After updating the frame, reload the integration to
pick them up.

Album options are the Immich album names. Duplicate names get a counter
("Vacation (2)"), and "All albums" restores the normal mix.

## Installation

The frame must be reachable from Home Assistant.

- **HACS:** add this repository as a custom repository (category *Integration*),
  install *Photoframe*, restart Home Assistant.
- **Manual:** copy `custom_components/photoframe` to `/config/custom_components/`,
  restart Home Assistant.

Then go to *Settings → Devices & services → Add integration → Photoframe* and
enter the frame's host, port (7777) and its web-interface username and password.
If the password changes later, Home Assistant asks for it again.

## Google Assistant

Home Assistant's built-in `google_assistant` integration (manual setup, no
Home Assistant Cloud) exposes these entities:

- the screen switch: "Hey Google, turn off the photo frame"
- the album select, as a Google *mode* whose settings are the album names
- the photo buttons, as scenes: "Hey Google, activate next photo"

A ready package is in `../ha-config/packages/google_assistant.yaml`. It exposes
only those entities and resyncs Google when the album list changes. Follow the
[manual setup](https://www.home-assistant.io/integrations/google_assistant/#manual-setup)
for the Google Home Developer Console project, service account and HomeGraph API,
then fill in the project ID and user ID and restart.

## Development

Tests use Home Assistant's own test harness with a mocked HTTP session; no frame
is contacted. They need Linux (HA doesn't install on Windows), so run them in a
container:

```sh
docker run --rm -v "$PWD:/src:ro" python:3.14 bash -c \
  "cp -r /src /work && cd /work && pip install -q -r requirements_test.txt && pytest -q"
```

Validate the integration the way HACS CI does:

```sh
docker run --rm -v "$PWD:/github/workspace" ghcr.io/home-assistant/hassfest
```
