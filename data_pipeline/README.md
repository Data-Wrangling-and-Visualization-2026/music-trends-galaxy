# Data pipeline

Produces `embeded_data.csv` for the frontend galaxy visualization. Storage is at project root `storage/` (same path Docker mounts).

## Run pipeline for frontend data

From the **project root** (`music-trends-galaxy/`):

```bash
cd data_pipeline
python run.py run 03 04
```

Or run stages separately:

```bash
cd data_pipeline
python run.py run 03   # output.csv -> preproccessed.csv
python run.py run 04   # preproccessed.csv -> embeded_data.csv
```

## Requirements

1. **Stage 03** needs `storage/output.csv` (from earlier stages: lyric fetch, etc.).
2. **Stage 04** needs `sentence-transformers`, `hdbscan`, `scikit-learn`:
   ```bash
   pip install sentence-transformers hdbscan scikit-learn
   ```

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
