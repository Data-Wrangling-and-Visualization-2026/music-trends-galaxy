import json
import msgpack
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Song
from PIL import Image, ImageDraw

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
CHUNKS_DIR = DATA_DIR / "chunks"
COVERS_DIR = DATA_DIR / "covers"
CHUNKS_DIR.mkdir(parents=True, exist_ok=True)
COVERS_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

manifest = {
    "total_points": 500,
    "chunk_count": 2,
    "chunk_size": 250,
    "chunks": ["chunk_001.msgpack", "chunk_002.msgpack"],
    "cluster_data": [
        {"id": "c1", "name": "Rock", "channel_count": 120, "color": "#ff0000"},
        {"id": "c2", "name": "Pop", "channel_count": 200, "color": "#00ff00"},
        {"id": "c3", "name": "90s", "channel_count": 80, "color": "#0000ff"},
    ],
}
with open(DATA_DIR / "manifest.json", "w") as f:
    json.dump(manifest, f, indent=2)

for i, chunk_name in enumerate(manifest["chunks"], 1):
    points = []
    for j in range(manifest["chunk_size"]):
        points.append({
            "id": (i - 1) * manifest["chunk_size"] + j + 1,
            "x": random.uniform(-100, 100),
            "y": random.uniform(-100, 100),
            "z": random.uniform(-100, 100),
            "label": f"Point {j}",
            "cluster": random.choice(["c1", "c2", "c3"]),
            "track_id": random.randint(1000, 9999),
        })
    with open(CHUNKS_DIR / chunk_name, "wb") as f:
        f.write(msgpack.packb(points, default=str))

for cover_id in ["cover_001", "cover_002", "ab-12345"]:
    img = Image.new("RGB", (100, 100), color=random.choice(["red", "green", "blue", "yellow"]))
    img.save(COVERS_DIR / f"{cover_id}.jpeg", "JPEG")

songs = [
    (1, "Bohemian Rhapsody", json.dumps(["Queen"]), "A Night at the Opera", "album_queen_opera",
     "Is this the real life? Is this just fantasy?"),
    (2, "Imagine", json.dumps(["John Lennon"]), "Imagine", "album_lennon_imagine",
     "Imagine there's no heaven..."),
    (3, "Like a Rolling Stone", json.dumps(["Bob Dylan"]), "Highway 61 Revisited", "album_dylan_61",
     "Once upon a time you dressed so fine..."),
    (4, "Кино", json.dumps(["Виктор Цой", "Кино"]), "Группа крови", "album_kino_gruppa",
     "Группа крови, руку пожать..."),
    (5, "Smells Like Teen Spirit", json.dumps(["Nirvana"]), "Nevermind", "album_nirvana_nevermind",
     "With the lights out, it's less dangerous..."),
    (6, "Billie Jean", json.dumps(["Michael Jackson"]), "Thriller", "album_mj_thriller",
     "She was more like a beauty queen..."),
    (7, "Blinding Lights", json.dumps(["The Weeknd"]), "After Hours", "album_weeknd_after",
     "I've been tryna call..."),
    (8, "Levitating", json.dumps(["Dua Lipa", "DaBaby"]), "Future Nostalgia", "album_dua_future",
     "If you wanna run away with me, I know a galaxy..."),
]

session: Session = SessionLocal()
try:
    for sid, name, artists, album, album_id, lyrics in songs:
        ins = insert(Song).values(
            id=sid,
            name=name,
            artists=artists,
            album=album,
            album_id=album_id,
            lyrics=lyrics,
        )
        stmt = ins.on_conflict_do_update(
            index_elements=[Song.id],
            set_={
                "name": ins.excluded.name,
                "artists": ins.excluded.artists,
                "album": ins.excluded.album,
                "album_id": ins.excluded.album_id,
                "lyrics": ins.excluded.lyrics,
            },
        )
        session.execute(stmt)
    session.commit()
finally:
    session.close()

print("Fake data generated successfully.")