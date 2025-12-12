# Guía Paso a Paso: Integrar Chroma Local

## Objetivo
Usar ChromaDB local para buscar productos semánticamente, evitar alucinaciones de links y mejorar relevancia.

## Arquitectura
- **Chroma local**: indexa `contexto_bot.jsonl` en `mvp_bot/chroma_db/` (persistente en disco).
- **Embeddings**: modelo `e5-small` (gratis, local, ~100MB).
- **Flujo**: consulta semántica con filtros por categoría → devuelve top‑7 productos con `link_mercadolibre` → Groq verbraliza.
- **Fallback**: si Chroma no está listo, usa heurística legacy; si nada, responde categorías o `ESCALATE`.

---

## Paso 1: Preparar entorno

```bash
cd /home/rm/Desarrollo/botguerralaser

# Opción A (automático - recomendado)
bash setup.sh

# Opción B (manual)
pip install chromadb sentence-transformers
python -m mvp_bot.chroma_index
```

**¿Qué pasa?**
- Instala `chromadb` (~50MB) y `sentence-transformers` (~500MB para e5-small).
- `chroma_index.py` lee `contexto_bot.jsonl`, genera embeddings y guarda en `mvp_bot/chroma_db/`.
- Primera vez tarda ~2-3 min (descarga modelo). Posteriores son instantáneas.

**Verificar:**
```bash
ls -la mvp_bot/chroma_db/
# Debe mostrar archivos de la DB (*.db, etc.)
```

---

## Paso 2: Ejecutar el bot

```bash
reflex run
# En otra terminal (si es necesario):
python -c "from mvp_bot.backend import cargar_contexto_completo; print(cargar_contexto_completo())"
```

**¿Qué pasa?**
- Backend carga Chroma al primer mensaje de usuario (lazy loading).
- Embedder e5-small se descarga/cachea (~100MB en memoria la primera vez).
- Posteriores consultas son rápidas (<100ms).

---

## Paso 3: Probar

### Consulta específica (usa Chroma)
```
Usuario: "tienes tubos puri en venta?"
Bot: [Busca en Chroma] 
     → Filtra por "tubo" + "puri"
     → Devuelve top 7 productos con link_mercadolibre
     → Groq verbaliza: "Sí, tenemos tubos Puri... [link]"
```

### Consulta genérica (usa categorías)
```
Usuario: "hola que vendes"
Bot: [Omite Chroma, genera categorías del TXT]
     → "Contamos con: CO2, Fibra, CNC, ... [links]"
```

### Sin Chroma inicializado (fallback)
```
Usuario: "quiero una máquina CO2 con chiller"
Bot: [Chroma no existe] → usa heurística keyword
     → Si hay match, devuelve producto + link
     → Si no, ofrece categoría o "ESCALATE"
```

---

## Paso 4: Actualizar catálogo

Si cambias `contexto_bot.jsonl`:
```bash
# Reindexa (borra índice viejo)
rm -rf mvp_bot/chroma_db/
python -m mvp_bot.chroma_index

# O reindexar sin borrar (upsert):
python -m mvp_bot.chroma_index  # por defecto hace upsert
```

---

## Paso 5: Optimizaciones (opcional)

### Cambiar modelo de embeddings
En `backend.py`, línea `EMBED_MODEL = "intfloat/e5-small"`:
- `e5-small`: rápido, 100MB, suficiente para catálogos normales.
- `e5-base`: más preciso, 500MB, más lento (solo si muchas variaciones).
- `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`: multiidioma, 500MB.

Cambiar y reindexar:
```bash
# edita backend.py
EMBED_MODEL = "intfloat/e5-base"

# reindexar
rm -rf mvp_bot/chroma_db/
python -m mvp_bot.chroma_index
```

### Top-k por defecto
En `filtrar_contexto_relevante()`, línea `buscar_productos_semanticos(..., top_k=7)`:
- Aumentar a 10-15 si consultas son genéricas/amplias.
- Bajar a 3-5 si quieres respuestas muy concisas.

### Filtros por categoría
En `filtrar_contexto_relevante()`, ajusta keywords para mapeos:
```python
if "tubo" in mensaje_lower:
    filtros_cat.append("tubo")  # busca en categoria que contenga "tubo"
```

---

## Troubleshooting

| Problema | Solución |
|----------|----------|
| "ModuleNotFoundError: chromadb" | `pip install chromadb sentence-transformers` |
| Chroma demora mucho la 1ª vez | Normal: descarga e5-small (~100MB). Posteriores <100ms. |
| "No se encuentra chroma_db" | Ejecuta `python -m mvp_bot.chroma_index` primero. |
| Bot responde genérico sin productos | Chroma sin match; usa heurística legacy o categorías. |
| Links siguen mal | Asegura que el JSONL tiene campo `id` con formato MLM... |
| Indexador error "KeyError: 'categoria'" | Algunos productos en JSONL pueden carecer de campo. OK—el script salta. |

---

## Resumen de archivos nuevos

- `mvp_bot/chroma_index.py`: script para indexar (ejecutar 1 sola vez o cuando cambie catálogo).
- `mvp_bot/chroma_db/`: carpeta generada (ignorar en Git).
- `setup.sh`: script auxiliar para instalación automática.
- `requirements.txt`: actualizado con `chromadb` + `sentence-transformers`.
- `mvp_bot/backend.py`: actualizado con funciones Chroma y fallback.

---

## Próximos pasos avanzados

1. **Caché de embeddings**: guarda embeddings + metadatos JSON para no recalcular.
2. **Filtros avanzados**: combina metadatos (precio, potencia, accesorios) con búsqueda semántica.
3. **Multiidioma**: usa `intfloat/multilingual-e5-base` si clientes preguntan en idiomas diferentes.
4. **Monitoreo**: log de queries no encontradas para mejorar categoría/producto.

---

¡Listo! El bot ahora usa Chroma para búsqueda inteligente sin alucinar links. 🚀
