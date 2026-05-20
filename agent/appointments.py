# agent/appointments.py — Almacén de citas en la base de datos de Railway
# Generado por AgentKit

import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Boolean, select
from sqlalchemy.orm import Mapped, mapped_column
from agent.memory import Base, async_session


class CitaAgendada(Base):
    """Cita registrada via WhatsApp — se sincroniza al sistema local."""
    __tablename__ = "citas_agendadas"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    nombre_dueno: Mapped[str] = mapped_column(String(100))
    telefono: Mapped[str] = mapped_column(String(50))
    nombre_mascota: Mapped[str] = mapped_column(String(100))
    especie: Mapped[str] = mapped_column(String(20))
    servicio: Mapped[str] = mapped_column(String(200))
    fecha: Mapped[str] = mapped_column(String(20))
    hora: Mapped[str] = mapped_column(String(10))
    estado: Mapped[str] = mapped_column(String(20), default="pendiente")
    sincronizada: Mapped[bool] = mapped_column(Boolean, default=False)
    creada: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


async def guardar_cita(
    nombre_dueno: str,
    telefono: str,
    nombre_mascota: str,
    especie: str,
    servicio: str,
    fecha: str,
    hora: str,
) -> dict:
    """Guarda una cita agendada via WhatsApp en la base de datos de Railway."""
    cita_id = str(uuid.uuid4())
    async with async_session() as session:
        cita = CitaAgendada(
            id=cita_id,
            nombre_dueno=nombre_dueno,
            telefono=telefono,
            nombre_mascota=nombre_mascota,
            especie=especie,
            servicio=servicio,
            fecha=fecha,
            hora=hora,
            estado="pendiente",
            sincronizada=False,
            creada=datetime.utcnow(),
        )
        session.add(cita)
        await session.commit()
    return {
        "id": cita_id,
        "nombre_dueno": nombre_dueno,
        "telefono": telefono,
        "nombre_mascota": nombre_mascota,
        "especie": especie,
        "servicio": servicio,
        "fecha": fecha,
        "hora": hora,
        "estado": "pendiente",
    }


async def obtener_todas_citas(limite: int = 50) -> list[dict]:
    """Retorna todas las citas agendadas via WhatsApp."""
    async with async_session() as session:
        result = await session.execute(
            select(CitaAgendada).order_by(CitaAgendada.creada.desc()).limit(limite)
        )
        citas = result.scalars().all()
        return [
            {
                "id": c.id,
                "nombre_dueno": c.nombre_dueno,
                "telefono": c.telefono,
                "nombre_mascota": c.nombre_mascota,
                "especie": c.especie,
                "servicio": c.servicio,
                "fecha": c.fecha,
                "hora": c.hora,
                "estado": c.estado,
                "sincronizada": c.sincronizada,
                "creada": c.creada.isoformat() if c.creada else None,
            }
            for c in citas
        ]
