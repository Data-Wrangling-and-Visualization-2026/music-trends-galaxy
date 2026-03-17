# Data pipeline

Produces `embeded_data.csv` for the frontend galaxy visualization. Storage is at project root `storage/` (same path Docker mounts).

## Run pipeline for frontend data

From the **project root** (`music-trends-galaxy/`):

```bash
cd data_pipeline
python run.py run 03 04 --limit 1000
```

Or run stages separately:

```bash
cd data_pipeline
python run.py run 03                    # output.csv -> preproccessed.csv
python run.py run 04 --limit 500        # process 500 tracks (faster for testing)
python run.py run 04                    # interactive: prompts for max tracks, default 1000
python run.py run 04 --limit 0          # process all tracks (may take hours for 80k+)
```

## Requirements

1. **Stage 03** needs `storage/output.csv` (from earlier stages: lyric fetch, etc.).
2. **Stage 04** needs extra packages:
   ```bash
   pip install sentence-transformers hdbscan scikit-learn tqdm
   ```
   First run downloads the embedding model (~90MB); later runs reuse the cache.

## Data flow

| Stage | Input | Output |
|-------|-------|--------|
| 03    | `storage/output.csv` | `storage/preproccessed.csv` |
| 04    | `storage/preproccessed.csv` | `storage/embeded_data.csv` |

After running, start Docker and open the frontend:

```bash
docker compose up --build
# http://localhost:3000/map
```
