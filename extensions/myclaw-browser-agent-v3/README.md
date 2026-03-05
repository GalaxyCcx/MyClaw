# MyClaw Browser Agent v3

Vision-first browser extension for MyClaw.

## Goal

- Produce labeled screenshot (`a1`, `a2`, ...)
- Execute actions by label using coordinates
- Keep protocol simple for agent-driven loops

## Load

1. Open `chrome://extensions/`
2. Enable developer mode
3. Load unpacked extension from:
   - `extensions/myclaw-browser-agent-v3/`

## Channel

- WebSocket: `ws://127.0.0.1:8000/ws/browser-gateway`
- Client meta: `mode=vision_v3`

## Actions

- `navigate`, `go_back`, `go_forward`, `wait`, `get_url`
- `vision_capture_marked`
  - Mark current page interactive elements with labels
  - Take screenshot
  - Return `{ data_url, marks[] }`
- `vision_click_label`
  - Click center point of mark label (for example `a1`)
- `vision_type_label`
  - Click label target then type text into active element
- `vision_clear_marks`
- `screenshot` (plain visible viewport screenshot)

## Marks Schema

Each mark item includes:

- `label`: string (for example `a1`)
- `x`, `y`, `width`, `height`: viewport coordinates
- `tag`, `role`, `text`: lightweight element hints

