"""Create the schema and load demo data.

Run as a one-shot compose service before the API starts:
    python -m app.seed

Matches carry a `played_at` date and the items that were built, so the
performance views have something to show before any Riot sync happens.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.database import Base, SessionLocal, engine
from app.models import Champion, Item, Match

CHAMPIONS = [
    ("Aatrox", "the Darkin Blade", "Top", "Runeterra", 8, 2013),
    ("Ahri", "the Nine-Tailed Fox", "Mid", "Ionia", 5, 2011),
    ("Akali", "the Rogue Assassin", "Mid", "Ionia", 7, 2010),
    ("Ashe", "the Frost Archer", "Bot", "Freljord", 2, 2009),
    ("Darius", "the Hand of Noxus", "Top", "Noxus", 4, 2012),
    ("Ezreal", "the Prodigal Explorer", "Bot", "Piltover", 6, 2010),
    ("Garen", "the Might of Demacia", "Top", "Demacia", 2, 2009),
    ("Jinx", "the Loose Cannon", "Bot", "Zaun", 4, 2013),
    ("Lee Sin", "the Blind Monk", "Jungle", "Ionia", 9, 2011),
    ("Lux", "the Lady of Luminosity", "Mid", "Demacia", 3, 2010),
    ("Nautilus", "the Titan of the Depths", "Support", "Bilgewater", 5, 2012),
    ("Thresh", "the Chain Warden", "Support", "Shadow Isles", 7, 2013),
    ("Vi", "the Piltover Enforcer", "Jungle", "Piltover", 6, 2012),
    ("Yasuo", "the Unforgiven", "Mid", "Ionia", 10, 2013),
]

ITEMS = [
    ("Infinity Edge", "Crit", 3400, "Massive critical strike damage for marksmen."),
    ("Rabadon's Deathcap", "Ability Power", 3600, "Huge ability power multiplier for mages."),
    ("Trinity Force", "Bruiser", 3333, "Well-rounded stats for spellblade champions."),
    ("Zhonya's Hourglass", "Ability Power", 3000, "Stasis active that blocks all damage briefly."),
    ("Thornmail", "Tank", 2700, "Reflects incoming attack damage back at the attacker."),
    ("Bloodthirster", "Sustain", 3400, "Lifesteal and an overshield that scales with farm."),
    ("Guardian Angel", "Tank", 3200, "Revives the wearer after death with partial health."),
    ("Luden's Companion", "Ability Power", 2900, "Burst damage and mana sustain for poke mages."),
    ("Kraken Slayer", "Crit", 3100, "Deals true damage every third attack."),
    ("Redemption", "Support", 2300, "Area heal and shield for the whole team."),
]

# (champion, player, kills, deaths, assists, duration, victory, days_ago, [items built])
MATCHES = [
    ("Ahri", "ShadowFox", 12, 3, 9, 32, True, 3,
     ["Luden's Companion", "Rabadon's Deathcap", "Zhonya's Hourglass"]),
    ("Yasuo", "IronWolf", 7, 8, 4, 28, False, 5, ["Infinity Edge", "Kraken Slayer"]),
    ("Lee Sin", "RiverGhost", 4, 5, 18, 35, True, 6, ["Thornmail", "Guardian Angel"]),
    ("Jinx", "NeonCrow", 15, 6, 7, 41, True, 9,
     ["Infinity Edge", "Kraken Slayer", "Bloodthirster"]),
    ("Thresh", "Lumen", 1, 7, 24, 38, True, 11, ["Redemption", "Thornmail"]),
    ("Darius", "StoneOx", 9, 4, 5, 30, False, 14, ["Trinity Force", "Thornmail"]),
    ("Lux", "AuroraVeil", 11, 2, 12, 27, True, 16,
     ["Luden's Companion", "Rabadon's Deathcap"]),
    ("Ezreal", "QuietStorm", 6, 6, 3, 26, False, 19, ["Trinity Force", "Kraken Slayer"]),
    ("Vi", "Bramble", 5, 4, 16, 33, True, 21, ["Trinity Force", "Guardian Angel"]),
    ("Akali", "NightReed", 13, 5, 2, 29, True, 24,
     ["Rabadon's Deathcap", "Zhonya's Hourglass"]),
    ("Ashe", "FrostPetals", 8, 7, 11, 36, False, 28, ["Infinity Edge", "Bloodthirster"]),
    ("Garen", "CopperLion", 3, 6, 8, 31, False, 31,
     ["Trinity Force", "Thornmail", "Guardian Angel"]),
    ("Nautilus", "DeepAnchor", 2, 9, 21, 39, True, 35, ["Thornmail", "Redemption"]),
    ("Aatrox", "AshenKing", 10, 8, 6, 34, True, 40,
     ["Trinity Force", "Bloodthirster", "Guardian Angel"]),
]


def seed() -> None:
    """Create tables and populate them once, skipping if already seeded."""
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        if db.scalar(select(Champion.id).limit(1)) is not None:
            print("Database already seeded — nothing to do.")
            return

        db.add_all([
            Champion(
                name=name,
                title=title,
                role=role,
                region=region,
                difficulty=difficulty,
                release_year=release_year,
            )
            for name, title, role, region, difficulty, release_year in CHAMPIONS
        ])
        db.add_all([
            Item(name=name, category=category, cost=cost, description=description)
            for name, category, cost, description in ITEMS
        ])
        db.flush()

        champions = {c.name: c for c in db.scalars(select(Champion)).all()}
        items = {i.name: i for i in db.scalars(select(Item)).all()}
        now = datetime.now(timezone.utc)

        for (
            champion_name,
            player,
            kills,
            deaths,
            assists,
            duration,
            victory,
            days_ago,
            item_names,
        ) in MATCHES:
            match = Match(
                champion_id=champions[champion_name].id,
                player=player,
                kills=kills,
                deaths=deaths,
                assists=assists,
                duration_minutes=duration,
                victory=victory,
                played_at=now - timedelta(days=days_ago),
                source="demo",
            )
            match.items.extend(items[name] for name in item_names)
            db.add(match)

        db.commit()

    print(
        f"Seeded {len(CHAMPIONS)} champions, {len(ITEMS)} items, "
        f"{len(MATCHES)} matches."
    )


if __name__ == "__main__":
    seed()
