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
    process_incoming_message
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


def index() -> rx.Component:
    """Página principal con el visor de mensajes."""
    return rx.container(
        rx.vstack(
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
                rx.heading("📡 Información del Webhook", size="7", margin_bottom="1rem"),
                rx.text(
                    "Endpoint de verificación (GET): /webhook",
                    margin_bottom="0.5rem"
                ),
                rx.text(
                    "Endpoint de mensajes (POST): /webhook",
                    margin_bottom="0.5rem"
                ),
                rx.text(
                    "Los mensajes se actualizarán automáticamente en tiempo real.",
                    color="green",
                    font_weight="bold"
                ),
                padding="1rem",
                border_radius="md",
                background="#f7fafc",
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
                color="gray",
                font_weight="bold",
            ),
            rx.badge(
                msg["sender"],
                color_scheme="blue" if msg["sender"] == "Usuario" else "green",
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
            line_height="1.6",
        ),
        padding="1rem",
        border_radius="md",
        background=rx.cond(
            msg["sender"] == "Usuario",
            "#e3f2fd",
            "#f1f8e9"
        ),
        border_left=rx.cond(
            msg["sender"] == "Usuario",
            "4px solid #2196f3",
            "4px solid #8bc34a"
        ),
        width="100%",
    )


# Crear la app
app = rx.App()
app.add_page(index, route="/")


# ==================== API ENDPOINTS ====================

@app.api.get("/webhook")
async def webhook_verify(hub_mode: str = "", hub_verify_token: str = "", hub_challenge: str = ""):
    """
    Endpoint GET para verificación de webhook de Facebook.
    """
    print(f"Verificación de webhook recibida: mode={hub_mode}, token={hub_verify_token}")
    
    challenge_response = verify_webhook(hub_mode, hub_verify_token, hub_challenge)
    
    if challenge_response is not None:
        print("✅ Verificación exitosa")
        return challenge_response
    else:
        print("❌ Verificación fallida")
        return {"error": "Verification failed"}, 403


@app.api.post("/webhook")
async def webhook_post(data: Dict):
    """
    Endpoint POST para recibir mensajes de Facebook Messenger.
    """
    print(f"Webhook POST recibido: {data}")
    
    # Parsear los mensajes del payload
    messages = parse_webhook_payload(data)
    
    if not messages:
        print("No se encontraron mensajes en el payload")
        return {"status": "ok"}
    
    # Procesar cada mensaje
    for sender_id, message_text in messages:
        print(f"Procesando mensaje de {sender_id}: {message_text}")
        
        # Añadir mensaje del usuario al historial
        async with app.modify_state(State) as state:
            state.add_message("Usuario", message_text)
        
        # Procesar el mensaje (Groq + respuesta)
        result = await process_incoming_message(sender_id, message_text)
        
        # Añadir respuesta del bot al historial
        async with app.modify_state(State) as state:
            state.add_message(
                "Bot",
                result["final_message"],
                escalated=result["escalated"]
            )
        
        print(f"Resultado: {result}")
    
    return {"status": "ok"}
