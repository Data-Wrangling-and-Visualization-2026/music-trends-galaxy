from typing import Any
import yaml

class Config:
    values: dict

    def __init__(self, path: str | None = None, kw_dict: dict | None = None):
        if path is not None:
            with open(path, 'r') as file:
                self.values = yaml.safe_load(file)
        elif kw_dict is not None:
            self.values = kw_dict
        else:
            raise ValueError("Invalid config source: no path or dictionary provided")
        
    def get(self, key: str) -> Any:
        return self.values[key]