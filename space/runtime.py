"""Primitives d'execution sans dependance UI pour la demo publique.

Ce module reste volontairement petit et testable avec la bibliotheque standard :
- cache LRU borne et protege par verrou ;
- reservation atomique des quotas avant tout calcul couteux ;
- classification prudente des erreurs exposees a l'utilisateur.
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from datetime import date
from threading import RLock
from typing import Generic, TypeVar
from uuid import uuid4


K = TypeVar("K")
V = TypeVar("V")


class BoundedLRUCache(Generic[K, V]):
    """Cache LRU en memoire, borne et sur pour plusieurs threads."""

    def __init__(self, max_size: int = 96):
        if max_size < 1:
            raise ValueError("max_size doit etre superieur a zero")
        self.max_size = max_size
        self._items: OrderedDict[K, V] = OrderedDict()
        self._lock = RLock()

    def get(self, key: K) -> V | None:
        with self._lock:
            value = self._items.get(key)
            if value is not None:
                self._items.move_to_end(key)
            return value

    def put(self, key: K, value: V) -> None:
        with self._lock:
            self._items[key] = value
            self._items.move_to_end(key)
            while len(self._items) > self.max_size:
                self._items.popitem(last=False)

    def __len__(self) -> int:
        with self._lock:
            return len(self._items)


class QuotaExceeded(RuntimeError):
    """Quota applicatif refuse avant le lancement du pipeline."""

    def __init__(self, scope: str):
        self.scope = scope
        super().__init__(f"quota {scope} atteint")


@dataclass(frozen=True)
class QuotaReservation:
    token: str
    day: str
    client_id: str


class QuotaGuard:
    """Compteurs journaliers avec reservations atomiques.

    Une reservation compte immediatement dans la capacite disponible. Elle est
    confirmee apres un calcul reussi, ou liberee si le fournisseur / serveur
    echoue. Cela empeche plusieurs requetes simultanees de depasser la limite.
    """

    def __init__(self, daily_limit: int, per_client_limit: int):
        if daily_limit < 1 or per_client_limit < 1:
            raise ValueError("les limites doivent etre superieures a zero")
        self.daily_limit = daily_limit
        self.per_client_limit = per_client_limit
        self._day = ""
        self._completed_total = 0
        self._completed_clients: dict[str, int] = {}
        self._reservations: dict[str, QuotaReservation] = {}
        self._lock = RLock()

    def _roll_day(self, today: str) -> None:
        if self._day != today:
            self._day = today
            self._completed_total = 0
            self._completed_clients = {}
            self._reservations = {}

    def reserve(self, client_id: str, today: str | None = None) -> QuotaReservation:
        today = today or date.today().isoformat()
        client_id = (client_id or "unknown")[:128]
        with self._lock:
            self._roll_day(today)
            reserved_total = len(self._reservations)
            reserved_for_client = sum(
                item.client_id == client_id for item in self._reservations.values()
            )
            if self._completed_total + reserved_total >= self.daily_limit:
                raise QuotaExceeded("global")
            if (
                self._completed_clients.get(client_id, 0) + reserved_for_client
                >= self.per_client_limit
            ):
                raise QuotaExceeded("client")
            reservation = QuotaReservation(uuid4().hex, today, client_id)
            self._reservations[reservation.token] = reservation
            return reservation

    def commit(self, reservation: QuotaReservation) -> bool:
        with self._lock:
            current = self._reservations.pop(reservation.token, None)
            if current is None or current.day != self._day:
                return False
            self._completed_total += 1
            self._completed_clients[current.client_id] = (
                self._completed_clients.get(current.client_id, 0) + 1
            )
            return True

    def release(self, reservation: QuotaReservation | None) -> bool:
        if reservation is None:
            return False
        with self._lock:
            return self._reservations.pop(reservation.token, None) is not None

    def snapshot(self) -> dict[str, object]:
        """Vue non sensible utile aux tests et a l'observabilite locale."""
        with self._lock:
            return {
                "day": self._day,
                "completed_total": self._completed_total,
                "reserved_total": len(self._reservations),
                "completed_clients": dict(self._completed_clients),
            }


def classify_exception(exc: BaseException) -> str:
    """Retourne ``provider`` ou ``internal`` sans exposer le detail public."""
    name = type(exc).__name__.lower()
    message = str(exc).lower()
    provider_names = (
        "apierror",
        "apitimeout",
        "ratelimit",
        "connectionerror",
        "connecttimeout",
        "readtimeout",
        "serviceunavailable",
    )
    provider_markers = (
        "gemini",
        "cerebras",
        "quota",
        "rate limit",
        "429",
        "503",
        "provider",
        "api down",
    )
    if any(marker in name for marker in provider_names):
        return "provider"
    if any(marker in message for marker in provider_markers):
        return "provider"
    return "internal"
