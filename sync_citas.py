# sync_citas.py — Sincronizador de citas WhatsApp → Sistema local Vet-Darlie
# Generado por AgentKit

"""
Descarga las citas agendadas por WhatsApp desde Railway
e inserta las nuevas en el sistema de historiales clínicos local.

Uso:
  python sync_citas.py           -> sincroniza automáticamente cada 5 minutos
  python sync_citas.py --ahora   -> sincroniza una vez y termina
"""

import sys
import time
import uuid
import sqlite3
import httpx
from datetime import datetime

RAILWAY_URL = "https://agente-vet-darlie-production.up.railway.app"
VET_DB_PATH = r"C:\Users\oroci\Desktop\Vet-Darlie\vet-historial\prisma\dev.db"
INTERVALO_MINUTOS = 5


def _conn():
    return sqlite3.connect(VET_DB_PATH)


def _asegurar_tabla_sync(conn):
    """Crea la tabla de control de sincronización si no existe."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS _agentkit_sync (
            cita_id TEXT PRIMARY KEY,
            synced_at TEXT NOT NULL
        )
    """)
    conn.commit()


def sincronizar():
    """Descarga citas de Railway e inserta las nuevas en vet-historial."""
    ahora = datetime.now().strftime("%H:%M:%S")
    print(f"[{ahora}] Sincronizando citas con Railway...")

    try:
        response = httpx.get(f"{RAILWAY_URL}/citas", timeout=15)
        response.raise_for_status()
        data = response.json()
        citas = data.get("citas", [])
    except Exception as e:
        print(f"  Error al conectar con Railway: {e}")
        return

    if not citas:
        print("  Sin citas en Railway todavía.")
        return

    conn = _conn()
    _asegurar_tabla_sync(conn)
    cur = conn.cursor()
    nuevas = 0

    for cita in citas:
        cita_id = cita.get("id")
        if not cita_id:
            continue

        # Verificar si ya fue sincronizada
        cur.execute("SELECT cita_id FROM _agentkit_sync WHERE cita_id = ?", (cita_id,))
        if cur.fetchone():
            continue

        # Buscar o crear dueño
        cur.execute("SELECT id FROM Dueno WHERE telefono = ?", (cita["telefono"],))
        dueno = cur.fetchone()
        if dueno:
            dueno_id = dueno[0]
        else:
            dueno_id = str(uuid.uuid4())
            cur.execute(
                "INSERT INTO Dueno (id, nombre, telefono, createdAt) VALUES (?, ?, ?, ?)",
                (dueno_id, cita["nombre_dueno"], cita["telefono"], datetime.utcnow().isoformat()),
            )

        # Buscar o crear mascota
        cur.execute(
            "SELECT id FROM Mascota WHERE duenoPk = ? AND nombre = ?",
            (dueno_id, cita["nombre_mascota"]),
        )
        mascota = cur.fetchone()
        if mascota:
            mascota_id = mascota[0]
        else:
            mascota_id = str(uuid.uuid4())
            cur.execute(
                "INSERT INTO Mascota (id, duenoPk, nombre, especie, sexo, createdAt) VALUES (?, ?, ?, ?, ?, ?)",
                (mascota_id, dueno_id, cita["nombre_mascota"], cita["especie"], "desconocido", datetime.utcnow().isoformat()),
            )

        # Insertar cita en vet-historial
        cita_vet_id = str(uuid.uuid4())
        cur.execute(
            "INSERT INTO Cita (id, mascotaId, fecha, hora, motivo, estado, createdAt) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (cita_vet_id, mascota_id, cita["fecha"], cita["hora"], cita["servicio"], "pendiente", datetime.utcnow().isoformat()),
        )

        # Marcar como sincronizada
        cur.execute(
            "INSERT INTO _agentkit_sync (cita_id, synced_at) VALUES (?, ?)",
            (cita_id, datetime.utcnow().isoformat()),
        )
        nuevas += 1
        print(f"  + {cita['nombre_mascota']} ({cita['especie']}) — {cita['servicio']} el {cita['fecha']} a las {cita['hora']}")

    conn.commit()
    conn.close()

    if nuevas == 0:
        print("  Sin citas nuevas.")
    else:
        print(f"  {nuevas} cita(s) sincronizada(s) en el sistema de historiales.")


def main():
    modo_unico = "--ahora" in sys.argv

    print()
    print("=" * 52)
    print("  AgentKit — Sincronizador de Citas WhatsApp")
    print("=" * 52)

    if modo_unico:
        print("  Modo: sincronización única")
        print()
        sincronizar()
        print()
    else:
        print(f"  Modo: automático cada {INTERVALO_MINUTOS} minutos")
        print("  Presiona Ctrl+C para detener")
        print("  Tip: usa '--ahora' para sincronizar una vez y salir")
        print()
        sincronizar()
        while True:
            time.sleep(INTERVALO_MINUTOS * 60)
            sincronizar()


if __name__ == "__main__":
    main()
