#!/usr/bin/env python3
"""
Test script to verify semantic search fallback behavior.
"""
import sys
import time
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))

from mvp_bot.backend import (
    buscar_productos_semanticos,
    _embedder_ready,
)


def test_fallback_when_not_ready():
    """Test que buscar_productos_semanticos retorna [] cuando embedder no está listo."""
    print("[Test] Verificando fallback cuando embedder no está listo...")
    
    # Primero asegurarse de que no está pre-cargado
    from mvp_bot import backend
    backend._embedder_ready = False
    backend._embedder = None
    
    result = buscar_productos_semanticos("tubos puri")
    
    if result == []:
        print("[Test] ✓ Fallback correcto: retornó []")
        return True
    else:
        print(f"[Test] ✗ Fallback incorrecto: retornó {result}")
        return False


def test_search_when_ready():
    """Test que buscar_productos_semanticos funciona cuando embedder está listo."""
    print("[Test] Verificando búsqueda cuando embedder está listo...")
    
    # Pre-cargar embedder
    from mvp_bot.backend import precargar_embedder
    precargar_embedder()
    
    # Simular una búsqueda (puede retornar [] si no hay DB o no hay resultados)
    result = buscar_productos_semanticos("tubos co2")
    
    # La búsqueda debe completarse sin error
    print(f"[Test] ✓ Búsqueda completada sin error: {len(result)} resultados")
    return True


if __name__ == "__main__":
    test1 = test_fallback_when_not_ready()
    test2 = test_search_when_ready()
    
    success = test1 and test2
    sys.exit(0 if success else 1)
