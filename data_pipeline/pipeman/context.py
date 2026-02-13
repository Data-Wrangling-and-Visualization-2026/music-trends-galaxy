from .config import Config
import re
from pathlib import Path
from typing import Any, Tuple

STORAGE_PATH = 'storage'

def parse_folder_name(name: str) -> Tuple[int, str]:
    """
    Parse a line in the format 'id_name' and return a tuple (id, name).
    
    Args:
        line (str): String in the format 'id_name' (e.g., '123_john' or '45_alice')
        
    Returns:
        tuple: (id: int, name: str)
        
    Raises:
        ValueError: If the line format is invalid or id cannot be converted to int
    """
    # Split the line at the first underscore
    parts = name.split('_', 1)
    
    # Check if we have exactly two parts
    if len(parts) != 2:
        raise ValueError(f"Invalid format. Expected 'id_name', got: {name}")
    
    id_str, name = parts
    
    # Convert id to integer
    try:
        id_int = int(id_str)
    except ValueError:
        raise ValueError(f"Invalid id format. Expected integer, got: {id_str}")
    
    return (id_int, name)
    

class DataPipelineContext:
    stage_id: int
    stage_name: str

    root_dir: str

    global_config: Config
    local_config: Config

    @property
    def folder_name(self) -> str: return f'{self.stage_id}_{self.stage_name}'

    def __init__(self, root_dir: str, current_folder: str, config: Config):
        stage_id, stage_name = parse_folder_name(current_folder)
        self.stage_id = stage_id 
        self.stage_name = stage_name

        self.root_dir = root_dir
        
        self.global_config = config
        self.local_config = self.global_config[self.folder_name]

    def get(self, key: str) -> Any:
        return self.local_config.get(key)
    
    def get_global(self, key: str) -> Any:
        return self.global_config.get(key)
    
    def get_data_prefix(self) -> str:
        return f'{self.stage_id}_'