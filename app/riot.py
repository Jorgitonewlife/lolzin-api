"""Riot Games API client and match sync.

Pulls the most recent matches for the Riot ID configured in the environment and
stores them along with the items that were built, so champion and item
performance can be tracked over time.
"""

import os
import time
from datetime import datetime, timezone

import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Champion, Item, Match

ACCOUNT_URL = (
    "https://{region}.api.riotgames.com"
    "/riot/account/v1/accounts/by-riot-id/{game_name}/{tag_line}"
)
MATCH_IDS_URL = (
    "https://{region}.api.riotgames.com"
    "/lol/match/v5/matches/by-puuid/{puuid}/ids"
)
MATCH_URL = "https://{region}.api.riotgames.com/lol/match/v5/matches/{match_id}"

DDRAGON_VERSIONS_URL = "https://ddragon.leagueoflegends.com/api/versions.json"
DDRAGON_CHAMPIONS_URL = (
    "https://ddragon.leagueoflegends.com/cdn/{version}/data/en_US/champion.json"
)
DDRAGON_ITEMS_URL = (
    "https://ddragon.leagueoflegends.com/cdn/{version}/data/en_US/item.json"
)

DEFAULT_REGION = "americas"
ITEM_SLOTS = [f"item{i}" for i in range(7)]

_ddragon_cache: dict = {}


class RiotError(RuntimeError):
    """The Riot API could not be used."""


class RiotNotConfigured(RiotError):
    """Required Riot settings are missing from the environment."""


def riot_configured() -> bool:
    """Whether an API key and a usable Riot ID are present."""
    return bool(os.getenv("RIOT_API_KEY", "").strip()) and "#" in os.getenv(
        "RIOT_ID", ""
    )


def _api_key() -> str:
    key = os.getenv("RIOT_API_KEY", "").strip()
    if not key:
        raise RiotNotConfigured(
            "RIOT_API_KEY is not configured — add your Riot API key to enable the sync."
        )
    return key


def _riot_id() -> tuple[str, str]:
    riot_id = os.getenv("RIOT_ID", "").strip()
    if "#" not in riot_id:
        raise RiotNotConfigured(
            "RIOT_ID is not configured — set it to your Riot ID, e.g. GameName#BR1."
        )
    game_name, tag_line = riot_id.rsplit("#", 1)
    return game_name.strip(), tag_line.strip()


def _region() -> str:
    return os.getenv("RIOT_REGION", "").strip() or DEFAULT_REGION


def _get(
    url: str,
    *,
    params: dict | None = None,
    authenticated: bool = True,
    attempts: int = 4,
):
    """GET JSON, retrying briefly when Riot rate limits the request."""
    headers = {"X-Riot-Token": _api_key()} if authenticated else {}
    delay = 1.0

    for attempt in range(attempts):
        response = httpx.get(url, params=params, headers=headers, timeout=20.0)

        if response.status_code == 429 and attempt < attempts - 1:
            time.sleep(delay)
            delay *= 2
            continue
        if response.status_code in (401, 403):
            raise RiotError(
                "Riot rejected the API key. Development keys expire after 24 hours — "
                "regenerate it at developer.riotgames.com."
            )
        if response.status_code == 404:
            raise RiotError("Riot could not find that account or match.")
        if response.status_code >= 400:
            raise RiotError(f"Riot API returned an error ({response.status_code}).")

        return response.json()

    raise RiotError("Riot API rate limit reached — try again in a minute.")


def _ddragon() -> tuple[dict, dict]:
    """Champion and item metadata from Data Dragon, cached for the process."""
    if not _ddragon_cache:
        version = _get(DDRAGON_VERSIONS_URL, authenticated=False)[0]
        champions = _get(
            DDRAGON_CHAMPIONS_URL.format(version=version), authenticated=False
        )["data"]
        items = _get(DDRAGON_ITEMS_URL.format(version=version), authenticated=False)[
            "data"
        ]
        _ddragon_cache["champions"] = {entry["key"]: entry for entry in champions.values()}
        _ddragon_cache["items"] = items

    return _ddragon_cache["champions"], _ddragon_cache["items"]


def _champion_for(db: Session, participant: dict, champions: dict) -> Champion:
    """Find or create the champion a participant played."""
    meta = champions.get(str(participant.get("championId")))
    name = (meta or {}).get("name") or participant.get("championName") or "Unknown"

    champion = db.scalar(
        select(Champion).where(func.lower(Champion.name) == name.lower())
    )
    if champion is None:
        champion = Champion(name=name, title=(meta or {}).get("title", ""))
        db.add(champion)
        db.flush()
    return champion


def _item_for(db: Session, riot_item_id: int, items: dict) -> Item | None:
    """Find or create a purchasable item; None when Riot has no such item."""
    meta = items.get(str(riot_item_id))
    if meta is None:
        return None

    item = db.scalar(select(Item).where(Item.riot_item_id == riot_item_id))
    if item is None:
        name = meta["name"]
        # Adopt a curated item that already carries this name rather than duplicating it.
        item = db.scalar(select(Item).where(func.lower(Item.name) == name.lower()))
        if item is None:
            item = Item(name=name)
            db.add(item)
        item.riot_item_id = riot_item_id
        item.category = (meta.get("tags") or [None])[0]
        item.cost = (meta.get("gold") or {}).get("total")
        plaintext = meta.get("plaintext")
        item.description = plaintext[:240] if plaintext else None
        db.flush()

    return item


def sync_matches(db: Session, count: int = 20) -> dict:
    """Pull the most recent matches for the configured Riot ID and store them."""
    game_name, tag_line = _riot_id()
    region = _region()

    account = _get(
        ACCOUNT_URL.format(region=region, game_name=game_name, tag_line=tag_line)
    )
    puuid = account.get("puuid")
    if not puuid:
        raise RiotError("Riot did not return a PUUID for that Riot ID.")

    match_ids = _get(
        MATCH_IDS_URL.format(region=region, puuid=puuid),
        params={"start": 0, "count": count},
    )
    champions, items = _ddragon()

    synced, skipped = 0, 0
    stored_ids: list[str] = []

    for match_id in match_ids:
        exists = db.scalar(select(Match.id).where(Match.riot_match_id == match_id))
        if exists is not None:
            skipped += 1
            continue

        info = _get(MATCH_URL.format(region=region, match_id=match_id)).get("info", {})
        participant = next(
            (p for p in info.get("participants", []) if p.get("puuid") == puuid),
            None,
        )
        if participant is None:
            skipped += 1
            continue

        champion = _champion_for(db, participant, champions)
        duration = info.get("gameDuration") or 0

        match = Match(
            champion_id=champion.id,
            player=participant.get("riotIdGameName") or game_name,
            kills=participant.get("kills", 0),
            deaths=participant.get("deaths", 0),
            assists=participant.get("assists", 0),
            duration_minutes=round(duration / 60),
            victory=bool(participant.get("win")),
            played_at=datetime.fromtimestamp(
                (info.get("gameCreation") or 0) / 1000, tz=timezone.utc
            ),
            source="riot",
            riot_match_id=match_id,
        )

        seen: set[int] = set()
        for slot in ITEM_SLOTS:
            item_id = participant.get(slot) or 0
            if not item_id or item_id in seen:
                continue
            seen.add(item_id)
            item = _item_for(db, item_id, items)
            if item is not None:
                match.items.append(item)

        db.add(match)
        synced += 1
        stored_ids.append(match_id)

    db.commit()
    return {"synced": synced, "skipped": skipped, "match_ids": stored_ids}
