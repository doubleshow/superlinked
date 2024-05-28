# Copyright 2024 Superlinked, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from dataclasses import dataclass
from enum import Enum, auto
from typing import Any, Generic

from superlinked.framework.common.parser.data_parser import DataParser
from superlinked.framework.common.parser.dataframe_parser import DataFrameParser
from superlinked.framework.common.schema.schema_object import SchemaObjectT
from superlinked.framework.common.source.types import SourceTypeT
from superlinked.framework.dsl.source.in_memory_source import InMemorySource
from superlinked.framework.dsl.source.source import Source
from superlinked.framework.online.source.in_memory_source import (
    InMemorySource as CommonInMemorySource,
)


class DataFormat(Enum):
    CSV = auto()
    FWF = auto()
    XML = auto()
    JSON = auto()
    PARQUET = auto()
    ORC = auto()


@dataclass
class DataLoaderConfig:
    path: str
    format: DataFormat
    pandas_read_kwargs: dict[str, Any]


class DataLoaderSource(Source, Generic[SchemaObjectT, SourceTypeT]):
    def __init__(
        self,
        schema: SchemaObjectT,
        data_loader_config: DataLoaderConfig,
        parser: DataParser | None = None,
    ):
        self._online_source: InMemorySource = InMemorySource(
            schema, parser if parser is not None else DataFrameParser(schema)
        )
        self.__data_loader_config = data_loader_config

    @property
    def _source(self) -> CommonInMemorySource:
        return self._online_source._source

    @property
    def config(self) -> DataLoaderConfig:
        return self.__data_loader_config
