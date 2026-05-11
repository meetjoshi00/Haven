# Setup Guide

## Windows setup

**Python 3.11.9**
python.org/downloads/release/python-3119/ — 64-bit installer.
Check: Add to PATH, Install pip, Install for all users.
Verify: `python --version` → Python 3.11.9

**C++ Build Tools (REQUIRED before pip installs)**
visualstudio.microsoft.com/visual-cpp-build-tools/
Select "Desktop development with C++" workload (~4GB).
Needed for: sentence-transformers, scipy, NeuroKit2.

**Node 18 via nvm-windows**
github.com/coreybutler/nvm-windows → `nvm install 18 && nvm use 18`

**Git** — git-scm.com/download/win

**Venv**
```powershell
python -m venv .venv
.venv\Scripts\activate
pip install --upgrade pip wheel setuptools
```

---

## Environment variables

```bash
# LLM
GROQ_API_KEY=
GOOGLE_AI_API_KEY=

# Supabase
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_ANON_KEY=
SUPABASE_SERVICE_ROLE_KEY=          # backend only — never expose to client

# LangSmith
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=
LANGCHAIN_PROJECT=asd-coaching-layer3

# Redis (Upstash)
UPSTASH_REDIS_REST_URL=
UPSTASH_REDIS_REST_TOKEN=

# App
NEXT_PUBLIC_APP_URL=http://localhost:3000
API_URL=http://localhost:8000

# Sentry
NEXT_PUBLIC_SENTRY_DSN=
SENTRY_DSN=
```

---

## Python requirements (apps/api/requirements.txt)

```
fastapi==0.111.0
uvicorn[standard]==0.29.0
pydantic==2.7.0
python-dotenv==1.0.1

# LangChain
langchain==0.2.0
langchain-groq==0.1.4
langchain-google-genai==1.0.3
langchain-community==0.2.0
langsmith==0.1.57

# Vector + embeddings
pgvector==0.2.5
sentence-transformers==2.7.0
supabase==2.4.3

# Utilities
pyyaml==6.0.1
httpx==0.27.0
python-frontmatter==1.1.0

# ML — install only when building Layer 1
# xgboost==2.0.3
# onnxruntime==1.17.3
# neurokit2==0.2.9
# imbalanced-learn==0.12.2
# shap==0.45.0
# scikit-learn==1.4.2
# pandas==2.2.2
# numpy==1.26.4
# pyarrow==16.0.0
```

**Install order (critical on Windows):**
```powershell
pip install --upgrade pip wheel setuptools
pip install numpy==1.26.4
pip install scipy
pip install -r requirements.txt
```

---

## L1 ML pipeline requirements (ml/requirements.txt)

Install separately from the API — only needed when building L1.

```powershell
pip install numpy==1.26.4    # must precede all others
pip install scipy
pip install -r ml/requirements.txt
```

Key packages and gotchas:
- `cvxopt` — cvxEDA decomposition optimizer; requires C++ Build Tools (same as NeuroKit2)
- `neurokit2` — physiological signal processing; depends on scipy
- `polars` + `pyarrow` — columnar data pipeline; no numpy dependency issues
- `mlflow` — experiment tracking; installs a local SQLite backend by default
- `skl2onnx` — sklearn → ONNX export; version must match `onnx` version

---

## Windows gotchas
- sentence-transformers downloads ~80MB model on first run
- NeuroKit2 needs scipy which needs C++ Build Tools
- ONNX Runtime: `pip install onnxruntime` (not onnxruntime-gpu)
- Redis: Upstash cloud only — no local Redis
- All Python paths: pathlib.Path, never os.path string concat
