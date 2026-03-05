# MyClaw Browser Agent v2

Generic atomic browser executor extension for MyClaw.

## Goal

- Keep extension generic and stable.
- Move page-specific strategies to Python jobs/skills.

## Load

1. Open `chrome://extensions/`
2. Enable developer mode
3. Load unpacked extension from:
   - `extensions/myclaw-browser-agent-v2/`

## Channel

- WebSocket: `ws://127.0.0.1:8000/ws/browser-gateway`
- Client meta: `mode=atomic_v2`

## Atomic actions

- Tab-level:
  - `navigate`
  - `get_url`
  - `go_back`
  - `go_forward`
  - `wait`
- DOM-level:
  - `snapshot`
  - `locate`
  - `click`
  - `type`
  - `hover`
  - `press_key`
  - `select_option`
  - `scroll_into_view`
  - `wait_for`
  - `assert`

## Return contract

Each action returns an object with at least:

- `ok`: boolean
- `changed`: boolean (where applicable)
- `error_code`: present when failed
- `message`: optional

No page-specific logic should be added here.
