from dataclasses import dataclass
from os import name
from typing import Dict, List, Optional, List, Any, TypeVar
from pydantic import BaseModel
from google.cloud import bigquery, bigquery_storage
from pathlib import Path


class FalGeneralException(Exception):
    pass


class DbtNodeDeps(BaseModel):
    nodes: List[str]


class DbtNodeConfig(BaseModel):
    materialized: Optional[str]


class Node(BaseModel):
    unique_id: str
    path: str
    resource_type: str
    description: str
    depends_on: Optional[DbtNodeDeps]
    config: DbtNodeConfig
    relation_name: Optional[str]


class DbtManifest(BaseModel):
    nodes: Dict[str, Node]
    sources: Dict[str, Node]
    metadata: Dict[str, Any]


class DbtModel(BaseModel):
    name: str
    meta: Any
    description: str
    columns: Any

    def model_key(self, project_name):
        return "model." + project_name + "." + self.name


class DbtProfileOutputDetail(BaseModel):
    type: str
    method: str
    ## pydantic is parsing default values as Lists
    ## for example; "dataset: [the name of your dbt dataset]""
    ## so they are Any types for now
    keyfile: Any
    project: Any
    dataset: Any


class DbtProfileOutput(BaseModel):
    dev: DbtProfileOutputDetail
    prod: DbtProfileOutputDetail


class DbtProfile(BaseModel):
    target: str
    outputs: DbtProfileOutput


class DbtProfileFile(BaseModel):
    __root__: Dict[str, DbtProfile]


T = TypeVar("T", bound="DbtProject")


@dataclass
class DbtProject:
    name: str
    model_config_paths: List[str]
    models: List[DbtModel]
    manifest: DbtManifest
    keyword: str
    profiles: Dict[str, DbtProfile]

    def state_has_changed(self, other: DbtManifest) -> bool:
        return self.manifest != other

    def find_model_location(self, model: DbtModel) -> List[str]:
        model_node = self.manifest.nodes[model.model_key(self.name)]
        return model_node.relation_name.replace("`", "")

    def get_materilization_type(self, model: DbtModel) -> str:
        model_node = self.manifest.nodes[model.model_key(self.name)]
        config = model_node["config"]["materialized"]
        return config

    def get_data_frame(self, table_id: str):
        db_type = self.manifest.metadata["adapter_type"]
        if db_type == "bigquery":
            rows = bigquery.Client().list_rows(
                bigquery.TableReference.from_string(table_id)
            )
            client = bigquery_storage.BigQueryReadClient()
            return rows.to_dataframe(bqstorage_client=client)
        else:
            raise FalGeneralException(db_type + "is not supported in Fal yet.")

    def get_data_frame_for_model(self, model: DbtModel):
        table_id = self.find_model_location(model)
        return self.get_data_frame(table_id)
