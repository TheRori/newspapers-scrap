import yaml
import re
from typing import Dict, Any, Union
from pathlib import Path
from pydantic import BaseModel, Field, create_model


# Define the base models for structured access
class URLs(BaseModel):
    base_newspaper_archives: str


class SearchParams(BaseModel):
    a: str
    hs: str
    r: str
    results: str


class SearchConfig(BaseModel):
    params: SearchParams


class SearchSelectors(BaseModel):
    result_item: str
    result_title: str
    result_link: str
    result_newspaper: str
    result_snippet: str


class Newspaper(BaseModel):
    base_url: str
    search_url: str


class NewspaperDict(BaseModel):
    e_newspaper_archives: Newspaper
    # Add other newspapers as needed


class ArticleSelectors(BaseModel):
    title: str
    article_text: str
    permalink: str
    article_container: str


class Selectors(BaseModel):
    search_selectors: SearchSelectors = Field(alias="SEARCH_SELECTORS")
    article_selectors: ArticleSelectors = Field(alias="ARTICLE_SELECTORS")
    newspapers: NewspaperDict = Field(alias="NEWSPAPERS")


class Headers(BaseModel):
    user_agent: str


class RequestLimits(BaseModel):
    request_delay_min: float
    request_delay_max: float
    max_search_pages: int
    max_results_per_search: int


class RequestConfig(BaseModel):
    headers: Headers


class Limits(BaseModel):
    request_delay_min: float
    request_delay_max: float
    max_search_pages: int
    max_results_per_search: int


class Scraping(BaseModel):
    request: RequestConfig = Field(alias="REQUEST")
    limits: Limits = Field(alias="LIMITS")


class StorageConfig(BaseModel):
    raw_data_dir: str
    processed_data_dir: str
    topics_data_dir: str
    logs_dir: str


class Storage(BaseModel):
    paths: StorageConfig = Field(alias="PATHS")


class UrlsConfig(BaseModel):
    urls: URLs = Field(alias="URLS")
    search: SearchConfig = Field(alias="SEARCH")


class BrightDataConfig(BaseModel):
    username: str
    password: str
    zone: str


class Config(BaseModel):
    urls: UrlsConfig
    selectors: Selectors
    scraping: Scraping
    storage: Storage


def load_yaml(file_path: Path) -> dict:
    """Loads a YAML file and returns its content as a dictionary."""
    with open(file_path, "r", encoding="utf-8") as file:
        return yaml.safe_load(file)


def resolve_placeholders(config_dict: Dict[str, Any], all_configs: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """
    Recursively resolves placeholders in config_dict using values from all_configs.
    Placeholders are in the format ${file.path.to.value}
    """
    if isinstance(config_dict, dict):
        return {k: resolve_placeholders(v, all_configs) for k, v in config_dict.items()}
    elif isinstance(config_dict, list):
        return [resolve_placeholders(v, all_configs) for v in config_dict]
    elif isinstance(config_dict, str) and "${" in config_dict:
        # Process string with placeholder
        result = config_dict
        pattern = re.compile(r"\${([\w.]+)}")
        for match in pattern.finditer(config_dict):
            path = match.group(1).split(".")
            file_name, *key_path = path

            if file_name in all_configs:
                # Navigate through the nested dictionary
                value = all_configs[file_name]
                for key in key_path:
                    if key in value:
                        value = value[key]
                    else:
                        break

                if isinstance(value, str):
                    result = result.replace(f"${{{match.group(1)}}}", value)

        return result
    else:
        return config_dict


def load_config() -> Config:
    """Loads and merges all config files into a structured model."""
    base_path = Path(__file__).parent

    # Load raw configs
    raw_configs = {
        "urls": load_yaml(base_path / "urls.yaml"),
        "selectors": load_yaml(base_path / "selectors.yaml"),
        "scraping": load_yaml(base_path / "scraping.yaml"),
        "storage": load_yaml(base_path / "storage.yaml"),
    }

    # Resolve placeholders
    resolved_configs = resolve_placeholders(raw_configs, raw_configs)

    # Create the final config
    return Config(
        urls=resolved_configs["urls"],
        selectors=resolved_configs["selectors"],
        scraping=resolved_configs["scraping"],
        storage=resolved_configs["storage"],
    )


# Load the configuration once and expose it globally
env = load_config()


# Example of how to access values
def example_usage():
    # Access using dot notation
    base_url = env.urls.urls.base_newspaper_archives
    selector = env.selectors.search_selectors.result_item
    newspaper_url = env.selectors.newspapers.e_newspaper_archives.base_url
    storage_dir = env.storage.storage.raw_data_dir

    return {
        "base_url": base_url,
        "selector": selector,
        "newspaper_url": newspaper_url,
        "storage_dir": storage_dir
    }
