"""
Backend module para el webhook de Facebook Messenger y la integración con Groq.
"""
import os
import asyncio
from typing import Dict, Any, Optional
from dotenv import load_dotenv
import httpx
from groq import AsyncGroq

# Cargar variables de entorno
load_dotenv()

FB_PAGE_ACCESS_TOKEN = os.getenv("FB_PAGE_ACCESS_TOKEN")
FB_VERIFY_TOKEN = os.getenv("FB_VERIFY_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# System prompt para el bot
SYSTEM_PROMPT = """Eres un vendedor de máquinas láser. Productos: Cortadora 130W ($4000), Grabadora Fibra 30W ($2500). 
Si la pregunta es técnica o piden hablar con alguien, responde solo la palabra clave 'ESCALATE'. 
Si no, responde amablemente."""

# Cliente de Groq
groq_client = AsyncGroq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None


async def classify_and_respond_with_groq(user_message: str) -> str:
    """
    Envía el mensaje del usuario a Groq y obtiene una respuesta.
    
    Args:
        user_message: El mensaje del usuario
        
    Returns:
        La respuesta del modelo o 'ESCALATE' si debe escalar a humano
    """
    if not groq_client:
        return "Error: Groq API no configurada"
    
    try:
        chat_completion = await groq_client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT
                },
                {
                    "role": "user",
                    "content": user_message
                }
            ],
            model="llama3-8b-8192",
            temperature=0.7,
            max_tokens=500,
        )
        
        response = chat_completion.choices[0].message.content.strip()
        return response
        
    except Exception as e:
        print(f"Error al llamar a Groq API: {e}")
        return "Lo siento, hubo un error al procesar tu mensaje."


async def send_facebook_message(recipient_id: str, message_text: str) -> bool:
    """
    Envía un mensaje a través de la Graph API de Facebook.
    
    Args:
        recipient_id: El ID del destinatario
        message_text: El texto del mensaje
        
    Returns:
        True si se envió correctamente, False en caso contrario
    """
    if not FB_PAGE_ACCESS_TOKEN:
        print("Error: FB_PAGE_ACCESS_TOKEN no configurado")
        return False
    
    url = f"https://graph.facebook.com/v18.0/me/messages?access_token={FB_PAGE_ACCESS_TOKEN}"
    
    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": message_text}
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, timeout=10.0)
            
            if response.status_code == 200:
                print(f"Mensaje enviado a {recipient_id}: {message_text}")
                return True
            else:
                print(f"Error al enviar mensaje: {response.status_code} - {response.text}")
                return False
                
    except Exception as e:
        print(f"Excepción al enviar mensaje a Facebook: {e}")
        return False


async def process_incoming_message(sender_id: str, message_text: str) -> Dict[str, Any]:
    """
    Procesa un mensaje entrante: lo envía a Groq y responde según la clasificación.
    
    Args:
        sender_id: El ID del remitente
        message_text: El mensaje del usuario
        
    Returns:
        Diccionario con información del procesamiento
    """
    # Obtener respuesta de Groq
    groq_response = await classify_and_respond_with_groq(message_text)
    
    result = {
        "sender_id": sender_id,
        "user_message": message_text,
        "groq_response": groq_response,
        "escalated": False,
        "sent_to_facebook": False
    }
    
    # Verificar si debe escalar
    if "ESCALATE" in groq_response.upper():
        result["escalated"] = True
        # Enviar mensaje genérico
        escalation_message = "Gracias por tu consulta. Un representante se pondrá en contacto contigo pronto."
        result["sent_to_facebook"] = await send_facebook_message(sender_id, escalation_message)
        result["final_message"] = escalation_message
    else:
        # Enviar la respuesta del bot
        result["sent_to_facebook"] = await send_facebook_message(sender_id, groq_response)
        result["final_message"] = groq_response
    
    return result


def verify_webhook(mode: str, token: str, challenge: str) -> Optional[int]:
    """
    Verifica el webhook de Facebook.
    
    Args:
        mode: El modo de verificación
        token: El token de verificación
        challenge: El challenge de Facebook
        
    Returns:
        El challenge como int si la verificación es exitosa, None en caso contrario
    """
    if mode == "subscribe" and token == FB_VERIFY_TOKEN:
        try:
            return int(challenge)
        except ValueError:
            return None
    return None


def parse_webhook_payload(payload: Dict[str, Any]) -> list:
    """
    Parsea el payload del webhook de Facebook para extraer los mensajes.
    
    Args:
        payload: El payload JSON de Facebook
        
    Returns:
        Lista de tuplas (sender_id, message_text)
    """
    messages = []
    
    try:
        for entry in payload.get("entry", []):
            for messaging_event in entry.get("messaging", []):
                sender_id = messaging_event.get("sender", {}).get("id")
                message = messaging_event.get("message", {})
                message_text = message.get("text")
                
                # Solo procesar si hay sender_id y texto
                if sender_id and message_text:
                    messages.append((sender_id, message_text))
    except Exception as e:
        print(f"Error al parsear webhook payload: {e}")
    
    return messages
