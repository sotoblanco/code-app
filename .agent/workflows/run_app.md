---
description: How to run the application (frontend and backend)
---

# Run Application

The application consists of a FastAPI backend and a React frontend. You can run them together using the provided shell script or individually.

## Prerequisites

-   **Node.js & npm** (for frontend)
-   **uv** (for backend dependency management)

## Option 1: Run All Services (Recommended)

Use the helper script to verify dependencies and start both services:

```bash
./dev.sh
```

This will check for `docker`, `uv` and `npm`, build the sandbox image, and launch:
-   Backend: [http://localhost:8000](http://localhost:8000)
-   Frontend: [http://localhost:5173](http://localhost:5173)

## Option 2: Run Individually

### Backend

```bash
cd backend
uv run uvicorn main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm run dev
```

## Verification

To verify the app is running:
1.  Open [http://localhost:5173](http://localhost:5173).
2.  Ensure you can see the course list or login page.
3.  If issues persist, check the terminal output for errors.
