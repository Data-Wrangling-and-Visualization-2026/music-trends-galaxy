"""
Data pipeline context module.

Defines the DataPipelineContext class, which encapsulates stage-specific information,
configuration access, and utility methods for file path management in a data pipeline.
"""

from .config import Config
import re
from pathlib import Path
from typing import Any, Tuple

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
    '''
    Context that is given for running instance of the stage
    '''
    STORAGE_PATH: Path = 'storage'
    EXPORT_PATH: Path = 'export'

    stage_id: int
    stage_name: str

    root_dir: Path

    global_config: Config
    local_config: Config

    @property
    def folder_name(self) -> str: return f'{self.stage_id:02d}_{self.stage_name}'

    def __init__(self, root_dir: str, current_folder: str, config: Config):
        stage_id, stage_name = parse_folder_name(current_folder)
        self.stage_id = stage_id 
        self.stage_name = stage_name

        self.root_dir = Path(root_dir)
        
        self.global_config = config
        self.local_config = self.global_config.get(self.folder_name)

        self.EXPORT_PATH  = root_dir / config.get('export_folder')
        self.STORAGE_PATH = root_dir / config.get('storage_folder')

        # Ensure created
        self.EXPORT_PATH.mkdir(exist_ok=True)
        self.STORAGE_PATH.mkdir(exist_ok=True)

    def get(self, key: str) -> Any:
        '''
        Returns value from the config section related to the current stage
        '''
        return self.local_config.get(key)
    
    def get_export_dir(self) -> Path:
        '''
        Returns path of the folder where all ouput is located
        '''
        return self.EXPORT_PATH
    
    def get_storage_dir(self) -> Path:
        '''
        Returns path of the folder where all ouput is located
        '''
        return self.STORAGE_PATH
    
    def get_global(self, key: str) -> Any:
        '''
        Returns value from the global's config section
        '''
        return self.global_config.get(key)
    
    def get_file_path_from_stage(self, stage_id: int, filename: str) -> Path:
        path = self.STORAGE_PATH / f'{stage_id:02d}' 
        path.mkdir(exist_ok=True)

        return path / filename
    
    def get_file_path(self, filename: str) -> Path:
        return self.get_file_path_from_stage(self.stage_id, filename)