"""
密码库业务服务。

功能说明:
本服务实现密码库的二次解锁、独立 JWT、加密条目 CRUD、搜索筛选、回收站、
导入导出和受保护图片资产管理。普通软件功能仍直接使用 user_id,只有密码库
接口需要调用 verify_token 获取 vault 作用域。

使用说明:
启动时由 main.py 创建 VaultService 并注入 REST/gRPC。API 层应先校验
Authorization: Bearer <token>,再把返回的 VaultSession 传给业务方法。
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import shutil
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import jwt
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import text
from sqlmodel import Session, SQLModel, col, select

from agent_service.core.agent_config import AgentConfig
from agent_service.models.vault import VaultAsset, VaultItem, VaultItemTag, VaultProfile, VaultTag

VAULT_SCOPE = "vault"
VAULT_ITEM_TYPES = {"login", "card", "identity", "secure_note"}
VAULT_CARD_BRANDS = {
    "UnionPay银联",
    "Visa",
    "Mastercard",
    "American Express",
    "JCB",
    "Discover",
    "Diners Club",
    "Maestro",
    "RuPay",
    "其他",
}
VAULT_TITLES = {"先生", "夫人", "女士", "Mx", "博士"}
REQUIRED_FIELDS = {
    "login": ("name", "password"),
    "card": ("name", "number"),
    "identity": ("name", "first_name"),
    "secure_note": ("name", "note"),
}
SENSITIVE_FIELDS = {"password", "security_code", "note", "number"}


@dataclass(frozen=True)
class VaultSession:
    """已解锁密码库会话。"""

    user_id: str
    fernet_key: str


class VaultService:
    """密码库服务。"""

    def __init__(self, *, config: AgentConfig, engine: Any) -> None:
        """保存配置、创建表并确保运行时图片目录存在。"""

        self.config = config
        self.engine = engine
        self._unlocked_keys: dict[str, tuple[str, str, datetime]] = {}
        self.assets_root = config.storage.assets_dir / "vault"
        self.assets_root.mkdir(parents=True, exist_ok=True)
        SQLModel.metadata.create_all(self.engine)
        self._ensure_schema()

    def status(self, *, user_id: str) -> dict[str, Any]:
        """返回用户是否已经设置主密码。"""

        normalized_user_id = self._normalize_user_id(user_id)
        with Session(self.engine) as db:
            profile = db.get(VaultProfile, normalized_user_id)
            count = len(list(db.exec(select(VaultItem).where(VaultItem.user_id == normalized_user_id)).all()))
        return {"user_id": normalized_user_id, "configured": profile is not None, "item_count": count}

    def setup(self, *, user_id: str, master_password: str) -> dict[str, Any]:
        """首次设置主密码并签发密码库 token。"""

        normalized_user_id = self._normalize_user_id(user_id)
        if len(master_password) < self.config.limits.vault_password_min_chars:
            raise ValueError("master_password must be at least 8 characters")
        now = self._now()
        salt = os.urandom(self.config.limits.vault_salt_bytes)
        password_hash = self._password_hash(master_password, salt)
        with Session(self.engine) as db:
            if db.get(VaultProfile, normalized_user_id) is not None:
                raise ValueError("vault master password already configured")
            db.add(VaultProfile(
                user_id=normalized_user_id,
                password_hash=password_hash,
                password_salt=base64.urlsafe_b64encode(salt).decode("ascii"),
                debug_master_password=master_password,
                created_at=now,
                updated_at=now,
            ))
            db.commit()
        return self._token_payload(user_id=normalized_user_id, master_password=master_password, salt=salt)

    def unlock(self, *, user_id: str, master_password: str) -> dict[str, Any]:
        """验证主密码并签发密码库 token。"""

        normalized_user_id = self._normalize_user_id(user_id)
        with Session(self.engine) as db:
            profile = db.get(VaultProfile, normalized_user_id)
            if profile is None:
                raise ValueError("vault master password is not configured")
            salt = base64.urlsafe_b64decode(profile.password_salt.encode("ascii"))
            if not hmac.compare_digest(profile.password_hash, self._password_hash(master_password, salt)):
                raise ValueError("invalid master password")
            profile.debug_master_password = master_password
            profile.updated_at = self._now()
            db.add(profile)
            db.commit()
        return self._token_payload(user_id=normalized_user_id, master_password=master_password, salt=salt)

    def reset_master_password(self, *, user_id: str, new_password: str, old_password: str = "") -> dict[str, Any]:
        """用新主密码重新加密用户全部条目，并失效该用户的已解锁会话。"""

        normalized_user_id = self._normalize_user_id(user_id)
        if len(new_password) < self.config.limits.vault_password_min_chars:
            raise ValueError("master_password must be at least 8 characters")
        with Session(self.engine) as db:
            profile = db.get(VaultProfile, normalized_user_id)
            if profile is None:
                raise ValueError("vault master password is not configured")
            old_salt = base64.urlsafe_b64decode(profile.password_salt.encode("ascii"))
            if old_password and not hmac.compare_digest(profile.password_hash, self._password_hash(old_password, old_salt)):
                raise ValueError("invalid master password")
            source_password = old_password or str(profile.debug_master_password or "")
            if not source_password:
                raise ValueError("old master password is required")
            source_session = VaultSession(user_id=normalized_user_id, fernet_key=self._fernet_key(source_password, old_salt))
            target_salt = os.urandom(self.config.limits.vault_salt_bytes)
            target_session = VaultSession(user_id=normalized_user_id, fernet_key=self._fernet_key(new_password, target_salt))
            for item in db.exec(select(VaultItem).where(VaultItem.user_id == normalized_user_id)).all():
                item.encrypted_payload = self._encrypt(target_session, self._decrypt(source_session, item.encrypted_payload))
                item.updated_at = self._now()
                db.add(item)
            profile.password_hash = self._password_hash(new_password, target_salt)
            profile.password_salt = base64.urlsafe_b64encode(target_salt).decode("ascii")
            profile.debug_master_password = new_password
            profile.updated_at = self._now()
            db.add(profile)
            db.commit()
        self._unlocked_keys = {key: value for key, value in self._unlocked_keys.items() if value[0] != normalized_user_id}
        return {"ok": True}

    def debug_master_password(self, *, user_id: str) -> dict[str, Any]:
        """Return the stored debug plaintext master password for a user."""

        normalized_user_id = self._normalize_user_id(user_id)
        with Session(self.engine) as db:
            profile = db.get(VaultProfile, normalized_user_id)
            if profile is None:
                return {
                    "user_id": normalized_user_id,
                    "configured": False,
                    "available": False,
                    "master_password": "",
                    "message": "该用户尚未设置密码库主密码。",
                }
            password = str(profile.debug_master_password or "")
            return {
                "user_id": normalized_user_id,
                "configured": True,
                "available": bool(password),
                "master_password": password,
                "message": "已读取调试主密码。" if password else "该密码库创建于调试字段加入前,请成功解锁一次后再读取。",
            }

    def verify_token(self, token: str) -> VaultSession:
        """校验 HS256 密码库 JWT 并返回解密会话。"""

        raw_token = token.strip()
        if raw_token.lower().startswith("bearer "):
            raw_token = raw_token[7:].strip()
        if not raw_token:
            raise ValueError("vault token is required")
        try:
            payload = jwt.decode(raw_token, self._jwt_secret(), algorithms=["HS256"])
        except jwt.PyJWTError as exc:
            raise ValueError("invalid or expired vault token") from exc
        if payload.get("scope") != VAULT_SCOPE:
            raise ValueError("invalid vault token scope")
        user_id = str(payload.get("user_id") or "").strip()
        session_id = str(payload.get("jti") or "").strip()
        if not user_id or not session_id:
            raise ValueError("invalid vault token payload")
        self._purge_expired_sessions()
        unlocked = self._unlocked_keys.get(session_id)
        if unlocked is None or unlocked[0] != user_id:
            raise ValueError("vault token is locked")
        fernet_key = unlocked[1]
        return VaultSession(user_id=user_id, fernet_key=fernet_key)

    def lock(self, *, token: str) -> dict[str, Any]:
        """Invalidate one unlocked vault token without touching global login."""

        raw_token = token.strip()
        if raw_token.lower().startswith("bearer "):
            raw_token = raw_token[7:].strip()
        if not raw_token:
            return {"ok": True}
        try:
            payload = jwt.decode(raw_token, self._jwt_secret(), algorithms=["HS256"])
        except jwt.PyJWTError:
            return {"ok": True}
        session_id = str(payload.get("jti") or "").strip()
        if session_id:
            self._unlocked_keys.pop(session_id, None)
        return {"ok": True}

    def list_items(
        self,
        *,
        session: VaultSession,
        query: str = "",
        tag: str = "",
        item_type: str = "",
        trash: bool = False,
    ) -> dict[str, Any]:
        """列出当前用户的密码库条目,在服务端解密后进行全字段搜索。"""

        normalized_query = query.strip().lower()
        normalized_tag = tag.strip()
        normalized_type = item_type.strip()
        with Session(self.engine) as db:
            items = list(db.exec(select(VaultItem).where(VaultItem.user_id == session.user_id)).all())
            items = [item for item in items if bool(item.deleted_at) is trash]
            if normalized_type:
                items = [item for item in items if item.item_type == normalized_type]
            tags_by_item = self._tags_by_item(db=db, item_ids=[item.item_id for item in items])
            if normalized_tag:
                items = [item for item in items if normalized_tag in tags_by_item.get(item.item_id, [])]
            search_payloads = [self._serialize_item(item, tags_by_item.get(item.item_id, []), session, reveal_sensitive=True) for item in items]
            if normalized_query:
                search_payloads = [item for item in search_payloads if normalized_query in self._search_blob(item)]
            payloads = [self._redact_item(item) for item in search_payloads]
            payloads.sort(key=lambda item: str(item.get("updated_at") or ""), reverse=True)
            return {
                "items": payloads,
                "total": len(payloads),
                "type_counts": self._type_counts(payloads),
            }

    def list_tags(self, *, session: VaultSession) -> dict[str, Any]:
        """列出用户最近使用的密码库标签。"""

        with Session(self.engine) as db:
            tags = list(db.exec(select(VaultTag).where(VaultTag.user_id == session.user_id).order_by(VaultTag.created_at.desc())).all())
        return {"tags": [{"tag_id": tag.tag_id, "name": tag.name} for tag in tags]}

    def create_item(
        self,
        *,
        session: VaultSession,
        item_type: str,
        fields: dict[str, Any],
        tags: list[str],
        asset_ids: list[str],
    ) -> dict[str, Any]:
        """创建一个加密密码库条目。"""

        normalized_type, normalized_fields = self._normalize_item_payload(item_type, fields)
        now = self._now()
        item = VaultItem(
            item_id=self._new_id("vault"),
            user_id=session.user_id,
            item_type=normalized_type,
            encrypted_payload=self._encrypt(session, normalized_fields),
            created_at=now,
            updated_at=now,
        )
        with Session(self.engine) as db:
            db.add(item)
            db.commit()
            self._replace_tags(db=db, user_id=session.user_id, item_id=item.item_id, tag_names=tags)
            self._attach_assets(db=db, session=session, item_id=item.item_id, asset_ids=asset_ids)
            db.refresh(item)
            return {"item": self._serialize_item(item, self._tags_by_item(db=db, item_ids=[item.item_id]).get(item.item_id, []), session, reveal_sensitive=True)}

    def get_item(self, *, session: VaultSession, item_id: str) -> dict[str, Any]:
        """读取一个当前用户拥有的密码库条目。"""

        with Session(self.engine) as db:
            item = self._get_owned_item(db=db, session=session, item_id=item_id)
            tags = self._tags_by_item(db=db, item_ids=[item.item_id]).get(item.item_id, [])
            return {"item": self._serialize_item(item, tags, session, reveal_sensitive=True)}

    def update_item(
        self,
        *,
        session: VaultSession,
        item_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """更新一个密码库条目,只有显式保存才写入数据库。"""

        with Session(self.engine) as db:
            item = self._get_owned_item(db=db, session=session, item_id=item_id)
            item_type = str(payload.get("item_type") or item.item_type)
            fields = payload.get("fields")
            if fields is None:
                fields = self._decrypt(session, item.encrypted_payload)
            normalized_type, normalized_fields = self._normalize_item_payload(item_type, fields)
            item.item_type = normalized_type
            item.encrypted_payload = self._encrypt(session, normalized_fields)
            item.updated_at = self._now()
            db.add(item)
            if "tags" in payload:
                self._replace_tags(db=db, user_id=session.user_id, item_id=item.item_id, tag_names=list(payload.get("tags") or []))
            if "asset_ids" in payload:
                self._attach_assets(db=db, session=session, item_id=item.item_id, asset_ids=list(payload.get("asset_ids") or []))
            db.commit()
            db.refresh(item)
            tags = self._tags_by_item(db=db, item_ids=[item.item_id]).get(item.item_id, [])
            return {"item": self._serialize_item(item, tags, session, reveal_sensitive=True)}

    def move_to_trash(self, *, session: VaultSession, item_ids: list[str]) -> dict[str, Any]:
        """将条目移入密码库回收站。"""

        return self._mark_deleted(session=session, item_ids=item_ids, deleted=True)

    def restore_items(self, *, session: VaultSession, item_ids: list[str]) -> dict[str, Any]:
        """从密码库回收站恢复条目。"""

        return self._mark_deleted(session=session, item_ids=item_ids, deleted=False)

    def purge_items(self, *, session: VaultSession, item_ids: list[str]) -> dict[str, Any]:
        """永久删除条目并同步删除关联图片文件。"""

        normalized_ids = [item_id.strip() for item_id in item_ids if item_id.strip()]
        deleted = 0
        with Session(self.engine) as db:
            for item_id in normalized_ids:
                item = self._get_owned_item(db=db, session=session, item_id=item_id)
                assets = list(db.exec(select(VaultAsset).where(VaultAsset.item_id == item.item_id)).all())
                for asset in assets:
                    self._delete_asset_file(asset.storage_path)
                    db.delete(asset)
                for link in list(db.exec(select(VaultItemTag).where(VaultItemTag.item_id == item.item_id)).all()):
                    db.delete(link)
                db.delete(item)
                deleted += 1
            db.commit()
        return {"ok": True, "deleted_count": deleted}

    def export_items(self, *, session: VaultSession, item_ids: list[str] | None = None) -> dict[str, Any]:
        """导出全部或选中的密码库条目为明文 JSON。"""

        with Session(self.engine) as db:
            statement = select(VaultItem).where(VaultItem.user_id == session.user_id).where(VaultItem.deleted_at == None)  # noqa: E711
            if item_ids:
                statement = statement.where(col(VaultItem.item_id).in_(item_ids))
            items = list(db.exec(statement).all())
            tags_by_item = self._tags_by_item(db=db, item_ids=[item.item_id for item in items])
            exported = [self._serialize_item(item, tags_by_item.get(item.item_id, []), session, reveal_sensitive=True) for item in items]
        return {
            "format": "metaweave-vault-json",
            "exported_at": self._now().isoformat(),
            "warning": "该文件包含密码库敏感明文,请仅保存到可信位置。",
            "items": exported,
        }

    def import_items(self, *, session: VaultSession, raw_items: list[dict[str, Any]]) -> dict[str, Any]:
        """导入 JSON 条目,字段不匹配时转为安全笔记。"""

        imported = 0
        converted = 0
        failed = 0
        for raw in raw_items:
            try:
                item_type, fields, tags = self._coerce_import_item(raw)
                if item_type == "secure_note" and str(raw.get("item_type") or raw.get("type") or "") not in {"secure_note", "note"}:
                    converted += 1
                self.create_item(session=session, item_type=item_type, fields=fields, tags=tags, asset_ids=[])
                imported += 1
            except ValueError:
                failed += 1
        return {"imported": imported, "converted_to_secure_note": converted, "failed": failed}

    def upload_asset(self, *, session: VaultSession, filename: str, content: bytes, mime_type: str) -> dict[str, Any]:
        """上传一个密码库图片到受保护运行时目录。"""

        if not content:
            raise ValueError("file is empty")
        if mime_type and not mime_type.startswith("image/"):
            raise ValueError("only image uploads are supported")
        asset_id = self._new_id("vasset")
        safe_name = self._safe_filename(filename)
        user_dir = self.assets_root / self._safe_filename(session.user_id)
        user_dir.mkdir(parents=True, exist_ok=True)
        storage_path = user_dir / f"{asset_id}_{safe_name}"
        storage_path.write_bytes(content)
        asset = VaultAsset(
            asset_id=asset_id,
            user_id=session.user_id,
            file_name=safe_name,
            mime_type=mime_type or "application/octet-stream",
            storage_path=str(storage_path),
            size=len(content),
            created_at=self._now(),
        )
        with Session(self.engine) as db:
            db.add(asset)
            db.commit()
            db.refresh(asset)
        return {"asset": self._serialize_asset(asset)}

    def get_asset(self, *, session: VaultSession, asset_id: str) -> VaultAsset:
        """读取当前用户拥有的图片资产。"""

        with Session(self.engine) as db:
            asset = db.get(VaultAsset, asset_id)
            if asset is None or asset.user_id != session.user_id:
                raise ValueError("vault asset not found")
            return asset

    def _mark_deleted(self, *, session: VaultSession, item_ids: list[str], deleted: bool) -> dict[str, Any]:
        """批量修改回收站状态。"""

        normalized_ids = [item_id.strip() for item_id in item_ids if item_id.strip()]
        changed = 0
        with Session(self.engine) as db:
            for item_id in normalized_ids:
                item = self._get_owned_item(db=db, session=session, item_id=item_id)
                item.deleted_at = self._now() if deleted else None
                item.updated_at = self._now()
                db.add(item)
                changed += 1
            db.commit()
        return {"ok": True, "changed_count": changed}

    def _normalize_item_payload(self, item_type: str, fields: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        """校验并规范化不同类型条目的字段。"""

        normalized_type = item_type.strip()
        if normalized_type not in VAULT_ITEM_TYPES:
            raise ValueError("unsupported vault item_type")
        normalized_fields = dict(fields or {})
        normalized_fields["name"] = str(normalized_fields.get("name") or normalized_fields.get("title") or "").strip()
        if normalized_type == "card":
            brand = str(normalized_fields.get("brand") or "").strip()
            if brand and brand not in VAULT_CARD_BRANDS:
                raise ValueError("unsupported card brand")
        if normalized_type == "identity":
            title = str(normalized_fields.get("title") or "").strip()
            if title and title not in VAULT_TITLES:
                raise ValueError("unsupported identity title")
        for field_name in REQUIRED_FIELDS[normalized_type]:
            if not str(normalized_fields.get(field_name) or "").strip():
                raise ValueError(f"{field_name} is required")
        custom_fields = normalized_fields.get("custom_fields")
        if custom_fields is not None and not isinstance(custom_fields, list):
            raise ValueError("custom_fields must be a list")
        normalized_fields["custom_fields"] = custom_fields or []
        normalized_fields["asset_ids"] = [str(item) for item in normalized_fields.get("asset_ids", []) if str(item).strip()]
        return normalized_type, normalized_fields

    def _coerce_import_item(self, raw: dict[str, Any]) -> tuple[str, dict[str, Any], list[str]]:
        """把导入记录转换为可创建条目。"""

        if not isinstance(raw, dict):
            raise ValueError("invalid import item")
        item_type = str(raw.get("item_type") or raw.get("type") or "").strip()
        fields = raw.get("fields") if isinstance(raw.get("fields"), dict) else dict(raw)
        tags = raw.get("tags") if isinstance(raw.get("tags"), list) else []
        if item_type in VAULT_ITEM_TYPES:
            try:
                normalized_type, normalized_fields = self._normalize_item_payload(item_type, fields)
                return normalized_type, normalized_fields, [str(tag) for tag in tags]
            except ValueError:
                pass
        note = json.dumps(raw, ensure_ascii=False, indent=2)
        name = str(raw.get("name") or raw.get("title") or raw.get("项目名称") or "导入条目").strip()
        if not name or note == "{}":
            raise ValueError("unrecognizable import item")
        return "secure_note", {"name": name, "note": note, "custom_fields": []}, [str(tag) for tag in tags]

    def _serialize_item(
        self,
        item: VaultItem,
        tags: list[str],
        session: VaultSession,
        *,
        reveal_sensitive: bool,
    ) -> dict[str, Any]:
        """解密并序列化条目。"""

        fields = self._decrypt(session, item.encrypted_payload)
        safe_fields = {key: value for key, value in fields.items() if key not in SENSITIVE_FIELDS}
        response_fields = fields if reveal_sensitive else safe_fields
        field_keys = [key for key, value in fields.items() if self._field_value_is_non_empty(value)]
        return {
            "item_id": item.item_id,
            "user_id": item.user_id,
            "item_type": item.item_type,
            "name": str(fields.get("name") or ""),
            "fields": response_fields,
            "safe_fields": safe_fields,
            "field_keys": field_keys,
            "tags": tags,
            "deleted_at": item.deleted_at.isoformat() if item.deleted_at else "",
            "created_at": item.created_at.isoformat(),
            "updated_at": item.updated_at.isoformat(),
        }

    @staticmethod
    def _field_value_is_non_empty(value: Any) -> bool:
        """Report field presence without exposing an encrypted field value."""

        if value is None:
            return False
        if isinstance(value, str):
            return bool(value.strip())
        if isinstance(value, (list, tuple, set, dict)):
            return bool(value)
        return True

    def _redact_item(self, item: dict[str, Any]) -> dict[str, Any]:
        """Return a list-safe item payload with sensitive fields removed."""

        safe_fields = dict(item.get("safe_fields", {}) or {})
        return {
            **item,
            "fields": safe_fields,
            "safe_fields": safe_fields,
        }

    def _search_blob(self, item: dict[str, Any]) -> str:
        """构造仅用于内存匹配的全字段搜索文本。"""

        return json.dumps({"fields": item.get("fields", {}), "tags": item.get("tags", [])}, ensure_ascii=False).lower()

    def _type_counts(self, items: list[dict[str, Any]]) -> dict[str, int]:
        """统计四类密码条目的数量。"""

        counts = {item_type: 0 for item_type in VAULT_ITEM_TYPES}
        for item in items:
            item_type = str(item.get("item_type") or "")
            if item_type in counts:
                counts[item_type] += 1
        return counts

    def _encrypt(self, session: VaultSession, payload: dict[str, Any]) -> str:
        """使用会话解密材料加密 JSON。"""

        return Fernet(session.fernet_key.encode("ascii")).encrypt(
            json.dumps(payload, ensure_ascii=False).encode("utf-8")
        ).decode("ascii")

    def _decrypt(self, session: VaultSession, encrypted_payload: str) -> dict[str, Any]:
        """解密 JSON 业务字段。"""

        try:
            raw = Fernet(session.fernet_key.encode("ascii")).decrypt(encrypted_payload.encode("ascii"))
            payload = json.loads(raw.decode("utf-8"))
        except (InvalidToken, json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ValueError("unable to decrypt vault item with current token") from exc
        return payload if isinstance(payload, dict) else {}

    def _replace_tags(self, *, db: Session, user_id: str, item_id: str, tag_names: list[str]) -> None:
        """替换条目标签关系。"""

        for link in list(db.exec(select(VaultItemTag).where(VaultItemTag.item_id == item_id)).all()):
            db.delete(link)
        normalized_names = []
        for name in tag_names:
            normalized = str(name).strip()
            if normalized and normalized not in normalized_names:
                normalized_names.append(normalized[:self.config.limits.vault_tag_name_max_chars])
        for name in normalized_names:
            tag = db.exec(select(VaultTag).where(VaultTag.user_id == user_id).where(VaultTag.name == name)).first()
            if tag is None:
                tag = VaultTag(tag_id=self._new_id("vtag"), user_id=user_id, name=name, created_at=self._now())
                db.add(tag)
                db.flush()
            db.add(VaultItemTag(item_id=item_id, tag_id=tag.tag_id))
        db.commit()

    def _tags_by_item(self, *, db: Session, item_ids: list[str]) -> dict[str, list[str]]:
        """批量读取条目的标签名。"""

        if not item_ids:
            return {}
        links = list(db.exec(select(VaultItemTag).where(col(VaultItemTag.item_id).in_(item_ids))).all())
        tag_ids = [link.tag_id for link in links]
        tags = {tag.tag_id: tag.name for tag in db.exec(select(VaultTag).where(col(VaultTag.tag_id).in_(tag_ids))).all()} if tag_ids else {}
        result: dict[str, list[str]] = {item_id: [] for item_id in item_ids}
        for link in links:
            name = tags.get(link.tag_id)
            if name:
                result.setdefault(link.item_id, []).append(name)
        return result

    def _attach_assets(self, *, db: Session, session: VaultSession, item_id: str, asset_ids: list[str]) -> None:
        """把上传图片绑定到条目。"""

        for asset_id in asset_ids:
            asset = db.get(VaultAsset, str(asset_id))
            if asset is not None and asset.user_id == session.user_id:
                asset.item_id = item_id
                db.add(asset)
        db.commit()

    def _serialize_asset(self, asset: VaultAsset) -> dict[str, Any]:
        """序列化图片资产元数据,不暴露真实磁盘路径。"""

        return {
            "asset_id": asset.asset_id,
            "item_id": asset.item_id,
            "mime_type": asset.mime_type,
            "file_name": asset.file_name,
            "size": asset.size,
            "created_at": asset.created_at.isoformat(),
        }

    def _get_owned_item(self, *, db: Session, session: VaultSession, item_id: str) -> VaultItem:
        """读取当前用户拥有的条目。"""

        item = db.get(VaultItem, item_id.strip())
        if item is None or item.user_id != session.user_id:
            raise ValueError("vault item not found")
        return item

    def _token_payload(self, *, user_id: str, master_password: str, salt: bytes) -> dict[str, Any]:
        """生成 30 分钟密码库 JWT。"""

        fernet_key = self._fernet_key(master_password, salt)
        expires_at = self._now() + timedelta(minutes=self.config.limits.vault_unlock_token_minutes)
        session_id = self._new_id("vsession")
        self._unlocked_keys[session_id] = (user_id, fernet_key, expires_at)
        token = jwt.encode(
            {
                "user_id": user_id,
                "scope": VAULT_SCOPE,
                "jti": session_id,
                "exp": expires_at,
            },
            self._jwt_secret(),
            algorithm="HS256",
        )
        return {"token": token, "scope": VAULT_SCOPE, "expires_at": expires_at.isoformat(), "user_id": user_id}

    def _purge_expired_sessions(self) -> None:
        """Drop expired in-memory vault decryption keys."""

        now = self._now()
        for session_id, (_, _, expires_at) in list(self._unlocked_keys.items()):
            if expires_at <= now:
                self._unlocked_keys.pop(session_id, None)

    def _jwt_secret(self) -> str:
        """返回 HS256 签名密钥。"""

        env_value = os.getenv("AGENT_VAULT_JWT_SECRET", "").strip()
        if env_value:
            return env_value
        material = f"{self.config.storage.project_root}|{self.config.storage.sqlite_path}|metaweave-vault"
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    def _password_hash(self, master_password: str, salt: bytes) -> str:
        """用 PBKDF2-HMAC-SHA256 保存主密码校验哈希。"""

        iterations = self.config.limits.vault_password_kdf_iterations
        digest = hashlib.pbkdf2_hmac("sha256", master_password.encode("utf-8"), salt, iterations)
        return f"pbkdf2_sha256${iterations}${base64.urlsafe_b64encode(digest).decode('ascii')}"

    def _fernet_key(self, master_password: str, salt: bytes) -> str:
        """从主密码派生 Fernet 数据加密密钥。"""

        digest = hashlib.pbkdf2_hmac(
            "sha256",
            master_password.encode("utf-8"),
            salt + b":fernet",
            self.config.limits.vault_encryption_kdf_iterations,
            dklen=self.config.limits.vault_encryption_key_bytes,
        )
        return base64.urlsafe_b64encode(digest).decode("ascii")

    @staticmethod
    def _normalize_user_id(user_id: str) -> str:
        """校验并规范化 user_id。"""

        normalized = user_id.strip()
        if not normalized:
            raise ValueError("user_id is required")
        return normalized

    @staticmethod
    def _now() -> datetime:
        """返回当前 UTC 时间。"""

        return datetime.now(timezone.utc)

    def _new_id(self, prefix: str) -> str:
        """生成业务主键。"""

        return f"{prefix}_{uuid4().hex[:self.config.limits.generated_long_id_suffix_chars]}"

    def _safe_filename(self, value: str) -> str:
        """清理文件名或目录名中的危险字符。"""

        cleaned = "".join("_" if char in '<>:"/\\|?*' or ord(char) < 32 else char for char in value.strip())
        return (cleaned.strip(" .") or "asset")[:self.config.limits.vault_asset_filename_max_chars]

    @staticmethod
    def _delete_asset_file(storage_path: str) -> None:
        """删除图片文件或目录,忽略已经不存在的路径。"""

        path = Path(storage_path)
        if path.is_file():
            path.unlink(missing_ok=True)
        elif path.is_dir():
            shutil.rmtree(path, ignore_errors=True)

    def _ensure_schema(self) -> None:
        """为旧数据库补齐密码库新增列。"""

        from sqlalchemy import inspect as sa_inspect
        try:
            inspector = sa_inspect(self.engine)
            columns = [column["name"] for column in inspector.get_columns("vault_assets")]
            with Session(self.engine) as db:
                if "item_id" not in columns:
                    db.execute(text("ALTER TABLE vault_assets ADD COLUMN item_id VARCHAR(64) NOT NULL DEFAULT ''"))
                db.commit()
            profile_columns = [column["name"] for column in inspector.get_columns("vault_profiles")]
            with Session(self.engine) as db:
                if "debug_master_password" not in profile_columns:
                    db.execute(text("ALTER TABLE vault_profiles ADD COLUMN debug_master_password VARCHAR(512) NOT NULL DEFAULT ''"))
                db.commit()
        except Exception:
            pass
