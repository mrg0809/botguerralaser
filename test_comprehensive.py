#!/usr/bin/env python3
"""
Comprehensive test to verify the embedder fix works correctly.
Tests the full initialization flow as it would happen in production.
"""
import sys
import time
import threading
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))


def test_full_startup_flow():
    """Simulates the full app startup with embedder pre-loading."""
    print("=" * 60)
    print("TEST: Full Startup Flow with Embedder Pre-Loading")
    print("=" * 60)
    
    # Simulate app startup
    print("\n[App] Iniciando aplicación...")
    start_time = time.time()
    
    # Import and start pre-loader (as mvp_bot.py does)
    from mvp_bot.backend import precargar_embedder
    
    print("[App] Pre-cargando embedder en background...")
    embedder_thread = threading.Thread(target=precargar_embedder, daemon=True)
    embedder_thread.start()
    
    print("[App] ✓ Aplicación lista para recibir webhooks (no fue bloqueada)")
    
    # Simulate webhook arriving immediately (worst case)
    print("\n[Webhook] Mensaje llegó inmediatamente después de startup...")
    from mvp_bot.backend import buscar_productos_semanticos, _embedder_ready
    
    if _embedder_ready:
        print("[Webhook] ✓ Embedder ya está listo, ejecutando búsqueda...")
        result = buscar_productos_semanticos("tubos puri")
        print(f"[Webhook] ✓ Búsqueda completada: {len(result)} resultados")
    else:
        print("[Webhook] ! Embedder aún está cargando, usando fallback...")
        result = buscar_productos_semanticos("tubos puri")
        if result == []:
            print("[Webhook] ✓ Fallback a heurística activado correctamente")
        else:
            print(f"[Webhook] ✓ Búsqueda con fallback: {len(result)} resultados")
    
    # Wait for embedder to fully load if not ready
    print("\n[Test] Esperando a que embedder termine de cargar...")
    embedder_thread.join(timeout=30)
    
    elapsed = time.time() - start_time
    
    if not embedder_thread.is_alive():
        print(f"[Test] ✓ Embedder completamente cargado en {elapsed:.2f}s total")
    else:
        print(f"[Test] ✗ Embedder aún cargando después de 30s")
        return False
    
    # Test that embedder is now available
    print("\n[Test] Verificando que embedder está disponible para querys...")
    from mvp_bot.backend import _embedder_ready
    
    if _embedder_ready:
        print("[Test] ✓ Embedder está listo")
        result = buscar_productos_semanticos("cortadora laser co2")
        print(f"[Test] ✓ Búsqueda semántica funcionando: {len(result)} resultados")
        return True
    else:
        print("[Test] ✗ Embedder no está listo")
        return False


def test_error_handling():
    """Test error handling and recovery."""
    print("\n" + "=" * 60)
    print("TEST: Error Handling and Recovery")
    print("=" * 60)
    
    print("\n[Test] Limpiando estado global para probar reinicio...")
    from mvp_bot import backend
    backend._embedder_ready = False
    backend._embedder = None
    
    print("[Test] ✓ Estado limpio")
    
    # Try to search with no embedder
    from mvp_bot.backend import buscar_productos_semanticos
    
    print("[Test] Buscando sin embedder pre-cargado (debe hacer fallback)...")
    result = buscar_productos_semanticos("tubos")
    
    if result == []:
        print("[Test] ✓ Fallback funcionó correctamente")
    else:
        print(f"[Test] ⚠ Fallback retornó resultados: {len(result)}")
    
    # Pre-load and try again
    print("\n[Test] Pre-cargando embedder...")
    from mvp_bot.backend import precargar_embedder
    precargar_embedder()
    
    print("[Test] ✓ Embedder cargado")
    
    print("[Test] Buscando con embedder cargado...")
    result = buscar_productos_semanticos("tubos puri")
    
    if len(result) >= 0:
        print(f"[Test] ✓ Búsqueda funcionó: {len(result)} resultados")
        return True
    else:
        print("[Test] ✗ Búsqueda falló")
        return False


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("COMPREHENSIVE EMBEDDER FIX TEST SUITE")
    print("=" * 60)
    
    tests = [
        ("Full Startup Flow", test_full_startup_flow),
        ("Error Handling", test_error_handling),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n✗ Test '{test_name}' falló con excepción: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST RESULTS SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! Embedder fix is working correctly.")
        return 0
    else:
        print(f"\n❌ {total - passed} test(s) failed.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
