import json
import msgpack
import sqlite3
import random
from pathlib import Path
from PIL import Image, ImageDraw

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
CHUNKS_DIR = DATA_DIR / "chunks"
COVERS_DIR = DATA_DIR / "covers"
CHUNKS_DIR.mkdir(parents=True, exist_ok=True)
COVERS_DIR.mkdir(parents=True, exist_ok=True)

# 1. Create manifest.json
manifest = {
    "total_points": 500,
    "chunk_count": 2,
    "chunk_size": 250,
    "chunks": ["chunk_001.msgpack", "chunk_002.msgpack"],
    "cluster_data": {
        "deep": [
            {"id": "deep1", "name": "Rock", "channel_count": 120, "color": "#ff0000"},
            {"id": "deep2", "name": "Pop", "channel_count": 200, "color": "#00ff00"},
        ],
        "wide": [
            {"id": "wide1", "name": "90s", "channel_count": 80, "color": "#0000ff"},
        ]
    }
}
with open(DATA_DIR / "manifest.json", "w") as f:
    json.dump(manifest, f, indent=2)

# 2. Create dummy msgpack chunks
for i, chunk_name in enumerate(manifest["chunks"], 1):
    points = []
    for j in range(manifest["chunk_size"]):
        points.append({
            "id": (i-1)*manifest["chunk_size"] + j + 1,
            "x": random.uniform(-100, 100),
            "y": random.uniform(-100, 100),
            "z": random.uniform(-100, 100),
            "label": f"Point {j}",
            "cluster": random.choice(["deep1", "deep2", "wide1"]),
            "track_id": random.randint(1000, 9999)
        })
    with open(CHUNKS_DIR / chunk_name, "wb") as f:
        f.write(msgpack.packb(points, default=str))

# 3. Create dummy cover images (simple colored squares)
for cover_id in ["cover_001", "cover_002", "ab-12345"]:
    img = Image.new('RGB', (100, 100), color=random.choice(['red','green','blue','yellow']))
    img.save(COVERS_DIR / f"{cover_id}.jpeg", "JPEG")

# 4. Create SQLite database with songs
db_path = DATA_DIR / "database.sqlite"
conn = sqlite3.connect(str(db_path))
cursor = conn.cursor()
cursor.execute("""
    CREATE TABLE IF NOT EXISTS songs (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        artists TEXT NOT NULL,
        album TEXT NOT NULL,
        album_id TEXT NOT NULL,
        lyrics TEXT NOT NULL
    )
""")

songs = [
    (1, "Bohemian Rhapsody", json.dumps(["Queen"]), "A Night at the Opera", "album_123",
     "Is this the real life? Is this just fantasy?"),
    (2, "Imagine", json.dumps(["John Lennon"]), "Imagine", "album_456",
     "Imagine there's no heaven..."),
    (3, "Like a Rolling Stone", json.dumps(["Bob Dylan"]), "Highway 61 Revisited", "album_789",
     "Once upon a time you dressed so fine...")
]
cursor.executemany("INSERT INTO songs VALUES (?,?,?,?,?,?)", songs)
conn.commit()
conn.close()

print("Fake data generated successfully.")