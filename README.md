# 🤖 MVP Bot - Bot de Atención al Cliente para Facebook Messenger

Bot inteligente de atención al cliente para Facebook Messenger que utiliza IA (Groq) para clasificar consultas y responder automáticamente o escalar a un humano cuando sea necesario.

## 🎯 Características

- **Clasificación Inteligente**: Usa Groq AI (LLaMA 3) para analizar mensajes
- **Respuestas Automáticas**: Responde preguntas simples sobre productos
- **Escalamiento**: Detecta consultas complejas y las escala a atención humana
- **Monitoreo en Tiempo Real**: Interfaz web para ver mensajes en tiempo real
- **Stack Moderno**: Python + Reflex + FastAPI + Groq

## 📋 Requisitos Previos

- Python 3.8 o superior
- Cuenta de Facebook Developer
- Página de Facebook
- API Key de Groq
- ngrok (para desarrollo local)

## 🚀 Instalación

### 1. Clonar y preparar el entorno

```bash
# Instalar dependencias
pip install -r requirements.txt
```

### 2. Configurar variables de entorno

Copia el archivo `.env.example` a `.env`:

```bash
cp .env.example .env
```

Edita `.env` con tus credenciales:

```env
FB_PAGE_ACCESS_TOKEN=tu_page_access_token_aqui
FB_VERIFY_TOKEN=tu_verify_token_personalizado
GROQ_API_KEY=tu_groq_api_key_aqui
```

### 3. Obtener credenciales

#### API Key de Groq

1. Ve a [https://console.groq.com](https://console.groq.com)
2. Crea una cuenta o inicia sesión
3. Ve a "API Keys" y genera una nueva key
4. Copia la key y pégala en `GROQ_API_KEY`

#### Tokens de Facebook

**FB_VERIFY_TOKEN**:
- Puedes usar cualquier string aleatorio (ej: `mi_token_secreto_123`)
- Lo usarás más adelante para verificar el webhook

**FB_PAGE_ACCESS_TOKEN**:

1. Ve a [Facebook Developers](https://developers.facebook.com/)
2. Crea una nueva aplicación (tipo "Empresa")
3. Añade el producto "Messenger"
4. En la configuración de Messenger:
   - Ve a "Tokens de acceso"
   - Selecciona tu página
   - Genera un token de acceso
   - Copia el token y pégalo en `FB_PAGE_ACCESS_TOKEN`

## 🏃 Ejecutar la Aplicación

### Modo Desarrollo Local

```bash
reflex run
```

Esto iniciará:
- Frontend en: `http://localhost:3000`
- Backend/API en: `http://localhost:8000`

## 🌐 Configurar el Webhook de Facebook

### 1. Exponer tu servidor local con ngrok

```bash
# En otra terminal
ngrok http 8000
```

Copia la URL HTTPS que te proporciona ngrok (ej: `https://abc123.ngrok.io`)

### 2. Configurar el webhook en Facebook

1. Ve a tu app en Facebook Developers
2. En "Messenger" → "Configuración"
3. En la sección "Webhooks", click en "Añadir URL de callback":
   - **URL de callback**: `https://tu-url-de-ngrok.ngrok.io/webhook`
   - **Token de verificación**: El mismo que pusiste en `FB_VERIFY_TOKEN`
   - **Campos de suscripción**: Marca `messages` y `messaging_postbacks`
4. Click en "Verificar y guardar"

### 3. Suscribir la página

En la misma sección de Webhooks:
1. Click en "Añadir suscripciones"
2. Selecciona tu página de Facebook
3. Suscríbela a los eventos

## 🧪 Probar el Bot

### 1. Probar la verificación del webhook

```bash
curl "http://localhost:8000/webhook?hub.mode=subscribe&hub.verify_token=tu_verify_token&hub.challenge=12345"
```

Debe devolver: `12345`

### 2. Enviar un mensaje de prueba desde Facebook

1. Ve a tu página de Facebook
2. Envía un mensaje desde Messenger
3. Verás el mensaje aparecer en la interfaz web (`http://localhost:3000`)
4. El bot responderá automáticamente

### 3. Probar con el simulador (opcional)

```bash
curl -X POST http://localhost:8000/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "entry": [{
      "messaging": [{
        "sender": {"id": "12345"},
        "message": {"text": "Hola, ¿qué máquinas láser tienen?"}
      }]
    }]
  }'
```

## 📊 Estructura del Proyecto

```
botguerralaser/
├── mvp_bot/
│   ├── __init__.py
│   ├── mvp_bot.py          # Lógica principal, UI y State
│   └── backend.py          # Webhook de Facebook y Groq
├── assets/                 # Archivos estáticos (opcional)
├── rxconfig.py             # Configuración de Reflex
├── requirements.txt        # Dependencias
├── .env                    # Variables de entorno (no versionar)
├── .env.example            # Template de variables
├── .gitignore
└── README.md
```

## 🤖 Funcionamiento del Bot

### Sistema de Clasificación

El bot usa el siguiente prompt para Groq:

> "Eres un vendedor de máquinas láser. Productos: Cortadora 130W ($4000), Grabadora Fibra 30W ($2500). 
> Si la pregunta es técnica o piden hablar con alguien, responde solo la palabra clave 'ESCALATE'. 
> Si no, responde amablemente."

### Flujo de Mensajes

1. **Usuario envía mensaje** → Facebook Messenger
2. **Facebook envía webhook** → Tu servidor (`POST /webhook`)
3. **Backend parsea mensaje** → Extrae texto y sender_id
4. **Groq analiza y responde** → Clasifica el mensaje
5. **Decisión**:
   - Si contiene "ESCALATE" → Envía mensaje genérico de escalamiento
   - Si no → Envía la respuesta del bot
6. **Actualización de UI** → Los mensajes aparecen en tiempo real

## 🎨 Interfaz Web

La interfaz en `http://localhost:3000` muestra:

- **Historial de mensajes** en tiempo real
- **Identificación visual** de usuario vs bot
- **Indicador de escalamiento** (badge naranja)
- **Timestamps** de cada mensaje
- **Botón para limpiar historial**

## 🔧 Personalización

### Cambiar el prompt del bot

Edita `mvp_bot/backend.py`:

```python
SYSTEM_PROMPT = """Tu nuevo prompt aquí..."""
```

### Cambiar el modelo de Groq

En `mvp_bot/backend.py`, línea 48:

```python
model="llama3-8b-8192",  # Cambia por otro modelo disponible
```

Modelos disponibles: `llama3-8b-8192`, `llama3-70b-8192`, `mixtral-8x7b-32768`

### Personalizar la UI

Edita `mvp_bot/mvp_bot.py` en la función `index()` y `message_card()`.

## 🐛 Solución de Problemas

### El webhook no se verifica

- Verifica que `FB_VERIFY_TOKEN` en `.env` coincida con el de Facebook
- Asegúrate de que ngrok esté corriendo
- Revisa que la URL sea HTTPS

### No recibo mensajes

- Verifica que la página esté suscrita al webhook
- Revisa los logs de la terminal donde corre `reflex run`
- Comprueba que `FB_PAGE_ACCESS_TOKEN` sea correcto

### Error de Groq API

- Verifica que `GROQ_API_KEY` sea válida
- Revisa tu cuota de uso en [console.groq.com](https://console.groq.com)

### Los mensajes no aparecen en la UI

- Refresca la página del navegador (`http://localhost:3000`)
- Verifica que no haya errores en la consola del navegador
- Revisa los logs del servidor

## 📝 Comandos Útiles

```bash
# Iniciar la aplicación
reflex run

# Solo iniciar el backend
reflex run --backend-only

# Solo iniciar el frontend
reflex run --frontend-only

# Iniciar ngrok
ngrok http 8000

# Ver logs en tiempo real
# Los logs aparecen automáticamente en la terminal
```

## 🔒 Seguridad

- **Nunca versiones el archivo `.env`** (ya está en `.gitignore`)
- Usa tokens de acceso temporal para desarrollo
- En producción, usa variables de entorno del servidor
- Valida siempre la firma de Facebook en producción

## 🚀 Despliegue en Producción

Para producción, considera:

1. **Hosting**: Railway, Render, DigitalOcean, AWS
2. **Variables de entorno**: Configúralas en tu plataforma
3. **HTTPS**: Obligatorio para webhooks de Facebook
4. **Verificación de firmas**: Implementar `x-hub-signature-256`
5. **Logging**: Usar sistema de logs profesional
6. **Rate limiting**: Proteger endpoints públicos

## 📚 Recursos Adicionales

- [Documentación de Reflex](https://reflex.dev/docs/)
- [Facebook Messenger Platform](https://developers.facebook.com/docs/messenger-platform)
- [Groq API Documentation](https://console.groq.com/docs)
- [ngrok Documentation](https://ngrok.com/docs)

## 🤝 Contribuir

Este es un MVP/Prueba de Concepto. Mejoras sugeridas:

- [ ] Agregar persistencia (base de datos)
- [ ] Implementar autenticación
- [ ] Añadir más tipos de respuestas (imágenes, botones)
- [ ] Mejorar el manejo de errores
- [ ] Agregar tests unitarios
- [ ] Implementar rate limiting
- [ ] Dashboard de analíticas

## 📄 Licencia

MIT License - Úsalo libremente para tus proyectos.

## 💬 Soporte

Para preguntas o problemas:
1. Revisa la sección de "Solución de Problemas"
2. Verifica los logs de la aplicación
3. Consulta la documentación oficial de cada herramienta

---

**Desarrollado con ❤️ usando Python, Reflex y Groq AI**
