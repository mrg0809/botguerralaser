# Deployment Guide: Embedder Fix

## What Changed
The bot was timing out on the first webhook message due to synchronous embedder loading. This has been fixed by pre-loading the e5-small model at app startup in a background thread.

## Pre-Deployment Checklist

- [ ] Python 3.12.3+ is installed
- [ ] Virtual environment is activated
- [ ] Dependencies are installed: `pip install -r requirements.txt`
- [ ] ChromaDB index exists: `ls -la mvp_bot/chroma_db/` (should have files)
- [ ] Contexto files exist:
  - [ ] `mvp_bot/Contexto_tienda.txt`
  - [ ] `mvp_bot/contexto_bot.jsonl` (3440+ lines)
- [ ] Environment variables set: `FB_PAGE_ACCESS_TOKEN`, `FB_VERIFY_TOKEN`, `GROQ_API_KEY`

## Deployment Steps

### 1. Verify Changes
```bash
# Check embedder pre-loader is in backend.py
grep -n "def precargar_embedder" mvp_bot/backend.py

# Check import and thread start in mvp_bot.py
grep -n "precargar_embedder" mvp_bot/mvp_bot.py
```

Expected output:
```
mvp_bot/backend.py:63:def precargar_embedder():
mvp_bot/mvp_bot.py:14:    precargar_embedder,
mvp_bot/mvp_bot.py:249:embedder_thread = threading.Thread(target=precargar_embedder, daemon=True)
```

### 2. Run Tests (Optional)
```bash
# Quick embedder load test
python test_embedder_load.py

# Comprehensive test suite
python test_comprehensive.py
```

Expected: All tests pass ✓

### 3. Start the Bot
```bash
reflex run
```

### 4. Monitor Startup Logs
Look for these messages (in order):
```
[Init] Iniciando pre-carga de embedder en background...
[Init] Pre-cargando modelo de embeddings: intfloat/e5-small...
... (Reflex startup continues in parallel)
[Init] ✓ Modelo cargado exitosamente
```

The app should be ready to handle webhooks **immediately**, even if embedder is still loading.

### 5. Test First Message
Send a webhook message (e.g., from Facebook or test script):
```
"tienes tubos puri en venta?"
```

Expected responses (depending on timing):
- **If embedder ready:** Chroma semantic search results + MercadoLibre links
- **If embedder still loading:** Category links from fallback heuristic
- **In both cases:** ✓ Response arrives without timeout

### 6. Verify in Logs
Check that you see:
```
[Webhook] Procesando mensaje...
[GROQ] Cargando contexto...
[Chroma] Iniciando búsqueda semántica...  (or fallback message)
[Webhook] Respuesta enviada exitosamente
```

**NOT** these error messages:
```
[WARNING] Killing worker-0 after it refused to gracefully stop
RuntimeError: Embedder no está inicializado
```

## Rollback (if needed)
If you need to rollback to the previous version:

```bash
git revert HEAD
reflex run
```

This will restore the old lazy-loading behavior (but bot will still timeout on first message).

## Performance Expectations

| Metric | Value |
|--------|-------|
| App startup time | +2-3 seconds (embedder loads in background) |
| First webhook response time | ~1-2 seconds (Groq API call) |
| Subsequent webhook response time | ~1-2 seconds (same) |
| Memory overhead | ~100MB (for embedder, loaded once) |

## Troubleshooting

### Problem: Embedder loads but takes very long
**Symptom:** Logs show `[Init] Pre-cargando...` but `✓ Modelo cargado` takes >10 seconds

**Solution:**
1. Check disk space: `df -h`
2. Check network (first time downloads model): `ping huggingface.co`
3. Increase timeout if needed (edit `test_comprehensive.py`: `timeout=60`)

### Problem: Bot still times out on first message
**Symptom:** `[WARNING] Killing worker-0...` still appears

**Solution:**
1. Verify embedder is starting: `grep "\[Init\]" reflex.log`
2. If missing, check import in `mvp_bot/mvp_bot.py` line 14
3. Check `threading` module is available: `python -c "import threading; print('OK')"`

### Problem: Fallback returns empty results
**Symptom:** First message returns "ESCALATE" or no products

**Solution:**
1. This is expected if embedder is loading and legacy heuristic doesn't match
2. Wait 5 seconds and send same message again (embedder will be ready)
3. If still fails, check `Contexto_tienda.txt` has categories:
   ```bash
   grep "CATEGORÍA:" mvp_bot/Contexto_tienda.txt | head -5
   ```

### Problem: Python module not found
**Symptom:** `ModuleNotFoundError: No module named 'sentence_transformers'`

**Solution:**
```bash
pip install -r requirements.txt
pip install sentence-transformers>=3.0.1
```

## Monitoring in Production

### Enable detailed logging
Add to `mvp_bot/backend.py` after imports:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Key metrics to monitor
- `[Init]` logs at startup (confirms pre-loading started)
- `[Chroma]` logs on each webhook (confirms queries working)
- `[GROQ]` logs for each response (confirms API calls succeeding)
- Worker timeouts: `grep "Killing worker" reflex.log` (should be zero)

## Success Criteria

✅ Bot starts without errors
✅ First webhook message gets response (no timeout)
✅ Response includes MercadoLibre links or categories
✅ Logs show `[Init] ✓ Modelo cargado exitosamente`
✅ No worker timeout messages in logs
✅ Subsequent messages respond quickly

## Support

For issues, check:
1. `mvp_bot/backend.py` lines 63-89 (embedder functions)
2. `mvp_bot/mvp_bot.py` lines 244-250 (startup initialization)
3. Test logs: `python test_comprehensive.py`

Or review `EMBEDDER_FIX.md` for detailed technical explanation.
