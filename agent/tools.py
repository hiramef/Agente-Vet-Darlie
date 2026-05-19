# agent/tools.py — Herramientas del agente
# Generado por AgentKit — Veterinaria Darlie

import os
import yaml
import logging
from datetime import datetime

logger = logging.getLogger("agentkit")


def cargar_info_negocio() -> dict:
    """Carga la información del negocio desde business.yaml."""
    try:
        with open("config/business.yaml", "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        logger.error("config/business.yaml no encontrado")
        return {}


def obtener_horario() -> dict:
    """Retorna el horario de atención de la clínica."""
    info = cargar_info_negocio()
    return {
        "horario": info.get("negocio", {}).get("horario", "No disponible"),
    }


def buscar_en_knowledge(consulta: str) -> str:
    """Busca información relevante en los archivos de /knowledge."""
    resultados = []
    knowledge_dir = "knowledge"

    if not os.path.exists(knowledge_dir):
        return "No hay archivos de conocimiento disponibles."

    for archivo in os.listdir(knowledge_dir):
        ruta = os.path.join(knowledge_dir, archivo)
        if archivo.startswith(".") or not os.path.isfile(ruta):
            continue
        try:
            with open(ruta, "r", encoding="utf-8") as f:
                contenido = f.read()
                if consulta.lower() in contenido.lower():
                    resultados.append(f"[{archivo}]: {contenido[:500]}")
        except (UnicodeDecodeError, IOError):
            continue

    if resultados:
        return "\n---\n".join(resultados)
    return "No encontré información específica sobre eso en mis archivos."


# ════════════════════════════════════════════════════════════
# Herramientas para agendar citas — Veterinaria Darlie
# ════════════════════════════════════════════════════════════

# Almacén temporal de citas en memoria (en producción usar base de datos)
_citas: dict[str, list[dict]] = {}


def registrar_cita(telefono: str, nombre_dueno: str, nombre_mascota: str,
                   especie: str, servicio: str, fecha: str, hora: str) -> dict:
    """
    Registra una cita para una mascota.

    Returns:
        dict con confirmación y número de cita
    """
    numero_cita = f"DARLIE-{len(_citas) + 1:04d}"
    cita = {
        "id": numero_cita,
        "telefono": telefono,
        "nombre_dueno": nombre_dueno,
        "nombre_mascota": nombre_mascota,
        "especie": especie,
        "servicio": servicio,
        "fecha": fecha,
        "hora": hora,
        "creada": datetime.utcnow().isoformat(),
    }
    if telefono not in _citas:
        _citas[telefono] = []
    _citas[telefono].append(cita)
    logger.info(f"Cita registrada: {numero_cita} para {nombre_mascota} ({especie})")
    return cita


def consultar_citas(telefono: str) -> list[dict]:
    """Retorna todas las citas registradas para un número de teléfono."""
    return _citas.get(telefono, [])


def cancelar_cita(telefono: str, numero_cita: str) -> bool:
    """Cancela una cita por su número. Retorna True si fue exitoso."""
    citas = _citas.get(telefono, [])
    for i, cita in enumerate(citas):
        if cita["id"] == numero_cita:
            _citas[telefono].pop(i)
            logger.info(f"Cita cancelada: {numero_cita}")
            return True
    return False
