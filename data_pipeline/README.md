# Music Trends Galaxy Data Pipeline

This folder contains the stage-based ETL pipeline that prepares music data for the Music Trends Galaxy application.
It fetches and enriches metadata, builds embeddings and clusters, and produces artifacts consumed by the backend and frontend.

The pipeline is orchestrated with `run.py`, where each stage lives in `stages/<id>_<name>/main.py`.

## What this pipeline produces

- Processed datasets in the shared project `storage/` directory
- Cluster-ready and visualization-ready outputs for the map/galaxy UI
- Optional analytical artifacts for LLM-based cluster naming and descriptions

## Directory notes

- `stages/`: stage implementations grouped by numeric prefix
- `refs/`: reference images used by analysis/color-related tasks
- `config.yaml`: pipeline settings and stage configuration
- `requirements.txt` and `requirements-torch.txt`: Python dependencies

## Basic usage

Run commands from the `data_pipeline/` directory:

```bash
cd data_pipeline
python run.py list
```

Run one stage:

```bash
python run.py run 04
```

Run multiple stages by identifiers:

```bash
python run.py run 02 04 05
```

Run a numeric range:

```bash
python run.py run 02-05
```

Use optional arguments (if supported by selected stages), for example:

```bash
python run.py run 04 --limit 500
```

## Environment and dependencies

Install base dependencies:

```bash
pip install -r requirements.txt
```

For embedding and model-heavy workflows, also install:

```bash
pip install -r requirements-torch.txt
```

Some stages may download models on first run. Keep enough disk space for cached model files and generated artifacts.

## Storage and outputs

The pipeline uses the project-level `storage/` folder (`../storage` from this directory), which is shared with Docker services.
Large intermediate artifacts are expected during clustering and analysis stages.

To avoid committing generated binaries, keep artifact patterns in `.gitignore` up to date.

## Running with the full project

After generating data, you can run the application stack from the repository root:

```bash
docker compose up --build
```

Then open the frontend map/galaxy pages to validate the generated dataset.
