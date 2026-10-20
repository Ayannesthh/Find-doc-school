"""Camada de dados do Find Doc School.

SQLite para uso local. Defina DATABASE_URL para banco PostgreSQL persistente
em hospedagem (por exemplo, um PostgreSQL gerenciado).
"""
from __future__ import annotations

import base64
import json
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Column, ForeignKey, Integer, LargeBinary, MetaData, String, Table, Text,
    create_engine, delete, insert, select, update,
    or_,
)

metadata = MetaData()

documents = Table(
    "documents", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("code", String(50), unique=True),
    Column("title", String(250), nullable=False),
    Column("doc_type", String(100), nullable=False),
    Column("description", Text, nullable=False, default=""),
    Column("room", String(100), nullable=False),
    Column("cabinet", String(100), nullable=False),
    Column("drawer", String(100), nullable=False, default=""),
    Column("box", String(100), nullable=False, default=""),
    Column("folder", String(100), nullable=False),
    Column("creator", String(120), nullable=False),
    Column("status", String(20), nullable=False, default="Disponível"),
    Column("holder", String(120), nullable=False, default=""),
    Column("destination", String(120), nullable=False, default=""),
    Column("created_at", String(32), nullable=False),
    Column("updated_at", String(32), nullable=False),
)

attachments = Table(
    "attachments", metadata,
    Column("doc_id", Integer, ForeignKey("documents.id"), primary_key=True),
    Column("filename", String(255), nullable=False),
    Column("content_type", String(120), nullable=False),
    Column("content", LargeBinary, nullable=False),
)

movements = Table(
    "movements", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("doc_id", Integer, ForeignKey("documents.id"), nullable=False),
    Column("action", String(40), nullable=False),
    Column("actor", String(120), nullable=False),
    Column("destination", String(120), nullable=False, default=""),
    Column("notes", Text, nullable=False, default=""),
    Column("occurred_at", String(32), nullable=False),
)

FIELDS = ["title", "doc_type", "description", "room", "cabinet", "drawer", "box", "folder", "creator"]


def now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def normalize_db_url(db_url: str) -> str:
    if db_url.startswith("postgres://"):
        return "postgresql+psycopg://" + db_url[len("postgres://"):]
    if db_url.startswith("postgresql://"):
        return "postgresql+psycopg://" + db_url[len("postgresql://"):]
    return db_url


class Repository:
    def __init__(self, db_url: str):
        db_url = normalize_db_url(db_url)
        opts: dict[str, Any] = {"pool_pre_ping": True}
        if db_url.startswith("sqlite"):
            opts["connect_args"] = {"check_same_thread": False}
        self.engine = create_engine(db_url, **opts)
        metadata.create_all(self.engine)

    def create_document(self, info: dict, file_data: tuple[str, str, bytes] | None = None) -> str:
        payload = {key: (info.get(key) or "").strip() for key in FIELDS}
        if not all(payload[k] for k in ("title", "doc_type", "room", "cabinet", "folder", "creator")):
            raise ValueError("Preencha nome, categoria, sala, armário, pasta e responsável.")
        stamp = now()
        with self.engine.begin() as con:
            result = con.execute(insert(documents).values(**payload, status="Disponível", holder="", destination="", created_at=stamp, updated_at=stamp))
            doc_id = result.inserted_primary_key[0]
            # Em restaurações, o código original pode não coincidir com o ID novo.
            # Evite colisões com códigos importados de backups anteriores.
            existing_codes = set(con.execute(select(documents.c.code)).scalars())
            seq = doc_id
            code = f"FDS-{seq:05d}"
            while code in existing_codes:
                seq += 1
                code = f"FDS-{seq:05d}"
            con.execute(update(documents).where(documents.c.id == doc_id).values(code=code))
            if file_data:
                name, content_type, content = file_data
                con.execute(insert(attachments).values(doc_id=doc_id, filename=name, content_type=content_type, content=content))
        return code

    def list_documents(self, query: str = "") -> list[dict]:
        stmt = select(documents)
        if query.strip():
            token = f"%{query.strip()}%"
            stmt = stmt.where(or_(
                documents.c.code.ilike(token),
                documents.c.title.ilike(token),
                documents.c.doc_type.ilike(token),
                documents.c.room.ilike(token),
                documents.c.cabinet.ilike(token),
                documents.c.folder.ilike(token),
            ))
        stmt = stmt.order_by(documents.c.id.desc())
        with self.engine.connect() as con:
            return [dict(row) for row in con.execute(stmt).mappings()]

    def get_document(self, code: str) -> dict | None:
        with self.engine.connect() as con:
            row = con.execute(select(documents).where(documents.c.code == code)).mappings().first()
            return dict(row) if row else None

    def get_attachment(self, doc_id: int) -> dict | None:
        with self.engine.connect() as con:
            row = con.execute(select(attachments).where(attachments.c.doc_id == doc_id)).mappings().first()
            return dict(row) if row else None

    def set_attachment(self, code: str, file_data: tuple[str, str, bytes]) -> None:
        doc = self.get_document(code)
        if not doc:
            raise ValueError("Documento não encontrado.")
        name, typ, payload = file_data
        with self.engine.begin() as con:
            con.execute(delete(attachments).where(attachments.c.doc_id == doc["id"]))
            con.execute(insert(attachments).values(doc_id=doc["id"], filename=name, content_type=typ, content=payload))
            con.execute(update(documents).where(documents.c.id == doc["id"]).values(updated_at=now()))

    def update_document(self, code: str, info: dict) -> None:
        payload = {key: (info.get(key) or "").strip() for key in FIELDS}
        if not all(payload[k] for k in ("title", "doc_type", "room", "cabinet", "folder", "creator")):
            raise ValueError("Preencha os campos obrigatórios.")
        with self.engine.begin() as con:
            con.execute(update(documents).where(documents.c.code == code).values(**payload, updated_at=now()))

    def delete_document(self, code: str) -> bool:
        doc = self.get_document(code)
        if not doc:
            return False
        with self.engine.begin() as con:
            con.execute(delete(attachments).where(attachments.c.doc_id == doc["id"]))
            con.execute(delete(movements).where(movements.c.doc_id == doc["id"]))
            con.execute(delete(documents).where(documents.c.id == doc["id"]))
        return True

    def move_document(self, code: str, action: str, actor: str, destination: str = "", notes: str = "") -> None:
        actor = actor.strip()
        destination = destination.strip()
        if not actor:
            raise ValueError("Informe o nome do responsável.")
        if action not in ("Retirada", "Devolução"):
            raise ValueError("Movimentação inválida.")
        if action == "Retirada" and not destination:
            raise ValueError("Informe o setor ou destino da retirada.")
        with self.engine.begin() as con:
            # Locks the document row on PostgreSQL to prevent competing updates.
            stmt = select(documents).where(documents.c.code == code)
            if self.engine.dialect.name == "postgresql":
                stmt = stmt.with_for_update()
            doc = con.execute(stmt).mappings().first()
            if not doc:
                raise ValueError("Documento não encontrado.")
            if action == "Retirada" and doc["status"] != "Disponível":
                raise ValueError("O documento já está emprestado.")
            if action == "Devolução" and doc["status"] != "Emprestado":
                raise ValueError("O documento não está emprestado.")
            con.execute(update(documents).where(documents.c.id == doc["id"]).values(
                status="Emprestado" if action == "Retirada" else "Disponível",
                holder=actor if action == "Retirada" else "",
                destination=destination if action == "Retirada" else "",
                updated_at=now(),
            ))
            con.execute(insert(movements).values(
                doc_id=doc["id"], action=action, actor=actor,
                destination=destination, notes=notes.strip(), occurred_at=now(),
            ))

    def list_movements(self, doc_id: int | None = None) -> list[dict]:
        stmt = select(
            movements.c.id, documents.c.code, documents.c.title,
            movements.c.action, movements.c.actor, movements.c.destination,
            movements.c.notes, movements.c.occurred_at,
        ).select_from(movements.join(documents, movements.c.doc_id == documents.c.id))
        if doc_id is not None:
            stmt = stmt.where(movements.c.doc_id == doc_id)
        stmt = stmt.order_by(movements.c.id.desc())
        with self.engine.connect() as con:
            return [dict(row) for row in con.execute(stmt).mappings()]

    def backup_json(self) -> bytes:
        docs = self.list_documents()
        with self.engine.connect() as con:
            for doc in docs:
                attach = con.execute(select(attachments).where(attachments.c.doc_id == doc["id"])).mappings().first()
                doc["attachment"] = (
                    {"filename": attach["filename"], "content_type": attach["content_type"],
                     "base64": base64.b64encode(attach["content"]).decode("ascii")}
                    if attach else None
                )
            all_moves = [dict(row) for row in con.execute(select(movements)).mappings()]
        data = {"app": "Find Doc School", "backup_version": 1, "documents": docs, "movements": all_moves, "generated_at": now()}
        return json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")

    def restore_json(self, raw: bytes) -> tuple[int, int]:
        if len(raw) > 20 * 1024 * 1024:
            raise ValueError("O backup excede 20 MB.")
        data = json.loads(raw)
        if data.get("app") != "Find Doc School" or data.get("backup_version") != 1:
            raise ValueError("Arquivo de backup não reconhecido.")
        input_docs = data.get("documents", [])
        input_moves = data.get("movements", [])
        if not isinstance(input_docs, list) or not isinstance(input_moves, list) or len(input_docs) > 5000:
            raise ValueError("Backup inválido ou muito grande.")
        restored_docs = 0
        restored_moves = 0
        with self.engine.begin() as con:
            existing = {row[0] for row in con.execute(select(documents.c.code))}
            id_map = {}
            for doc in input_docs:
                code = doc.get("code", "")
                if not isinstance(code, str) or not code.startswith("FDS-"):
                    raise ValueError("Backup contém códigos inválidos.")
                if code in existing:
                    continue  # Mesclagem: evita duplicar documentos existentes.
                values = {f: str(doc.get(f) or "") for f in FIELDS}
                values.update({
                    "code": code, "status": doc.get("status") if doc.get("status") in ("Disponível", "Emprestado") else "Disponível",
                    "holder": str(doc.get("holder") or ""), "destination": str(doc.get("destination") or ""),
                    "created_at": str(doc.get("created_at") or now()), "updated_at": str(doc.get("updated_at") or now()),
                })
                result = con.execute(insert(documents).values(**values))
                new_id = result.inserted_primary_key[0]
                id_map[doc.get("id")] = new_id
                attach = doc.get("attachment")
                if attach:
                    payload = base64.b64decode(attach["base64"], validate=True)
                    if len(payload) > 5 * 1024 * 1024:
                        raise ValueError("Anexo no backup excede 5 MB.")
                    con.execute(insert(attachments).values(
                        doc_id=new_id, filename=str(attach["filename"]),
                        content_type=str(attach.get("content_type") or "application/octet-stream"), content=payload,
                    ))
                restored_docs += 1
                existing.add(code)
            for move in input_moves:
                doc_id = id_map.get(move.get("doc_id"))
                if doc_id is None:
                    continue
                if move.get("action") not in ("Retirada", "Devolução"):
                    continue
                con.execute(insert(movements).values(
                    doc_id=doc_id, action=move["action"], actor=str(move.get("actor") or ""),
                    destination=str(move.get("destination") or ""), notes=str(move.get("notes") or ""),
                    occurred_at=str(move.get("occurred_at") or now()),
                ))
                restored_moves += 1
        return restored_docs, restored_moves
