"""Schémas Pydantic (validation stricte des entrées)."""
from __future__ import annotations

import time
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

MAX_BODY = 100_000
MAX_BATCH = 500
_MAX_DATE_MS = 4_102_444_800_000  # 01/01/2100


def _clean(value: str) -> str:
    return value.replace("\x00", "")


class SmsIn(BaseModel):
    model_config = ConfigDict(extra="ignore")

    sms_id: int | None = Field(None, ge=0, description="Identifiant dans le fournisseur SMS Android")
    address: str = Field(..., min_length=1, max_length=64, description="Numéro ou expéditeur")
    body: str = Field("", max_length=MAX_BODY)
    date_ms: int = Field(..., gt=0, lt=_MAX_DATE_MS, description="Date en millisecondes UNIX")
    type: int = Field(..., ge=1, le=6, description="1 = reçu, 2 = envoyé, 4/5/6 = autres états d'envoi")
    read: bool = True
    contact_name: str | None = Field(None, max_length=128)

    @field_validator("address", "body", "contact_name")
    @classmethod
    def strip_nul(cls, v: str | None) -> str | None:
        return _clean(v) if isinstance(v, str) else v

    @field_validator("address")
    @classmethod
    def address_not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("adresse vide")
        return v


class SmsBatch(BaseModel):
    messages: list[SmsIn] = Field(..., min_length=1, max_length=MAX_BATCH)
    sync_total: int | None = Field(None, ge=0, description="Total estimé à synchroniser (progression)")
    sync_remaining: int | None = Field(None, ge=0, description="Messages restant en file d'attente")


class BatchResult(BaseModel):
    received: int
    inserted: int
    duplicates: int


class PairRequest(BaseModel):
    code: str = Field(..., min_length=6, max_length=16)
    device_id: str = Field(..., min_length=8, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    device_name: str = Field(..., min_length=1, max_length=64)
    transport: Literal["wifi", "usb"] | None = None


class PairResponse(BaseModel):
    device_id: str
    device_token: str
    server_version: str


class Heartbeat(BaseModel):
    battery: int | None = Field(None, ge=0, le=100)
    charging: bool | None = None
    app_version: str | None = Field(None, max_length=32)
    pending: int | None = Field(None, ge=0)
    transport: Literal["wifi", "usb"] | None = None


class SettingsIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lan_mode: bool | None = None
    lan_admin: bool | None = None
    adb_path: str | None = Field(None, max_length=512)
    adb_auto_reverse: bool | None = None


class PurgeRequest(BaseModel):
    confirm: Literal["SUPPRIMER"]


class AdbReverseRequest(BaseModel):
    serial: str | None = Field(None, pattern=r"^[A-Za-z0-9._:\-]{1,64}$")


def utc_ms() -> int:
    return int(time.time() * 1000)
