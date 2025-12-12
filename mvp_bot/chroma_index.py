"""Script para indexar contexto_bot.jsonl en Chroma local.

Uso:
    python -m mvp_bot.chroma_index

Crea/actualiza la colección "productos" en el directorio persistente `chroma_db/`.
"""
import json
import os
from typing import List, Dict, Any

import chromadb
from sentence_transformers import SentenceTransformer

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
JSONL_PATH = os.path.join(BASE_DIR, "contexto_bot.jsonl")
DB_DIR = os.path.join(BASE_DIR, "chroma_db")
COLLECTION_NAME = "productos"
MODEL_NAME = "intfloat/e5-small"  # suficiente para catálogo


def generar_link_mercadolibre(product_id: str) -> str:
    """Genera el link directo a un producto de MercadoLibre."""
    if not product_id or not product_id.startswith("MLM"):
        return ""
    return f"https://articulo.mercadolibre.com.mx/MLM-{product_id[3:]}"  # inserta guion después de MLM


def cargar_productos() -> List[Dict[str, Any]]:
    productos: List[Dict[str, Any]] = []
    if not os.path.exists(JSONL_PATH):
        raise FileNotFoundError(f"No se encontró {JSONL_PATH}")
    with open(JSONL_PATH, "r", encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()
            if not linea:
                continue
            try:
                producto = json.loads(linea)
                productos.append(producto)
            except json.JSONDecodeError:
                continue
    return productos


def build_texto_busqueda(prod: Dict[str, Any]) -> str:
    detalles = prod.get("detalles", {}) if isinstance(prod.get("detalles"), dict) else {}
    partes = [
        detalles.get("TITLE", ""),
        prod.get("categoria", ""),
        detalles.get("BRAND", ""),
        detalles.get("MODEL", ""),
    ]
    # concatenar resto de detalles como texto
    try:
        partes.append(json.dumps(detalles, ensure_ascii=False))
    except Exception:
        pass
    return " \n ".join([p for p in partes if p])


def main() -> None:
    productos = cargar_productos()
    if not productos:
        print("No hay productos para indexar")
        return

    embedder = SentenceTransformer(MODEL_NAME)
    client = chromadb.PersistentClient(path=DB_DIR)
    collection = client.get_or_create_collection(COLLECTION_NAME)

    ids: List[str] = []
    docs: List[str] = []
    metas: List[Dict[str, Any]] = []

    seen = set()
    for p in productos:
        pid = p.get("id") or p.get("detalles", {}).get("ID")
        if not pid:
            continue
        pid = str(pid)
        if pid in seen:
            continue
        seen.add(pid)

        detalles = p.get("detalles", {}) if isinstance(p.get("detalles"), dict) else {}
        link = generar_link_mercadolibre(pid)

        ids.append(pid)
        docs.append(build_texto_busqueda(p))
        metas.append({
            "id": pid,
            "titulo": detalles.get("TITLE", ""),
            "categoria": p.get("categoria", ""),
            "marca": detalles.get("BRAND", ""),
            "modelo": detalles.get("MODEL", ""),
            "precio": p.get("precio", ""),
            "link_mercadolibre": link,
            **{k: v for k, v in detalles.items() if isinstance(k, str)}
        })

    embeddings = embedder.encode(docs, convert_to_numpy=True).tolist()
    collection.upsert(ids=ids, documents=docs, embeddings=embeddings, metadatas=metas)
    print(f"Indexado listo: {len(ids)} productos en {DB_DIR}")


if __name__ == "__main__":
    main()
