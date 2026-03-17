"""
Pipeline manager package.

Exposes key classes for configuration and context management in data pipelines.
"""

from .config import Config
from .context import DataPipelineContext, parse_folder_name