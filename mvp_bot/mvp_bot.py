"""
MVP Bot - Aplicación principal con Reflex.
"""
import reflex as rx
from typing import List, Dict
import asyncio
from datetime import datetime

from .backend import (
    verify_webhook,
    parse_webhook_payload,
    process_incoming_message,
    get_message_buffer,
    precargar_embedder,
)


class State(rx.State):
    """Estado de la aplicación."""
    
    chat_history: List[Dict[str, str]] = []
    
    def add_message(self, sender: str, message: str, escalated: bool = False):
        """Añade un mensaje al historial de chat."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        message_entry = {
            "timestamp": timestamp,
            "sender": sender,
            "message": message,
            "escalated": escalated
        }
        
        self.chat_history.append(message_entry)
    
    def clear_history(self):
        """Limpia el historial de chat."""
        self.chat_history = []

    async def refresh_messages(self):
        """Carga el buffer de mensajes acumulados en backend."""
        # El backend expone un endpoint para consulta; aquí se llama al
        # mismo proceso para evitar dependencias externas.
        self.chat_history = get_message_buffer()


def index() -> rx.Component:
    """Página principal con el visor de mensajes."""
    return rx.container(
        rx.vstack(
                        # Auto-refresh cada 3s para simular chat en vivo (JS fallback)
                        rx.script(
                                """
                                (() => {
                                    const clickRefresh = () => {
                                        const btn = document.getElementById("refresh-btn");
                                        if (!btn) {
                                            console.debug("[auto-refresh] botón no encontrado aún");
                                            return false;
                                        }
                                        try {
                                            btn.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true, view: window}));
                                            return true;
                                        } catch (e) {
                                            console.debug("[auto-refresh] error al disparar click", e);
                                            return false;
                                        }
                                    };

                                    const start = () => {
                                        // primer intento inmediato tras carga
                                        setTimeout(() => {
                                            if (!clickRefresh()) {
                                                console.debug("[auto-refresh] primer intento falló");
                                            }
                                        }, 300);

                                        // intervalo de polling
                                        setInterval(() => {
                                            if (!clickRefresh()) {
                                                // mantener log leve
                                                console.debug("[auto-refresh] esperando al botón");
                                            }
                                        }, 3000);
                                    };

                                    if (document.readyState === 'complete') {
                                        start();
                                    } else {
                                        window.addEventListener('load', start, { once: true });
                                    }
                                })();
                                """
                        ),

            rx.heading(
                "🤖 Bot Guerra Láser - Monitor de Mensajes",
                size="9",
                margin_bottom="1rem"
            ),
            rx.text(
                "Estado: Esperando mensajes de Facebook Messenger...",
                color="gray",
                margin_bottom="2rem"
            ),

            rx.button(
                "🔄 Refrescar",
                on_click=State.refresh_messages,
                color_scheme="blue",
                variant="soft",
                margin_bottom="1rem",
                id="refresh-btn"
            ),
            
            # Botón para limpiar historial
            rx.button(
                "🗑️ Limpiar Historial",
                on_click=State.clear_history,
                color_scheme="red",
                variant="soft",
                margin_bottom="1rem"
            ),
            
            # Contenedor de mensajes
            rx.box(
                rx.cond(
                    State.chat_history.length() > 0,
                    rx.vstack(
                        rx.foreach(
                            State.chat_history,
                            lambda msg: message_card(msg)
                        ),
                        spacing="4",
                        width="100%",
                    ),
                    rx.text(
                        "No hay mensajes aún. Los mensajes aparecerán aquí cuando lleguen desde Facebook Messenger.",
                        color="gray",
                        font_style="italic"
                    )
                ),
                padding="2rem",
                border_radius="lg",
                border="1px solid #e2e8f0",
                background="white",
                min_height="400px",
                max_height="600px",
                overflow_y="auto",
                width="100%",
            ),
            
            # Información del webhook
            rx.divider(margin_y="2rem"),
            rx.box(
                rx.heading("📡 Información del Webhook", size="7", margin_bottom="1rem", color="#e2e8f0"),
                rx.text(
                    "Endpoint de verificación (GET): /webhook",
                    margin_bottom="0.5rem",
                    color="#e2e8f0"
                ),
                rx.text(
                    "Endpoint de mensajes (POST): /webhook",
                    margin_bottom="0.5rem",
                    color="#e2e8f0"
                ),
                rx.text(
                    "Los mensajes se actualizarán automáticamente en tiempo real.",
                    color="#86efac",
                    font_weight="bold"
                ),
                padding="1rem",
                border_radius="md",
                background="#0f172a",
                border="1px solid #1f2937",
            ),
            
            spacing="4",
            width="100%",
            max_width="1200px",
        ),
        padding="2rem",
    )


def message_card(msg: Dict) -> rx.Component:
    """Componente para mostrar un mensaje individual."""
    return rx.box(
        rx.hstack(
            rx.text(
                msg["timestamp"],
                font_size="0.8rem",
                color=rx.cond(
                    msg["sender"] == "Usuario",
                    "#e2e8f0",
                    "#e2e8f0"
                ),
                font_weight="bold",
            ),
            rx.badge(
                msg["sender"],
                color_scheme=rx.cond(
                    msg["sender"] == "Usuario",
                    "blue",
                    "green"
                ),
            ),
            rx.cond(
                msg["escalated"],
                rx.badge("⚠️ ESCALADO", color_scheme="orange"),
                rx.fragment(),
            ),
            spacing="2",
        ),
        rx.text(
            msg["message"],
            margin_top="0.5rem",
            color=rx.cond(
                msg["sender"] == "Usuario",
                "#f8fafc",
                "#f8fafc"
            ),
            line_height="1.6",
        ),
        padding="1rem",
        border_radius="md",
        background=rx.cond(
            msg["sender"] == "Usuario",
            "#1e3a8a",  # azul oscuro para alto contraste
            "#0f766e"   # verde oscuro para alto contraste
        ),
        border_left=rx.cond(
            msg["sender"] == "Usuario",
            "4px solid #60a5fa",
            "4px solid #34d399"
        ),
        width="100%",
    )


# Crear la app
app = rx.App()
app.add_page(index, route="/", on_load=State.refresh_messages)

# Pre-cargar el modelo de embeddings en background para evitar timeout
# en la primera petición del webhook
print("[Init] Iniciando pre-carga de embedder en background...")
import threading
embedder_thread = threading.Thread(target=precargar_embedder, daemon=True)
embedder_thread.start()


# ==================== API ENDPOINTS ====================

@app._api.route("/webhook", methods=["GET"])
async def webhook_verify(request):
    """
    Endpoint GET para verificación de webhook de Facebook.
    """
    hub_mode = request.query_params.get("hub.mode", "")
    hub_verify_token = request.query_params.get("hub.verify_token", "")
    hub_challenge = request.query_params.get("hub.challenge", "")
    
    print(f"Verificación de webhook recibida: mode={hub_mode}, token={hub_verify_token}")
    
    challenge_response = verify_webhook(hub_mode, hub_verify_token, hub_challenge)
    
    if challenge_response is not None:
        print("✅ Verificación exitosa")
        from starlette.responses import PlainTextResponse
        return PlainTextResponse(str(challenge_response))
    else:
        print("❌ Verificación fallida")
        from starlette.responses import JSONResponse
        return JSONResponse({"error": "Verification failed"}, status_code=403)


@app._api.route("/webhook", methods=["POST"])
async def webhook_post(request):
    """
    Endpoint POST para recibir mensajes de Facebook Messenger.
    """
    import json
    data = await request.json()
    print(f"Webhook POST recibido: {data}")
    
    # Parsear los mensajes del payload
    messages = parse_webhook_payload(data)
    
    if not messages:
        print("No se encontraron mensajes en el payload")
        from starlette.responses import JSONResponse
        return JSONResponse({"status": "ok"})
    
    # Procesar cada mensaje
    for sender_id, message_text in messages:
        print(f"Procesando mensaje de {sender_id}: {message_text}")

        # Procesar el mensaje (Groq + respuesta)
        result = await process_incoming_message(sender_id, message_text)

        # Nota: No actualizamos el estado compartido aquí porque no existe
        # un token de sesión (los webhooks vienen sin sesión de Reflex). Si
        # se necesita reflejar estos mensajes en la UI en tiempo real, se
        # debe implementar un canal separado (por ejemplo, websocket/broadcast)
        # o exponer un endpoint que el frontend consulte.

        print(f"Resultado: {result}")
    
    from starlette.responses import JSONResponse
    return JSONResponse({"status": "ok"})


# Endpoint simple para que el frontend consulte los mensajes acumulados
@app._api.route("/api/messages", methods=["GET"])
async def api_messages(request):
    from starlette.responses import JSONResponse
    return JSONResponse({"messages": get_message_buffer()})
