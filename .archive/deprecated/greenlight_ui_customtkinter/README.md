# Archived: CustomTkinter UI

**Archived Date:** 2025-12-13

## Reason for Deprecation

The CustomTkinter-based desktop UI was deprecated due to persistent widget lifecycle errors:

1. **TclError Exceptions**: Constant `invalid command name` errors caused by widget lifecycle race conditions
2. **Threading Issues**: Complex threading model led to race conditions during widget updates
3. **Limited Ecosystem**: CustomTkinter has limited component ecosystem compared to web technologies
4. **Debugging Difficulty**: Opaque Tcl errors made debugging extremely difficult

## Replacement

The UI has been migrated to a web-based architecture:

- **Frontend**: Next.js 14 + React + Tailwind CSS + Radix UI
- **Backend API**: FastAPI with WebSocket support
- **Location**: `Agnostic_Core_OS/web/src/app/greenlight/`

## Running the New Web UI

1. Start the FastAPI backend:
   ```bash
   cd Agnostic_Core_OS
   uvicorn api.main:app --reload --port 8000
   ```

2. Start the Next.js frontend:
   ```bash
   cd Agnostic_Core_OS/web
   pnpm dev
   ```

3. Open http://localhost:3000/greenlight in your browser

## Files in This Archive

- `main_window.py` - Main application window
- `theme.py` - Theme configuration
- `components/` - UI components (panels, modals, etc.)
- `dialogs/` - Dialog windows

## Do Not Use

This code is archived for reference only. Do not attempt to run or import these modules.

