# agent/brain.py — Cerebro del agente: conexión con Claude API + tool use
# Generado por AgentKit

import os
import yaml
import logging
from datetime import datetime
from anthropic import AsyncAnthropic
from dotenv import load_dotenv
from agent.appointments import guardar_cita

load_dotenv()
logger = logging.getLogger("agentkit")

client = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

# Herramientas que Claude puede invocar durante la conversación
HERRAMIENTAS = [
    {
        "name": "registrar_cita",
        "description": (
            "Registra una cita en el sistema de historiales clínicos de Veterinaria Darlie. "
            "Úsala SOLO cuando el cliente haya confirmado explícitamente TODOS los datos: "
            "nombre del dueño, nombre de la mascota, especie, servicio, fecha y hora."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "nombre_dueno": {
                    "type": "string",
                    "description": "Nombre completo del dueño de la mascota",
                },
                "telefono_dueno": {
                    "type": "string",
                    "description": "Número de teléfono del dueño (se obtiene del webhook automáticamente)",
                },
                "nombre_mascota": {
                    "type": "string",
                    "description": "Nombre de la mascota",
                },
                "especie": {
                    "type": "string",
                    "enum": ["perro", "gato"],
                    "description": "Especie de la mascota",
                },
                "servicio": {
                    "type": "string",
                    "description": "Servicio solicitado (ej: consulta general, vacuna puppy, desparasitación)",
                },
                "fecha": {
                    "type": "string",
                    "description": "Fecha de la cita en formato YYYY-MM-DD",
                },
                "hora": {
                    "type": "string",
                    "description": "Hora de la cita en formato HH:MM (24h)",
                },
            },
            "required": [
                "nombre_dueno",
                "telefono_dueno",
                "nombre_mascota",
                "especie",
                "servicio",
                "fecha",
                "hora",
            ],
        },
    },
]


async def _ejecutar_herramienta(nombre: str, argumentos: dict) -> str:
    """Ejecuta la herramienta solicitada por Claude y retorna el resultado como texto."""
    if nombre == "registrar_cita":
        try:
            resultado = await guardar_cita(
                nombre_dueno=argumentos["nombre_dueno"],
                telefono=argumentos["telefono_dueno"],
                nombre_mascota=argumentos["nombre_mascota"],
                especie=argumentos["especie"],
                servicio=argumentos["servicio"],
                fecha=argumentos["fecha"],
                hora=argumentos["hora"],
            )
            return (
                f"Cita registrada exitosamente.\n"
                f"ID: {resultado['id']}\n"
                f"Dueño: {resultado['nombre_dueno']}\n"
                f"Mascota: {resultado['nombre_mascota']} ({resultado['especie']})\n"
                f"Servicio: {resultado['servicio']}\n"
                f"Fecha: {resultado['fecha']} a las {resultado['hora']}\n"
                f"Estado: {resultado['estado']}"
            )
        except Exception as e:
            logger.error(f"Error al registrar cita: {e}")
            return f"Error al registrar la cita: {str(e)}"
    return "Herramienta no reconocida."


def cargar_config_prompts() -> dict:
    try:
        with open("config/prompts.yaml", "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        logger.error("config/prompts.yaml no encontrado")
        return {}


def cargar_system_prompt() -> str:
    config = cargar_config_prompts()
    return config.get("system_prompt", "Eres un asistente útil. Responde en español.")


def obtener_mensaje_error() -> str:
    config = cargar_config_prompts()
    return config.get("error_message", "Lo siento, estoy teniendo problemas técnicos. Por favor intenta de nuevo en unos minutos.")


def obtener_mensaje_fallback() -> str:
    config = cargar_config_prompts()
    return config.get("fallback_message", "Disculpa, no entendí tu mensaje. ¿Podrías reformularlo?")


async def generar_respuesta(mensaje: str, historial: list[dict], telefono: str = "") -> str:
    """
    Genera una respuesta usando Claude API con soporte de tool use.
    Si Claude decide registrar una cita, la escribe directamente en el sistema de historiales.

    Args:
        mensaje: El mensaje nuevo del usuario
        historial: Lista de mensajes anteriores
        telefono: Número de teléfono del cliente (para asociar la cita)

    Returns:
        La respuesta final de texto para enviar al cliente
    """
    if not mensaje or len(mensaje.strip()) < 2:
        return obtener_mensaje_fallback()

    system_prompt = cargar_system_prompt()

    # Inyectar fecha y hora actual para que Claude pueda validar citas correctamente
    _dias = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
    _meses = ["enero", "febrero", "marzo", "abril", "mayo", "junio",
              "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
    ahora = datetime.now()
    dia_nombre = _dias[ahora.weekday()]
    mes_nombre = _meses[ahora.month - 1]
    fecha_hoy = f"{dia_nombre} {ahora.day} de {mes_nombre} de {ahora.year}"
    system_prompt += (
        f"\n\n## Fecha y hora actual\n"
        f"Hoy es {fecha_hoy}.\n"
        f"Hora actual: {ahora.strftime('%H:%M')}.\n"
        f"Usa esta información para validar que las fechas de cita sean correctas "
        f"(día de semana coincide con la fecha) y que no sean en el pasado."
    )

    # Inyectar el teléfono del cliente en el system prompt para que Claude lo use al registrar
    if telefono:
        system_prompt += f"\n\n## Datos del cliente actual\nTeléfono: {telefono}\nUsa este teléfono al llamar a la herramienta registrar_cita."

    mensajes = [{"role": m["role"], "content": m["content"]} for m in historial]
    mensajes.append({"role": "user", "content": mensaje})

    try:
        # Loop de tool use: Claude puede llamar herramientas antes de dar respuesta final
        while True:
            response = await client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=1024,
                system=system_prompt,
                tools=HERRAMIENTAS,
                messages=mensajes,
            )

            # Si Claude terminó sin usar herramientas, retornar la respuesta de texto
            if response.stop_reason == "end_turn":
                texto = next(
                    (b.text for b in response.content if hasattr(b, "text")),
                    obtener_mensaje_fallback(),
                )
                logger.info(f"Respuesta generada ({response.usage.input_tokens} in / {response.usage.output_tokens} out)")
                return texto

            # Claude quiere usar una herramienta
            if response.stop_reason == "tool_use":
                # Agregar la respuesta de Claude (con el bloque tool_use) al historial
                mensajes.append({"role": "assistant", "content": response.content})

                # Ejecutar cada herramienta solicitada y recolectar resultados
                resultados_tools = []
                for bloque in response.content:
                    if bloque.type == "tool_use":
                        logger.info(f"Claude invoca herramienta: {bloque.name} con {bloque.input}")
                        resultado = await _ejecutar_herramienta(bloque.name, bloque.input)
                        resultados_tools.append({
                            "type": "tool_result",
                            "tool_use_id": bloque.id,
                            "content": resultado,
                        })

                # Devolver los resultados a Claude para que genere la respuesta final
                mensajes.append({"role": "user", "content": resultados_tools})
                continue

            # Stop reason inesperado — retornar lo que haya de texto
            texto = next(
                (b.text for b in response.content if hasattr(b, "text")),
                obtener_mensaje_error(),
            )
            return texto

    except Exception as e:
        logger.error(f"Error Claude API: {e}")
        return obtener_mensaje_error()
