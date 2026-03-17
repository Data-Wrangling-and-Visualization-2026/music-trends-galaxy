#!/usr/bin/env python3
"""
Pipeline runner for stage-based data processing.

This script provides a command-line interface to discover, list, and execute data pipeline stages.
Stages are organized in subdirectories under 'stages/', each containing a 'main.py' file with a 'main' function.
The runner supports running individual stages, ranges of stages, listing stages, clearing storage, and copying input data.
"""

import os
import sys
import shutil
import importlib.util
import argparse
import re
from pathlib import Path
from pipeman import DataPipelineContext, Config
from typing import List
from types import ModuleType


# ----------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------
ROOT_DIR    = Path(__file__).resolve().parent  # data_pipeline/
STAGES_DIR  = ROOT_DIR / "stages"
# Project root storage (matches Docker ./storage mount for frontend)
STORAGE_DIR = (ROOT_DIR / ".." / "storage").resolve()
BACKUP_DIR  = (ROOT_DIR / ".." / "_backup_storage").resolve()
CONFIG_FILE = ROOT_DIR / "config.yaml"

# ----------------------------------------------------------------------
# Stage discovery and helpers
# ----------------------------------------------------------------------
def discover_stages() -> List[dict]:
    """
    Scan STAGES_DIR for subdirectories containing main.py.
    Return a list of dicts with keys:
        id: numeric prefix (two digits, as string)
        full_name: the complete folder name
        name_part: part after the first underscore (or full name if no underscore)
        path: Path object to the stage folder
    """
    stages = []
    if not STAGES_DIR.exists():
        return stages

    for item in sorted(STAGES_DIR.iterdir()):
        if not item.is_dir():
            continue
        main_py = item / "main.py"
        if not main_py.exists():
            continue

        # Extract numeric prefix and name part
        match = re.match(r"^(\d{2})_(.+)$", item.name)
        if match:
            stage_id = match.group(1)
            name_part = match.group(2)
        else:
            # If folder doesn't follow the pattern, treat the whole name as both id and name
            stage_id = item.name
            name_part = item.name

        stages.append({
            "id": stage_id,
            "full_name": item.name,
            "name_part": name_part,
            "path": item
        })
    return stages


def resolve_stage_identifiers(identifiers) -> List[Path]:
    """
    Given a list of strings that may be numeric ids, name parts, or full folder names,
    return a list of stage paths (Path objects) in the order given.
    Raises ValueError if any identifier cannot be resolved.
    """
    stages = discover_stages()
    if not stages:
        raise ValueError("No stages found in 'stages/' directory.")

    resolved = []
    for ident in identifiers:
        found = None
        for stage in stages:
            if ident == stage["id"] or ident == stage["name_part"] or ident == stage["full_name"]:
                found = stage["path"]
                break
        if found is None:
            raise ValueError(f"Stage identifier '{ident}' not found.")
        resolved.append(found)
    return resolved


def get_stage_description(stage_path) -> None | str:
    """
    Import main.py from stage_path, call desc(), and return its output.
    On any error, return None.
    """
    try:
        sys.path.insert(0, str(stage_path))
        module = load_module_from_path(stage_path / "main.py")
        if hasattr(module, "desc") and callable(module.desc):
            return module.desc()
        else:
            return None
    except Exception:
        return None
    finally:
        sys.path.pop(0)


def load_module_from_path(filepath) -> ModuleType:
    """
    Load a Python module from a file path.
    """
    module_name = filepath.stem
    spec = importlib.util.spec_from_file_location(module_name, filepath)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_stage(stage_path, context) -> None:
    """
    Import main.py from stage_path, call main(context).
    """
    sys.path.insert(0, str(stage_path))
    try:
        module = load_module_from_path(stage_path / "main.py")
        if not hasattr(module, "main") or not callable(module.main):
            raise AttributeError(f"Stage {stage_path.name} does not have a callable main() function.")
        module.main(context)
    finally:
        sys.path.pop(0)


def parse_range(range_str) -> List[str]:
    """
    Parse a string like "01-04" and return a list of numeric ids (strings) in that range inclusive.
    Raises ValueError if format is invalid.
    """
    match = re.match(r"^(\d{2})-(\d{2})$", range_str)
    if not match:
        raise ValueError(f"Invalid range format: {range_str}. Use two-digit numbers separated by a hyphen (e.g., 01-04).")
    start, end = match.groups()
    if start > end:
        raise ValueError(f"Start id ({start}) cannot be greater than end id ({end}).")
    # Generate list of two‑digit strings from start to end
    return [f"{i:02d}" for i in range(int(start), int(end) + 1)]


def clear_folder_contents(folder_path) -> None:
    """
    Remove all contents of a folder (files and subdirectories), but keep the folder itself.
    """
    if not folder_path.exists():
        return
    for item in folder_path.iterdir():
        if item.is_file() or item.is_symlink():
            item.unlink()
        elif item.is_dir():
            shutil.rmtree(item)


def move_contents(src, dst) -> None:
    """
    Move all contents of src folder into dst folder. dst is created if it doesn't exist.
    After moving, src will be empty (but the folder remains).
    """
    if not src.exists():
        return
    dst.mkdir(parents=True, exist_ok=True)
    for item in src.iterdir():
        shutil.move(str(item), str(dst / item.name))


# ----------------------------------------------------------------------
# Commands
# ----------------------------------------------------------------------
def cmd_list(args) -> None:
    """List all stages with their ids, names, and descriptions."""
    stages = discover_stages()
    if not stages:
        print("No stages found.")
        return

    print(f"{'ID':<4} {'Name':<20} Description")
    print("-" * 50)
    for stage in stages:
        desc = get_stage_description(stage["path"])
        if desc is None:
            desc = "Error in getting description"
        print(f"{stage['id']:<4} {stage['full_name']:<20} {desc}")


def cmd_run(args) -> None:
    """
    Execute one or more pipeline stages based on provided identifiers or a range.

    Supports running stages by ID, name, or full folder name, or a range like '01-04'.
    Resolves identifiers to stage paths, loads configuration, and runs each stage's 'main' function
    with a DataPipelineContext. Exits on errors during resolution or execution.

    Args:
        args: Namespace with 'identifiers' list (stage IDs/names or a single range string).
    """
    if len(args.identifiers) == 1 and "-" in args.identifiers[0]:
        # Range syntax
        try:
            ids = parse_range(args.identifiers[0])
        except ValueError as e:
            print(f"Error: {e}")
            sys.exit(1)
        # Resolve each id to a stage path
        try:
            stage_paths = resolve_stage_identifiers(ids)
        except ValueError as e:
            print(f"Error: {e}")
            sys.exit(1)
    else:
        # List of identifiers
        try:
            stage_paths = resolve_stage_identifiers(args.identifiers)
        except ValueError as e:
            print(f"Error: {e}")
            sys.exit(1)
    
    # Read config 
    config = Config(path=str(CONFIG_FILE.resolve()))

    # Run each stage in order
    for path in stage_paths:
        filename = path.name
        context = DataPipelineContext(ROOT_DIR, filename, config)
        print(f"Running stage: {path.name}")
        try:
            run_stage(path, context)
        except Exception as e:
            print(f"Error in stage {path.name}: {e}")
            sys.exit(1)
        print(f"Finished stage: {path.name}")


def cmd_help(args):
    """
    Display the help message with available commands and their usage.

    Prints a formatted help text explaining each command, including syntax for running stages,
    listing, clearing storage, and copying input data.
    """
    help_text = """
Pipeline runner commands:
  run [stage ids/names]       Run the specified stages.
  run first-second            Run all stages whose numeric ids fall in the range (inclusive).
  list                        List all stages with their ids, names, and descriptions.
  clear all                   Move all contents of storage/ to _backup_storage/ (clearing backup first).
  clear [stage ids/names]     Move contents of storage/<stage_folder>/ to _backup_storage/<stage_folder>/.
  copy input                  Copy input data specified in config.yaml to storage/input/.
  help                        Show this help message.
"""
    print(help_text)


def cmd_clear(args):
    """
    Clear storage directories by moving contents to backup locations.

    For 'all', moves all contents from STORAGE_DIR to BACKUP_DIR (clearing backup first).
    For a specific stage, accepts ONLY a two-digit numeric stage id (e.g. '01') and moves
    contents from the stage's storage subfolder to a corresponding backup subfolder.
    """
    if args.target == "all":
        # Clear entire storage
        if not STORAGE_DIR.exists():
            print("Storage folder does not exist. Nothing to clear.")
            return

        # Prepare backup folder
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        clear_folder_contents(BACKUP_DIR)

        # Move everything from storage to backup
        move_contents(STORAGE_DIR, BACKUP_DIR)
        print(f"Moved all contents from {STORAGE_DIR} to {BACKUP_DIR}.")
    else:
        # Only accept two-digit numeric ids (e.g., '01', '02')
        if not re.match(r"^\d{2}$", args.target):
            print("Error: 'clear' accepts only two-digit stage ids (e.g., 01).")
            sys.exit(1)

        # Resolve by numeric id using discover_stages()
        stages = discover_stages()
        matching = None
        for s in stages:
            if s["id"] == args.target:
                matching = s
                break

        if matching is None:
            print(f"Error: Stage id '{args.target}' not found.")
            sys.exit(1)

        stage_path = matching["path"]
        stage_name = stage_path.name

        # Prefer storage/<id> (e.g., storage/02); if that doesn't exist, fall back to storage/<full_stage_folder>
        candidate_by_id = STORAGE_DIR / args.target

        src = candidate_by_id
        dst = BACKUP_DIR / args.target

        if not src.exists():
            print(f"Storage subfolder {src} does not exist. Nothing to clear.")
            return

        # Prepare backup subfolder
        dst.mkdir(parents=True, exist_ok=True)
        clear_folder_contents(dst)

        # Move contents
        move_contents(src, dst)
        print(f"Moved contents from {src} to {dst}.")


def cmd_copy_input(args):
    """
    Copy input data files/directories from paths specified in config.yaml to storage/input/.

    Reads the 'input' key from CONFIG_FILE (expected as a list of paths). Copies each item
    to the input storage directory, preserving file/directory structure. Requires PyYAML.
    Warns on missing paths and exits on errors.
    """
    if not CONFIG_FILE.exists():
        print(f"Config file {CONFIG_FILE} not found.")
        sys.exit(1)

    try:
        import yaml
        with open(CONFIG_FILE, 'r') as f:
            config = yaml.safe_load(f)
    except ImportError:
        print("PyYAML is required for the 'copy input' command. Install with: pip install pyyaml")
        sys.exit(1)
    except Exception as e:
        print(f"Error reading config file: {e}")
        sys.exit(1)

    input_paths = config.get("input")
    if not input_paths:
        print("No 'input' key found in config or it is empty.")
        return

    dest_dir = STORAGE_DIR / "input"
    dest_dir.mkdir(parents=True, exist_ok=True)

    for src_path in input_paths:
        src = Path(src_path)
        if not src.exists():
            print(f"Warning: input path {src} does not exist, skipping.")
            continue

        dest = dest_dir / src.name
        try:
            if src.is_file():
                shutil.copy2(src, dest)
                print(f"Copied file {src} -> {dest}")
            elif src.is_dir():
                shutil.copytree(src, dest, dirs_exist_ok=True)
                print(f"Copied directory {src} -> {dest}")
        except Exception as e:
            print(f"Error copying {src}: {e}")
            sys.exit(1)


# ----------------------------------------------------------------------
# Main CLI
# ----------------------------------------------------------------------
def main():
    """
    Main entry point for the pipeline runner CLI.

    Parses command-line arguments to determine the command (e.g., 'run', 'list') and its arguments.
    Dispatches to the appropriate command function. Exits with usage message if no command is provided
    or if an unknown command is given.
    """

    parser = argparse.ArgumentParser(description="Pipeline runner", add_help=False)
    parser.add_argument("command", nargs="?", help="Command to execute")
    parser.add_argument("args", nargs=argparse.REMAINDER, help="Arguments for the command")

    # Parse only the first argument to get the command
    args = parser.parse_args()

    if not args.command:
        print("No command given. Use 'run.py help' for usage.")
        sys.exit(1)

    command = args.command
    rest = args.args

    if command == "list":
        cmd_list(None)
    elif command == "help":
        cmd_help(None)
    elif command == "run":
        if not rest:
            print("Error: 'run' requires stage identifiers or a range.")
            sys.exit(1)
        # Create a simple namespace for the run command
        run_args = argparse.Namespace(identifiers=rest)
        cmd_run(run_args)
    elif command == "clear":
        if not rest:
            print("Error: 'clear' requires 'all' or a stage identifier.")
            sys.exit(1)
        clear_target = rest[0]
        clear_args = argparse.Namespace(target=clear_target)
        cmd_clear(clear_args)
    elif command == "copy":
        if not rest or rest[0] != "input":
            print("Error: 'copy' requires 'input' subcommand.")
            sys.exit(1)
        cmd_copy_input(None)
    else:
        print(f"Unknown command: {command}")
        print("Use 'run.py help' for usage.")
        sys.exit(1)


if __name__ == "__main__":
    main()