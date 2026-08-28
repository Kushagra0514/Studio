# Studio frontend

This directory contains Studio's React interface. It is part of the main Studio application, not a standalone Vite template.

## Requirements

- Node.js `^20.19.0` or `>=22.12.0`
- npm
- A Studio backend listening on `http://localhost:8000` for local development

## Commands

Run these from the repository root:

```powershell
npm --prefix frontend ci
npm --prefix frontend run dev
npm --prefix frontend test
npm --prefix frontend run lint
npm --prefix frontend run build
```

The development server is available at `http://localhost:5173`. `vite.config.js` proxies `/api` to the backend at `http://localhost:8000`.

The production Docker stage builds the same source with `npm ci` and serves `dist/` through Nginx on port `80`. Nginx proxies `/api/` to the Compose backend service.

## API-key handling

If no key is already present, the UI prompts for a Groq API key. It stores the value in browser `localStorage` under `groq_api_key` and sends it in the `X-Groq-Api-Key` request header. This is intended only for trusted local development and is not a secure browser credential store.

## Source layout

```text
src/App.jsx          Main application state and layout
src/api.js           Backend API client
src/components/      Upload, search, response, source, and key-modal UI
src/index.css        Application styles
nginx.conf           Production static hosting and API proxy
vite.config.js       Development server and API proxy
```

See the root `README.md` for full setup, Docker, persistence, Firecrawl, security limitations, and troubleshooting instructions.
