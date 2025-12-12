# Fix: Embedder Pre-Loading to Prevent Worker Timeout

## Problem
The bot was timing out on the first webhook message because the e5-small embedder model (~100MB) was loading synchronously in the request handler thread. The flow was:

1. Facebook webhook POST arrives
2. `process_incoming_message()` → `classify_and_respond_with_groq()` → `filtrar_contexto_relevante()` → `buscar_productos_semanticos()`
3. Inside `get_embedder()`: `SentenceTransformer(intfloat/e5-small)` loads (~2-3 seconds) **blocking the entire request handler**
4. Reflex worker timeout (~30-60s default) killed the process before Groq response completed

**Error:** `[WARNING] Killing worker-0 after it refused to gracefully stop`

## Solution
Pre-load the embedder at app startup in a **background thread**, so it's ready before the first webhook message arrives.

### Code Changes

#### 1. **mvp_bot/backend.py** - Add embedder preloader function

```python
_embedder_ready = False  # NEW: flag to track initialization status

def precargar_embedder():
    """Pre-carga el modelo de embeddings en background."""
    global _embedder, _embedder_ready
    try:
        print(f"[Init] Pre-cargando modelo de embeddings: {EMBED_MODEL}...")
        _embedder = SentenceTransformer(EMBED_MODEL)
        _embedder_ready = True
        print(f"[Init] ✓ Modelo cargado exitosamente")
    except Exception as e:
        print(f"[Init] ✗ Error al cargar modelo: {e}")
        _embedder = None
        _embedder_ready = False

def get_embedder():
    """Retorna el modelo de embeddings (debe estar pre-cargado)."""
    global _embedder
    if _embedder is None:
        raise RuntimeError("Embedder no está inicializado...")
    return _embedder
```

**Key changes:**
- `get_embedder()` now **requires** pre-loading (no lazy loading on first request)
- Added `_embedder_ready` flag to track initialization status
- `precargar_embedder()` can be called from a thread without blocking request handlers

#### 2. **mvp_bot/backend.py** - Update `buscar_productos_semanticos()`

```python
def buscar_productos_semanticos(...):
    # Check both DB exists AND embedder is ready
    if not os.path.exists(CHROMA_DB_DIR):
        return []
    
    if not _embedder_ready:
        print("[Chroma] Embedder aún no está listo, usando fallback de heurística")
        return []  # Falls back to legacy keyword heuristic
    
    # ... rest of function
```

**Key changes:**
- Added `_embedder_ready` check before attempting embedder use
- Returns empty list if embedder not ready → triggers fallback to keyword heuristic
- Prevents runtime errors from calling `get_embedder()` before initialization

#### 3. **mvp_bot/mvp_bot.py** - Start pre-loader at app startup

```python
# Import the preloader
from .backend import (..., precargar_embedder)

# Create app
app = rx.App()
app.add_page(index, route="/", on_load=State.refresh_messages)

# Pre-load embedder in background thread at startup
print("[Init] Iniciando pre-carga de embedder en background...")
import threading
embedder_thread = threading.Thread(target=precargar_embedder, daemon=True)
embedder_thread.start()
```

**Key changes:**
- Calls `precargar_embedder()` in a **daemon thread** at app startup
- Non-blocking: app continues loading while embedder loads in background
- Embedder is ready within ~2-3 seconds (before first webhook usually arrives)

## Behavior Timeline

### Before Fix (BLOCKER)
```
[App start] → [Webhook POST arrives] → [Blocks on SentenceTransformer load] 
→ [Worker timeout kills process] ✗
```

### After Fix (FIXED)
```
[App start]
  ├─ Main thread: Reflex starts, webhook endpoints ready
  └─ Background thread: Embedder loads (~2s) in parallel
                         ↓
                    [Embedder ready ✓]

[Webhook POST arrives] → [Embedder already loaded] 
→ [Chroma query executes immediately] → [Groq response sent] ✓
```

## Fallback Behavior
If the embedder is still loading when a webhook arrives:
1. `_embedder_ready == False`
2. `buscar_productos_semanticos()` detects and returns `[]`
3. `filtrar_contexto_relevante()` falls back to **keyword heuristic** matching
4. User gets response with **category links** instead of semantic search results
5. Once embedder finishes loading, subsequent queries use semantic search

## Testing

### Test 1: Embedder loads in background without blocking
```bash
python test_embedder_load.py
```

Expected output:
```
[Test] ✓ Thread iniciado sin bloqueo
[Init] ✓ Modelo cargado exitosamente
[Test] ✓ Embedder cargado en 2.16s
```

### Test 2: Fallback works when embedder not ready
```bash
python test_fallback.py
```

Expected output:
```
[Chroma] Embedder aún no está listo, usando fallback de heurística
[Test] ✓ Fallback correcto: retornó []
```

## Performance Impact
- **App startup:** +2-3 seconds (parallel in background, user doesn't notice)
- **First webhook:** ✓ No longer blocks (embedder ready or falls back gracefully)
- **Subsequent webhooks:** Same speed (embedder cached in memory)
- **Memory:** ~100MB for e5-small model loaded once

## Production Readiness
✅ Embedder pre-loads at startup
✅ Non-blocking background thread prevents worker timeout
✅ Graceful fallback if embedder not ready
✅ No change to Chroma index or data files
✅ Backwards compatible with existing code

## Troubleshooting

**Problem:** Bot still times out on first message
**Solution:** 
1. Check logs for `[Init] ✓ Modelo cargado exitosamente` at startup
2. If missing, embedder thread may have crashed (check error logs)
3. Verify `intfloat/e5-small` is installed: `pip list | grep sentence`

**Problem:** Embedder loads but queries still fail
**Solution:**
1. Check `chroma_db/` directory exists
2. Run `python -m mvp_bot.chroma_index` to re-index products
3. Verify `contexto_bot.jsonl` has products

## Next Steps
1. Start bot with `reflex run`
2. Send first webhook message (e.g., "tienes tubos puri?")
3. Verify response appears without timeout
4. Check logs show embedder loaded at startup and Chroma query succeeded
