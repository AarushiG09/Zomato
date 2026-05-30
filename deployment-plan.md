# Deployment Plan: Zomato AI Recommendation System

This document outlines the architecture, environment configuration, and step-by-step instructions to deploy the **FastAPI Backend on Railway** and the **React Frontend on Vercel**.

---

## 🏗️ Deployment Architecture

```text
┌─────────────────┐       HTTP Requests        ┌──────────────────┐
│ React Frontend  │ ─────────────────────────> │ FastAPI Backend  │
│   (Vercel)      │ <───────────────────────── │    (Railway)     │
│  Static HTML    │        CORS Enabled        │  SQLite + Groq   │
└─────────────────┘                            └──────────────────┘
```

---

## 1. Backend Deployment (Railway)

Railway will host the Python FastAPI web server, compile dependencies, execute the database ingestion script, and connect to the Groq LLM API.

### 1.1 Pre-requisites & Files
We need to ensure Railway knows how to run the FastAPI app. We will use a standard startup script or Start Command.

1. **Start Command**:
   In Railway, configure the service **Start Command** to:
   ```bash
   python scripts/ingest_dataset.py && uvicorn StitchUIDesign.server:app --host 0.0.0.0 --port $PORT
   ```
   *Note: This ensures that if the SQLite database is missing (since `data/*.db` is gitignored), the ingestion script runs and builds `data/restaurants.db` before the server starts listening for web requests.*

2. **Python Version**:
   Railway detects Python automatically. If you want to specify a version, add a `runtime.txt` at the root of the project with:
   ```text
   python-3.9.6
   ```

### 1.2 Step-by-Step Railway Setup
1. Log in to [Railway.app](https://railway.app/).
2. Click **New Project** -> **Deploy from GitHub repo**.
3. Select your repository.
4. Click **Add Variables** and configure the following environment variables:
   - `GROQ_API_KEY`: *Your Groq API key* (Required for LLM completions)
   - `GROQ_MODEL`: `llama-3.3-70b-versatile` (Optional, defaults to this model)
   - `DATABASE_PATH`: `data/restaurants.db` (Optional, defaults to this path)
5. Go to **Settings** -> **Service** -> **Start Command** and paste the start command from §1.1.
6. Railway will build and deploy the container. Once deployed, go to **Settings** -> **Public Networking** and click **Generate Domain**. You will get a URL like:
   `https://zomato-recommender-backend.up.railway.app`

---

## 2. Frontend Deployment (Vercel)

Vercel will host the single-page React frontend (`StitchUIDesign/index.html`).

### 2.1 Code Adjustments for Production API
In `StitchUIDesign/index.html`, the frontend fetches data from relative paths (`fetch("/api/v1/cities")`). When hosted separately, it must point to your Railway backend URL.

To handle this cleanly in both development (local) and production, update the fetch endpoints in `StitchUIDesign/index.html`:

```javascript
// Resolve the API URL dynamically
const BACKEND_URL = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
    ? ''
    : 'https://zomato-recommender-backend.up.railway.app'; // Replace with your Railway public domain

// Examples of updated fetch calls:
fetch(`${BACKEND_URL}/api/v1/cities`)
fetch(`${BACKEND_URL}/api/v1/recommendations`, { ... })
```

### 2.2 Step-by-Step Vercel Setup (With Env Variables Support)
Since the React SPA is a single static HTML file (`index.html`) inside the `StitchUIDesign` folder, we can configure Vercel to serve it and dynamically inject your Railway backend domain name using environment variables:

1. In the root of the project, ensure `vercel.json` exists to route requests to the static page:
   ```json
   {
     "cleanUrls": true,
     "rewrites": [
       { "source": "/(.*)", "destination": "/StitchUIDesign/index.html" }
     ]
   }
   ```
2. Log in to [Vercel](https://vercel.com/).
3. Click **Add New** -> **Project** and select your GitHub repository.
4. Set the **Root Directory** as `./` (project root).
5. Open the **Environment Variables** section and configure your Railway backend URL:
   - **Key**: `BACKEND_URL`
   - **Value**: `https://zomato-recommender-backend.up.railway.app` *(Your actual Railway service URL)*
6. In **Build and Development Settings**, customize the **Build Command** to execute the compiler injector script:
   - Toggle **Build Command** to override
   - Set value to: `node scripts/build-frontend.js`
7. Click **Deploy**.
8. Vercel will run the injector script to replace the default production URL in `StitchUIDesign/index.html` with your custom `BACKEND_URL` value, host your app, and generate a public domain (e.g. `https://zomato-recommender.vercel.app`).

---

## 3. CORS and Security Configuration

- **CORS Support**: The backend `StitchUIDesign/server.py` is pre-configured with `CORSMiddleware` allowing `allow_origins=["*"]`. This guarantees that the Vercel frontend domain can successfully request cities and recommendations from the Railway API.
- **Secrets Protection**: `GROQ_API_KEY` is loaded from the environment on Railway and is never exposed to the client browser. All LLM communications are handled server-side.
