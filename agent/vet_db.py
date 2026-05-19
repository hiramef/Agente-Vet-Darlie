# agent/vet_db.py — Integración con el sistema de historiales clínicos
# Generado por AgentKit

import os
import uuid
import sqlite3
import logging
from datetime import datetime

logger = logging.getLogger("agentkit")

VET_DB_PATH = os.getenv("VET_DB_PATH", r"C:\Users\oroci\Desktop\Vet-Darlie\vet-historial\prisma\dev.db")


def _conn():
    return sqlite3.connect(VET_DB_PATH)


# ── Dueños ──────────────────────────────────────────────────────────────────

def buscar_dueno(telefono: str) -> dict | None:
    """Busca un dueño por número de teléfono."""
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, nombre, telefono FROM Dueno WHERE telefono = ?", (telefono,))
        row = cur.fetchone()
    if row:
        return {"id": row[0], "nombre": row[1], "telefono": row[2]}
    return None


def crear_dueno(nombre: str, telefono: str) -> dict:
    """Crea un nuevo dueño en el sistema."""
    dueno_id = str(uuid.uuid4())
    with _conn() as conn:
        conn.execute(
            "INSERT INTO Dueno (id, nombre, telefono, createdAt) VALUES (?, ?, ?, ?)",
            (dueno_id, nombre, telefono, datetime.utcnow().isoformat()),
        )
    logger.info(f"Dueño creado: {nombre} ({telefono})")
    return {"id": dueno_id, "nombre": nombre, "telefono": telefono}


def buscar_o_crear_dueno(nombre: str, telefono: str) -> dict:
    """Busca un dueño por teléfono; si no existe, lo crea."""
    dueno = buscar_dueno(telefono)
    if dueno:
        return dueno
    return crear_dueno(nombre, telefono)


# ── Mascotas ─────────────────────────────────────────────────────────────────

def buscar_mascota(dueno_id: str, nombre_mascota: str) -> dict | None:
    """Busca una mascota por nombre dentro de las mascotas de un dueño."""
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, nombre, especie FROM Mascota WHERE duenoPk = ? AND nombre = ?",
            (dueno_id, nombre_mascota),
        )
        row = cur.fetchone()
    if row:
        return {"id": row[0], "nombre": row[1], "especie": row[2]}
    return None


def crear_mascota(dueno_id: str, nombre: str, especie: str) -> dict:
    """Crea una nueva mascota en el sistema."""
    mascota_id = str(uuid.uuid4())
    with _conn() as conn:
        conn.execute(
            "INSERT INTO Mascota (id, duenoPk, nombre, especie, sexo, createdAt) VALUES (?, ?, ?, ?, ?, ?)",
            (mascota_id, dueno_id, nombre, especie, "desconocido", datetime.utcnow().isoformat()),
        )
    logger.info(f"Mascota creada: {nombre} ({especie})")
    return {"id": mascota_id, "nombre": nombre, "especie": especie}


def buscar_o_crear_mascota(dueno_id: str, nombre: str, especie: str) -> dict:
    """Busca una mascota por nombre; si no existe, la crea."""
    mascota = buscar_mascota(dueno_id, nombre)
    if mascota:
        return mascota
    return crear_mascota(dueno_id, nombre, especie)


# ── Citas ────────────────────────────────────────────────────────────────────

def crear_cita(mascota_id: str, fecha: str, hora: str, motivo: str) -> dict:
    """Crea una nueva cita en el sistema de historiales."""
    cita_id = str(uuid.uuid4())
    with _conn() as conn:
        conn.execute(
            "INSERT INTO Cita (id, mascotaId, fecha, hora, motivo, estado, createdAt) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (cita_id, mascota_id, fecha, hora, motivo, "pendiente", datetime.utcnow().isoformat()),
        )
    logger.info(f"Cita creada: {cita_id} — {motivo} el {fecha} a las {hora}")
    return {
        "id": cita_id,
        "mascota_id": mascota_id,
        "fecha": fecha,
        "hora": hora,
        "motivo": motivo,
        "estado": "pendiente",
    }


def obtener_citas(limite: int = 50) -> list[dict]:
    """Retorna las citas más recientes con información del dueño y mascota."""
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT
                c.id,
                c.fecha,
                c.hora,
                c.motivo,
                c.estado,
                m.nombre  AS mascota,
                m.especie AS especie,
                d.nombre  AS dueno,
                d.telefono AS telefono
            FROM Cita c
            JOIN Mascota m ON c.mascotaId = m.id
            JOIN Dueno   d ON m.duenoPk   = d.id
            ORDER BY c.createdAt DESC
            LIMIT ?
        """, (limite,))
        cols = [desc[0] for desc in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def registrar_cita_completa(
    nombre_dueno: str,
    telefono_dueno: str,
    nombre_mascota: str,
    especie: str,
    servicio: str,
    fecha: str,
    hora: str,
) -> dict:
    """
    Función principal: registra o recupera dueño y mascota, luego crea la cita.
    Retorna un resumen con todos los datos creados.
    """
    dueno = buscar_o_crear_dueno(nombre_dueno, telefono_dueno)
    mascota = buscar_o_crear_mascota(dueno["id"], nombre_mascota, especie)
    cita = crear_cita(mascota["id"], fecha, hora, servicio)

    return {
        "cita_id": cita["id"],
        "dueno": dueno["nombre"],
        "mascota": mascota["nombre"],
        "especie": mascota["especie"],
        "servicio": servicio,
        "fecha": fecha,
        "hora": hora,
        "estado": "pendiente",
    }
