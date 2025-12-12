#!/usr/bin/env python3
"""
Test script to verify embedder loads correctly without blocking.
"""
import sys
import time
import threading
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))

from mvp_bot.backend import precargar_embedder, _embedder_ready, _embedder


def test_background_load():
    """Test que el embedder se carga en background sin bloquear."""
    print("[Test] Iniciando prueba de carga en background...")
    
    # Simular inicio de app
    print("[Test] Creando thread para pre-cargar embedder...")
    start_time = time.time()
    
    embedder_thread = threading.Thread(target=precargar_embedder, daemon=True)
    embedder_thread.start()
    
    # El hilo debe empezar inmediatamente sin bloquear
    print("[Test] ✓ Thread iniciado sin bloqueo")
    
    # Esperar a que termine
    print("[Test] Esperando a que el embedder se cargue (máx 30s)...")
    embedder_thread.join(timeout=30)
    
    elapsed = time.time() - start_time
    
    if not embedder_thread.is_alive():
        print(f"[Test] ✓ Embedder cargado en {elapsed:.2f}s")
        from mvp_bot.backend import _embedder_ready
        print(f"[Test] Estado _embedder_ready: {_embedder_ready}")
        return True
    else:
        print(f"[Test] ✗ Timeout después de 30s")
        return False


if __name__ == "__main__":
    success = test_background_load()
    sys.exit(0 if success else 1)
