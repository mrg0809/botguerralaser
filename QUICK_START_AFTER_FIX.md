# Quick Start After Embedder Fix

## What's Fixed?
✅ Bot no longer times out on first webhook message
✅ Embedder pre-loads at startup in background
✅ Fallback to categories if embedder still loading

## To Start the Bot

```bash
cd /home/rm/Desarrollo/botguerralaser
reflex run
```

### Expected Startup Output
```
[Init] Iniciando pre-carga de embedder en background...
[Init] Pre-cargando modelo de embeddings: intfloat/e5-small...
... (Reflex loads normally) ...
[Init] ✓ Modelo cargado exitosamente
```

**Important:** App is ready to handle webhooks **immediately**, even while embedder is still loading.

## Send a Test Message

Using Facebook Messenger, test webhook, or your client:
```
"tienes tubos puri en venta?"
```

### Expected Response (One of These)
1. **If embedder ready (after ~2-3s):** 
   - Semantic search results
   - MercadoLibre product links
   - Specific product details

2. **If sent very quickly (before embedder ready):**
   - Category suggestions
   - Category links
   - Still helpful, no timeout

3. **Never (should not happen):**
   - ❌ Timeout error
   - ❌ Worker killed message
   - ❌ Blank response

## If Something's Wrong

### Issue: "Killing worker" message still appears
```bash
# Check embedder is starting
grep "\[Init\]" reflex.log | head -5

# Check it loaded successfully  
grep "\[Init\] ✓" reflex.log
```

### Issue: First message times out
```bash
# Verify embedder is in code
grep -n "precargar_embedder" mvp_bot/mvp_bot.py

# Run test to verify fix is working
python test_comprehensive.py
```

### Issue: Bot responds but with no products
- Likely embedder still loading (normal within first 3 seconds)
- Wait 5 seconds and try again
- Should then get products via Chroma

## Test the Fix

```bash
# Fast test: embedder loads in background
python test_embedder_load.py

# Medium test: fallback works correctly
python test_fallback.py

# Full test: production simulation
python test_comprehensive.py
```

All tests should pass ✓

## Key Files Changed

- `mvp_bot/backend.py` - Added embedder pre-loader
- `mvp_bot/mvp_bot.py` - Start pre-loader at startup

## Documentation

- `EMBEDDER_FIX.md` - Technical details
- `DEPLOYMENT_GUIDE.md` - Full deployment steps
- `CHANGELOG_EMBEDDER_FIX.md` - What changed
- `FIX_SUMMARY.md` - Quick summary

## Support

If bot still doesn't work:
1. Check `DEPLOYMENT_GUIDE.md` troubleshooting section
2. Run `python test_comprehensive.py` to diagnose
3. Review `mvp_bot/backend.py` lines 63-89 (new code)

---

**Status:** ✅ PRODUCTION READY - No more worker timeouts!
