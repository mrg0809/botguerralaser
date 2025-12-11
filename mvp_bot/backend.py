"""
Backend module para el webhook de Facebook Messenger y la integración con Groq.
"""
import os
import asyncio
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv
import httpx
from groq import AsyncGroq

# Cargar variables de entorno
load_dotenv()

FB_PAGE_ACCESS_TOKEN = os.getenv("FB_PAGE_ACCESS_TOKEN")
FB_VERIFY_TOKEN = os.getenv("FB_VERIFY_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# System prompt para el bot
SYSTEM_PROMPT = """Eres un asistente virtual de GUERRA LÁSER, empresa de venta de maquinaria láser en México.

REGLAS ESTRICTAS:
1. USA SOLAMENTE la información exacta del contexto proporcionado.
2. NO menciones sucursales, sitios web, ni secciones que NO aparezcan en el contexto.
3. NO inventes datos de contacto, ubicaciones, productos, precios o servicios.
4. Si el contexto muestra UNA ubicación, di que es LA ubicación (no "una de nuestras sucursales").
5. Copia direcciones, teléfonos y correos EXACTAMENTE como aparecen en el contexto.
6. Cuando haya un producto relevante, responde con TODAS las especificaciones disponibles en el contexto para ese producto (no omitas campos que aparezcan).
7. IMPORTANTE: Cuando menciones un producto que tenga el campo "link_mercadolibre" en el contexto, SIEMPRE incluye ese link en tu respuesta para que el usuario pueda ver más detalles. Preséntalo de forma natural como "Puedes ver más detalles aquí: [link]" o "Ver publicación: [link]".
8. Si la pregunta es genérica (saludo, “qué venden”, “catálogo”, “categorías”), sugiere 3 a 5 categorías con su enlace exactamente como aparezcan en el contexto.
9. NUNCA inventes marcas, modelos, precios ni enlaces. Solo puedes usar los campos del contexto: `link_mercadolibre` de productos o los links de categoría de "CATEGORÍA / LINK". Si no hay productos en el contexto, responde únicamente con las categorías disponibles; si tampoco hay categorías, responde 'ESCALATE'.
10. Si el usuario pide "todas" las opciones o menciona una categoría (ej. CO2, fibra, CNC), responde con la(s) categorías correspondientes y sus links EXACTOS del contexto; no inventes dominios ni URLs.
11. Si no hay entrada [Productos relevantes] en el contexto, NO inventes un producto: responde únicamente con las categorías disponibles y sus enlaces. Si tampoco hay categorías, responde 'ESCALATE'.
12. SOLO puedes dar links de MercadoLibre que vengan en el contexto (link_mercadolibre de productos o los LINK de las CATEGORÍAS). NO uses dominios externos ni inventes URLs. Si no hay links disponibles en el contexto, responde 'ESCALATE'.

Escalación (solo si falta info o piden humano):
- Si la pregunta es técnica compleja o piden hablar con una persona, responde solo la palabra 'ESCALATE'.
- Si el contexto no contiene la información solicitada, responde solo la palabra 'ESCALATE'.

Responde de forma directa, concisa y profesional. No digas "consulta con un representante" si tienes la información en el contexto; en ese caso responde completo."""

# Cliente de Groq
groq_client = AsyncGroq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

# Buffer en memoria para exponer mensajes al frontend vía polling
MESSAGE_BUFFER = []


def cargar_contexto_completo() -> dict:
    """Carga contexto dinámico desde archivos locales.

    Lee `Contexto_tienda.txt` (políticas/datos generales) y `contexto_bot.jsonl`
    (inventario). Si alguno no existe, se omite silenciosamente. Retorna
    un dict con las secciones separadas.
    """
    contexto = {
        "tienda": "",
        "productos": [],
        "categorias_links": []
    }

    # Contexto general
    try:
        with open("Contexto_tienda.txt", "r", encoding="utf-8") as f:
            contexto["tienda"] = f.read().strip()
            contexto["categorias_links"] = extraer_categorias_links(contexto["tienda"])
    except FileNotFoundError:
        pass

    # Inventario JSONL
    try:
        import json
        with open("contexto_bot.jsonl", "r", encoding="utf-8") as f:
            for linea in f:
                linea = linea.strip()
                if linea:
                    try:
                        producto = json.loads(linea)
                        contexto["productos"].append(producto)
                    except json.JSONDecodeError:
                        pass
    except FileNotFoundError:
        pass

    return contexto


def generar_link_mercadolibre(product_id: str) -> str:
    """Genera el link directo a un producto de MercadoLibre."""
    if not product_id or not product_id.startswith("MLM"):
        return ""
    # Formato: https://articulo.mercadolibre.com.mx/MLM-1573916640
    # El ID viene como MLM1573916640, necesitamos insertarle el guion
    product_id_formatted = product_id.replace("MLM", "MLM-", 1)
    return f"https://articulo.mercadolibre.com.mx/{product_id_formatted}"


def extraer_categorias_links(tienda_texto: str) -> List[Dict[str, str]]:
    """Extrae pares categoría/link del bloque de catálogos del contexto."""
    if not tienda_texto:
        return []

    categorias: List[Dict[str, str]] = []
    lineas = [ln.strip() for ln in tienda_texto.splitlines() if ln.strip()]
    categoria_actual = None

    for linea in lineas:
        if linea.lower().startswith("categoría:") or linea.lower().startswith("categoria:"):
            categoria_actual = linea.split(":", 1)[1].strip()
        elif linea.lower().startswith("link:") and categoria_actual:
            link_valor = linea.split(":", 1)[1].strip()
            categorias.append({"categoria": categoria_actual, "link": link_valor})
            categoria_actual = None

    return categorias


def filtrar_categorias_por_keywords(categorias: List[Dict[str, str]], mensaje_lower: str) -> List[Dict[str, str]]:
    """Devuelve categorías cuyo nombre coincide con keywords del mensaje."""
    if not categorias:
        return []

    resultado = []
    keywords_map = [
        ("co2", ["co2"]),
        ("fibra", ["fibra", "fiber"]),
        ("cnc", ["cnc", "router"]),
        ("plasma", ["plasma", "canteadora"]),
        ("chiller", ["chiller", "enfriador", "enfriamiento"]),
        ("extractor", ["extractor"]),
        ("compresor", ["compresor", "aire"]),
        ("acrilico", ["acrilico", "acrílico"]),
        ("pet", ["pet"]),
        ("tubo", ["tubo", "tube", "reci", "puri", "efr"]),
    ]

    for categoria in categorias:
        nombre = categoria.get("categoria", "").lower()
        for _, kws in keywords_map:
            if any(kw in mensaje_lower for kw in kws) and any(kw in nombre for kw in kws):
                resultado.append(categoria)
                break

    # Si no hubo match específico pero el usuario dice "todas" u "opciones"
    if not resultado and any(term in mensaje_lower for term in ["todas", "todas las", "opciones", "catalogo", "catálogo", "ver todo", "todas las maquinas", "todas las máquinas"]):
        # devolver todas, pero límite 5 para no saturar
        resultado = categorias[:5]

    return resultado


def filtrar_contexto_relevante(mensaje_usuario: str, contexto_completo: dict) -> str:
    """Filtra el contexto según palabras clave en el mensaje del usuario.
    
    Args:
        mensaje_usuario: El mensaje del usuario
        contexto_completo: Dict con 'tienda' y 'productos'
        
    Returns:
        String con solo el contexto relevante para ahorrar tokens
    """
    mensaje_lower = mensaje_usuario.lower()
    partes = []

    keywords_genericos = [
        "hola", "buenos dias", "buenas", "buen dia", "que venden", "qué venden",
        "catalogo", "catálogo", "categorias", "categorías", "productos", "servicios",
        "que tienen", "qué tienen", "info", "informacion", "información",
        "co2", "fibra", "router", "cnc"
    ]
    es_consulta_generica = any(kw in mensaje_lower for kw in keywords_genericos)
    se_agregaron_categorias = False
    
    # Palabras clave que indican necesidad de info general
    keywords_tienda = ["envio", "envío", "garantia", "garantía", "pago", "forma de pago", "metodo",
                       "instalacion", "instalación", "soporte", "horario", "ubicacion", "ubicación",
                       "direccion", "dirección", "donde", "dónde", "contacto", "telefono", "teléfono",
                       "empresa", "llama", "nombre", "correo", "email", "tel", "cel", "whatsapp"]
    
    necesita_info_tienda = any(kw in mensaje_lower for kw in keywords_tienda)
    
    if necesita_info_tienda and contexto_completo["tienda"]:
        partes.append("[Contexto tienda]\n" + contexto_completo["tienda"])
    
    # Buscar productos mencionados por nombre o características
    productos_relevantes = []

    # Si la consulta es genérica (incluye co2/fibra/router/cnc o saludo/catalogo), evitamos listar productos
    if not es_consulta_generica:
        for producto in contexto_completo["productos"]:
            nombre = producto.get("nombre", "").lower()
            modelo = producto.get("modelo", "").lower()
            tipo = producto.get("tipo", "").lower()
            categoria = producto.get("categoria", "").lower()
            
            detalles = producto.get("detalles", {})
            titulo = detalles.get("TITLE", "").lower() if isinstance(detalles, dict) else ""
            
            match = False
            if titulo:
                palabras_busqueda = mensaje_lower.split()
                for palabra in palabras_busqueda:
                    if len(palabra) > 3 and palabra in titulo:  # palabras de más de 3 letras
                        match = True
                        break
            
            es_maquina_completa = any(term in categoria for term in ["maquina", "cortadora", "grabadora"])
            
            if not match and ((nombre and nombre in mensaje_lower) or \
               (modelo and modelo in mensaje_lower) or \
               (tipo and tipo in mensaje_lower) or \
               es_maquina_completa):
                match = True

            if match:
                productos_relevantes.append(producto)
    # Caso especial: tubos láser (Reci, Puri, etc.)
    keywords_tubos = ["tubo", "tube", "reci", "puri", "laser co2", "láser co2"]
    if not productos_relevantes and any(kw in mensaje_lower for kw in keywords_tubos):
        for producto in contexto_completo["productos"]:
            categoria = producto.get("categoria", "").lower()
            detalles = producto.get("detalles", {})
            titulo = detalles.get("TITLE", "").lower() if isinstance(detalles, dict) else ""
            marca = detalles.get("BRAND", "").lower() if isinstance(detalles, dict) else ""

            es_tubo = any(term in titulo for term in ["tubo", "tube"]) or "tubo" in categoria
            es_marca_objetivo = any(term in marca for term in ["reci", "puri", "pury", "purui"])

            if es_tubo or es_marca_objetivo:
                productos_relevantes.append(producto)

        # Limitar para no saturar
        if len(productos_relevantes) > 10:
            productos_relevantes = productos_relevantes[:10]

    # Opciones con chiller si el usuario lo menciona
    keywords_chiller = ["chiller", "enfriamiento", "enfriador"]
    menciona_chiller = any(kw in mensaje_lower for kw in keywords_chiller)
    if menciona_chiller:
        opciones_chiller = []
        for producto in contexto_completo["productos"]:
            detalles = producto.get("detalles", {})
            titulo = detalles.get("TITLE", "").lower() if isinstance(detalles, dict) else ""
            accesorios = detalles.get("ACCESSORIES_INCLUDED", "").lower() if isinstance(detalles, dict) else ""
            cooling = detalles.get("COOLING_SYSTEM", "").lower() if isinstance(detalles, dict) else ""
            categoria = producto.get("categoria", "").lower()

            if any(term in categoria for term in ["maquina", "cortadora", "grabadora"]):
                if "chiller" in titulo or "chiller" in accesorios or "chiller" in cooling:
                    opciones_chiller.append(producto)

        if opciones_chiller:
            # Añadir como sección aparte para que el prompt lo exponga
            import json
            productos_relevantes = productos_relevantes or []
            # No duplicar demasiados; máximo 5
            opciones_chiller = opciones_chiller[:5]
            productos_relevantes.extend(opciones_chiller)

    # Opciones con rotativo si el usuario lo menciona
    keywords_rotativo = ["rotativo", "rotary", "rotatorio"]
    menciona_rotativo = any(kw in mensaje_lower for kw in keywords_rotativo)
    if menciona_rotativo:
        opciones_rotativo = []
        for producto in contexto_completo["productos"]:
            detalles = producto.get("detalles", {})
            titulo = detalles.get("TITLE", "").lower() if isinstance(detalles, dict) else ""
            accesorios = detalles.get("ACCESSORIES_INCLUDED", "").lower() if isinstance(detalles, dict) else ""
            categoria = producto.get("categoria", "").lower()

            if ("rotativo" in titulo) or ("rotary" in titulo) or ("rotativo" in accesorios) or ("rotary" in accesorios):
                opciones_rotativo.append(producto)
            elif any(term in categoria for term in ["maquina", "cortadora", "grabadora"]):
                # Máquinas que mencionen rotativo en título o accesorios
                if "rotativo" in titulo or "rotary" in titulo or "rotativo" in accesorios or "rotary" in accesorios:
                    opciones_rotativo.append(producto)

        if opciones_rotativo:
            productos_relevantes = productos_relevantes or []
            opciones_rotativo = opciones_rotativo[:5]
            productos_relevantes.extend(opciones_rotativo)

    # Si no hay match específico pero preguntan por productos, filtrar por categoría relevante
    keywords_productos = ["cortadora", "grabadora", "laser", "láser", "maquina", "máquina", 
                          "producto", "catalogo", "catálogo", "modelos", "que tienen", "co2", "fibra",
                          "chica", "grande", "tamaño", "area", "área", "watts", "potencia", "precio"]
    
    if not productos_relevantes and any(kw in mensaje_lower for kw in keywords_productos):
        # Filtrar máquinas completas de la categoría correcta
        for producto in contexto_completo["productos"]:
            categoria = producto.get("categoria", "").lower()
            
            # Solo incluir productos de la categoría de máquinas completas
            if any(cat in categoria for cat in ["maquina", "cortadora", "grabadora"]):
                detalles = producto.get("detalles", {})
                titulo = detalles.get("TITLE", "").lower() if isinstance(detalles, dict) else ""
                
                # Verificar que sea una máquina completa (no accesorio)
                if (titulo and "maquina" in titulo) or ("laser co2" in titulo) or ("co2" in mensaje_lower and "co2" in titulo):
                    # Si la consulta es genérica, solo añadimos si el título menciona el término consultado
                    if not es_consulta_generica or any(term in titulo for term in mensaje_lower.split() if len(term) > 3):
                        productos_relevantes.append(producto)
        
        # Limitar a máximo 15 máquinas para no saturar
        if len(productos_relevantes) > 15:
            productos_relevantes = productos_relevantes[:15]
    
    if productos_relevantes:
        import json
        # Agregar links de MercadoLibre a cada producto
        productos_con_links = []
        for p in productos_relevantes:
            producto_copia = p.copy()
            product_id = p.get("id", "")
            if product_id:
                link = generar_link_mercadolibre(product_id)
                if link:
                    producto_copia["link_mercadolibre"] = link
            productos_con_links.append(producto_copia)
        
        productos_str = "\n".join([json.dumps(p, ensure_ascii=False) for p in productos_con_links])
        partes.append("[Productos relevantes]\n" + productos_str)

    # Añadir categorías recomendadas si es consulta genérica
    categorias_links = contexto_completo.get("categorias_links", [])
    if es_consulta_generica and categorias_links:
        import json
        recomendadas = filtrar_categorias_por_keywords(categorias_links, mensaje_lower) or categorias_links[:5]
        partes.append("[Categorias recomendadas]\n" + json.dumps(recomendadas, ensure_ascii=False))
        se_agregaron_categorias = True
    
    # Si no se detectó nada relevante, incluir info básica de la tienda por defecto
    if not partes:
        # Para preguntas generales/saludo, incluir siempre info básica de la empresa
        if contexto_completo["tienda"]:
            # Extraer solo las primeras 500 caracteres de info básica
            info_basica = contexto_completo["tienda"][:500]
            partes.append("[Info empresa]\n" + info_basica)
        
        if contexto_completo["productos"]:
            import json
            # Solo nombres y precios de todos los productos
            resumen = []
            for p in contexto_completo["productos"][:5]:  # máximo 5
                resumen.append({
                    "nombre": p.get("nombre", ""),
                    "precio": p.get("precio", ""),
                    "tipo": p.get("tipo", "")
                })
            if resumen:
                partes.append("[Resumen productos]\n" + json.dumps(resumen, ensure_ascii=False))

        # Añadir recomendaciones de categorías con links si es genérico o no hubo match
        categorias_links = contexto_completo.get("categorias_links", [])
        if categorias_links and not se_agregaron_categorias:
            import json
            recomendadas = filtrar_categorias_por_keywords(categorias_links, mensaje_lower) or categorias_links[:5]
            partes.append("[Categorias recomendadas]\n" + json.dumps(recomendadas, ensure_ascii=False))
    return "\n\n".join(partes) if partes else ""


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

    # Cargar contexto completo y filtrar según mensaje del usuario
    contexto_completo = cargar_contexto_completo()
    contexto_filtrado = filtrar_contexto_relevante(user_message, contexto_completo)
    
    system_prompt = SYSTEM_PROMPT
    
    if contexto_filtrado:
        system_prompt += "\n\n=== CONTEXTO (usa SOLO esta información) ===\n" + contexto_filtrado
        system_prompt += "\n\n=== FIN DEL CONTEXTO ==="
        system_prompt += "\n\nRespuesta basada EXCLUSIVAMENTE en el contexto anterior:"

    try:
        chat_completion = await groq_client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": user_message,
                },
            ],
            # Modelo actualizado: reemplaza el deprecado `llama3-8b-8192`.
            model="llama-3.1-8b-instant",
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
    
    # Guardar en buffer para que el frontend pueda consultarlo por polling.
    # Se almacena una vista simplificada para UI.
    from datetime import datetime
    ts = datetime.now().strftime("%H:%M:%S")

    MESSAGE_BUFFER.append(
        {
            "timestamp": ts,
            "sender": "Usuario",
            "message": message_text,
            "escalated": False,
        }
    )
    MESSAGE_BUFFER.append(
        {
            "timestamp": ts,
            "sender": "Bot",
            "message": result["final_message"],
            "escalated": result["escalated"],
        }
    )

    # Limitar buffer para no crecer indefinidamente
    if len(MESSAGE_BUFFER) > 200:
        MESSAGE_BUFFER[:] = MESSAGE_BUFFER[-200:]

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


def get_message_buffer() -> list:
    """Devuelve el buffer de mensajes acumulados."""
    return MESSAGE_BUFFER
