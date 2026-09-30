"""Historial de transcripciones persistido en SQLite."""

import json
import re
import sqlite3
import unicodedata
from contextlib import closing
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.transcriber import ResultadoTranscripcion, SegmentoTranscripcion


RAIZ_PROYECTO = Path(__file__).resolve().parent.parent
RUTA_POR_DEFECTO = RAIZ_PROYECTO / "data" / "historial.db"
VERSION_ESQUEMA = 1

ESQUEMA = """
CREATE TABLE IF NOT EXISTS transcripciones (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    titulo               TEXT    NOT NULL,
    titulo_editado       INTEGER NOT NULL DEFAULT 0,   -- 1 si el usuario lo cambió a mano
    archivo_nombre       TEXT    NOT NULL,
    archivo_ruta         TEXT    NOT NULL,
    creado_en            TEXT    NOT NULL,             -- ISO 8601, hora local
    actualizado_en       TEXT    NOT NULL,
    duracion_segundos    REAL,
    idioma               TEXT,
    probabilidad_idioma  REAL,
    modelo_whisper       TEXT,
    texto                TEXT    NOT NULL,
    segmentos_json       TEXT    NOT NULL,
    resumen              TEXT,
    resumen_modelo       TEXT,
    resumen_en           TEXT,
    minuta               TEXT,
    minuta_modelo        TEXT,
    minuta_en            TEXT
);
CREATE INDEX IF NOT EXISTS idx_transcripciones_creado ON transcripciones (creado_en DESC);
"""

DOCUMENTOS = ("resumen", "minuta")


@dataclass
class EntradaHistorial:
    id: int
    titulo: str
    archivo_nombre: str
    archivo_ruta: str
    creado_en: str
    actualizado_en: str
    duracion_segundos: Optional[float]
    idioma: Optional[str]
    modelo_whisper: Optional[str]
    tiene_resumen: bool
    tiene_minuta: bool
    titulo_editado: bool = False
    probabilidad_idioma: Optional[float] = None
    texto: str = ""
    segmentos: list = field(default_factory=list)
    resumen: Optional[str] = None
    resumen_modelo: Optional[str] = None
    minuta: Optional[str] = None
    minuta_modelo: Optional[str] = None

    @property
    def archivo_existe(self) -> bool:
        return Path(self.archivo_ruta).exists()

    def a_resultado(self) -> ResultadoTranscripcion:
        """Reconstruye el resultado de la transcripción para volver a mostrarlo o exportarlo."""
        return ResultadoTranscripcion(
            texto_completo=self.texto,
            segmentos=[SegmentoTranscripcion(**s) for s in self.segmentos],
            idioma_detectado=self.idioma or "",
            probabilidad_idioma=self.probabilidad_idioma or 0.0,
            duracion_total=self.duracion_segundos or 0.0,
        )


def _ahora() -> str:
    return datetime.now().isoformat(timespec="seconds")


def normalizar(texto: Optional[str]) -> Optional[str]:
    """Minúsculas y sin acentos, para búsquedas: 'Reunión' -> 'reunion'."""
    if texto is None:
        return None
    descompuesto = unicodedata.normalize("NFD", texto)
    return "".join(c for c in descompuesto if not unicodedata.combining(c)).casefold()


def titulo_desde_minuta(minuta: str) -> Optional[str]:
    """Extrae el título de la línea '# Minuta: <título>'."""
    m = re.search(r"^#\s*Minuta:\s*(.+?)\s*$", minuta, re.MULTILINE)
    return m.group(1).strip("*_ ") if m else None


class Historial:
    """Acceso al historial. Abre una conexión por operación, así se puede usar desde varios hilos."""

    def __init__(self, ruta: Optional[str] = None):
        ruta = Path(ruta) if ruta else RUTA_POR_DEFECTO
        self.ruta = ruta if ruta.is_absolute() else RAIZ_PROYECTO / ruta
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._conectar()) as con, con:
            con.executescript(ESQUEMA)
            con.execute(f"PRAGMA user_version = {VERSION_ESQUEMA}")

    def _conectar(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.ruta, timeout=10)
        con.row_factory = sqlite3.Row
        con.create_function("normalizar", 1, normalizar, deterministic=True)
        return con

    # ------------------------------------------------------------ Escritura

    def crear(
        self,
        archivo_ruta: str,
        resultado: ResultadoTranscripcion,
        modelo_whisper: Optional[str] = None,
        titulo: Optional[str] = None,
    ) -> int:
        ruta = Path(archivo_ruta)
        ahora = _ahora()
        segmentos = [
            {"inicio": s.inicio, "fin": s.fin, "texto": s.texto, "palabras": s.palabras}
            for s in resultado.segmentos
        ]
        with closing(self._conectar()) as con, con:
            cursor = con.execute(
                """INSERT INTO transcripciones (
                       titulo, titulo_editado, archivo_nombre, archivo_ruta, creado_en, actualizado_en,
                       duracion_segundos, idioma, probabilidad_idioma, modelo_whisper, texto, segmentos_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    titulo or ruta.stem, int(bool(titulo)), ruta.name, str(ruta.resolve()), ahora, ahora,
                    resultado.duracion_total, resultado.idioma_detectado, resultado.probabilidad_idioma,
                    modelo_whisper, resultado.texto_completo, json.dumps(segmentos, ensure_ascii=False),
                ),
            )
            return cursor.lastrowid

    def guardar_documento(self, id_: int, tipo: str, contenido: str, modelo: Optional[str] = None) -> None:
        """Guarda el resumen o la minuta. Con la minuta, si el título no se editó a mano, se toma de ella."""
        if tipo not in DOCUMENTOS:
            raise ValueError(f"Tipo de documento no válido: {tipo}")
        ahora = _ahora()
        with closing(self._conectar()) as con, con:
            con.execute(
                f"UPDATE transcripciones SET {tipo} = ?, {tipo}_modelo = ?, {tipo}_en = ?, actualizado_en = ? "
                "WHERE id = ?",
                (contenido, modelo, ahora, ahora, id_),
            )
            titulo = titulo_desde_minuta(contenido) if tipo == "minuta" else None
            if titulo:
                con.execute(
                    "UPDATE transcripciones SET titulo = ? WHERE id = ? AND titulo_editado = 0", (titulo, id_)
                )

    def renombrar(self, id_: int, titulo: str) -> None:
        titulo = titulo.strip()
        if not titulo:
            raise ValueError("El título no puede estar vacío")
        with closing(self._conectar()) as con, con:
            con.execute(
                "UPDATE transcripciones SET titulo = ?, titulo_editado = 1, actualizado_en = ? WHERE id = ?",
                (titulo, _ahora(), id_),
            )

    def eliminar(self, id_: int) -> None:
        with closing(self._conectar()) as con, con:
            con.execute("DELETE FROM transcripciones WHERE id = ?", (id_,))

    # ------------------------------------------------------------ Lectura

    def listar(self, busqueda: str = "", limite: int = 500) -> list[EntradaHistorial]:
        """Entradas más recientes primero. `busqueda` filtra por título, archivo, texto, resumen o minuta."""
        sql = """SELECT id, titulo, titulo_editado, archivo_nombre, archivo_ruta, creado_en, actualizado_en,
                        duracion_segundos, idioma, modelo_whisper,
                        resumen IS NOT NULL AS tiene_resumen, minuta IS NOT NULL AS tiene_minuta
                 FROM transcripciones"""
        parametros: list = []
        busqueda = busqueda.strip()
        if busqueda:
            # Se escapan los comodines de LIKE para buscar el texto literal
            escapada = normalizar(busqueda).replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            patron = f"%{escapada}%"
            sql += " WHERE " + " OR ".join(
                f"normalizar({c}) LIKE ? ESCAPE '\\'" for c in ("titulo", "archivo_nombre", "texto", "resumen", "minuta")
            )
            parametros = [patron] * 5
        sql += " ORDER BY creado_en DESC, id DESC LIMIT ?"
        parametros.append(limite)
        with closing(self._conectar()) as con:
            return [
                EntradaHistorial(**{**dict(fila), "tiene_resumen": bool(fila["tiene_resumen"]),
                                    "tiene_minuta": bool(fila["tiene_minuta"]),
                                    "titulo_editado": bool(fila["titulo_editado"])})
                for fila in con.execute(sql, parametros)
            ]

    def obtener(self, id_: int) -> Optional[EntradaHistorial]:
        with closing(self._conectar()) as con:
            fila = con.execute("SELECT * FROM transcripciones WHERE id = ?", (id_,)).fetchone()
        if fila is None:
            return None
        return EntradaHistorial(
            id=fila["id"],
            titulo=fila["titulo"],
            titulo_editado=bool(fila["titulo_editado"]),
            archivo_nombre=fila["archivo_nombre"],
            archivo_ruta=fila["archivo_ruta"],
            creado_en=fila["creado_en"],
            actualizado_en=fila["actualizado_en"],
            duracion_segundos=fila["duracion_segundos"],
            idioma=fila["idioma"],
            probabilidad_idioma=fila["probabilidad_idioma"],
            modelo_whisper=fila["modelo_whisper"],
            texto=fila["texto"],
            segmentos=json.loads(fila["segmentos_json"]),
            resumen=fila["resumen"],
            resumen_modelo=fila["resumen_modelo"],
            minuta=fila["minuta"],
            minuta_modelo=fila["minuta_modelo"],
            tiene_resumen=fila["resumen"] is not None,
            tiene_minuta=fila["minuta"] is not None,
        )
