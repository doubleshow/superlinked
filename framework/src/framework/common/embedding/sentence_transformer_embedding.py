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

from pathlib import Path

import numpy as np
from beartype.typing import cast
from huggingface_hub.file_download import (  # type:ignore[import-untyped]
    repo_folder_name,
)
from sentence_transformers import SentenceTransformer
from torch import Tensor
from typing_extensions import override

from superlinked.framework.common.dag.context import ExecutionContext
from superlinked.framework.common.data_types import Vector
from superlinked.framework.common.embedding.embedding import Embedding
from superlinked.framework.common.interface.has_default_vector import HasDefaultVector
from superlinked.framework.common.interface.has_length import HasLength
from superlinked.framework.common.settings import Settings
from superlinked.framework.common.space.normalization import Normalization
from superlinked.framework.common.util.gpu_embedding_util import GpuEmbeddingUtil

SENTENCE_TRANSFORMERS_ORG_NAME = "sentence-transformers"
SENTENCE_TRANSFORMERS_MODEL_DIR: Path = (
    Path.home() / ".cache" / SENTENCE_TRANSFORMERS_ORG_NAME
)


class SentenceTransformerEmbedding(Embedding[str], HasLength, HasDefaultVector):
    def __init__(self, model_name: str, normalization: Normalization) -> None:
        local_files_only = self._model_is_downloaded(model_name)
        self._gpu_embedding_util = GpuEmbeddingUtil(Settings().GPU_EMBEDDING_THRESHOLD)
        self._embedding_model = SentenceTransformer(
            model_name,
            trust_remote_code=True,
            local_files_only=local_files_only,
            device="cpu",
            cache_folder=str(SENTENCE_TRANSFORMERS_MODEL_DIR),
        )
        self._bulk_embedding_model = None
        if self._gpu_embedding_util.is_gpu_embedding_enabled:
            self._bulk_embedding_model = SentenceTransformer(
                model_name,
                trust_remote_code=True,
                local_files_only=local_files_only,
                device=self._gpu_embedding_util.gpu_device_type,
                cache_folder=str(SENTENCE_TRANSFORMERS_MODEL_DIR),
            )

        self.__normalization = normalization
        self.__length = self._embedding_model.get_sentence_embedding_dimension() or 0

    def _model_is_downloaded(self, model_name: str) -> bool:
        return bool(model_name) and (
            (SENTENCE_TRANSFORMERS_MODEL_DIR / model_name).exists()
            or self._get_model_folder_path(model_name).exists()
        )

    def _get_model_folder_path(self, model_name: str) -> Path:
        repo_id = (
            SENTENCE_TRANSFORMERS_ORG_NAME + "/" + model_name
            if "/" not in model_name
            else model_name
        )
        return SENTENCE_TRANSFORMERS_MODEL_DIR / repo_folder_name(
            repo_id=repo_id, repo_type="model"
        )

    def embed_multiple(self, inputs: list[str]) -> list[Vector]:
        inputs_count = len(inputs)
        if not inputs_count:
            return []
        embedding_model = self._get_embedding_model(inputs_count)
        embeddings = embedding_model.encode(inputs)
        return [self.__to_vector(embedding) for embedding in embeddings]

    def _get_embedding_model(self, number_of_inputs: int) -> SentenceTransformer:
        return (
            self._bulk_embedding_model
            if self._bulk_embedding_model
            and self._gpu_embedding_util.is_above_gpu_embedding_threshold(
                number_of_inputs
            )
            else self._embedding_model
        )

    @override
    def embed(
        self,
        input_: str,
        context: ExecutionContext,  # pylint: disable=unused-argument
    ) -> Vector:
        return self.embed_multiple([input_])[0]

    @property
    def length(self) -> int:
        return self.__length

    @property
    @override
    def default_vector(self) -> Vector:
        return Vector([0.0] * self.length)

    def __to_vector(self, embedding: list[Tensor] | np.ndarray | Tensor) -> Vector:
        vector_input = cast(np.ndarray, embedding).astype(np.float64)
        vector = Vector(vector_input)
        return vector.normalize(self.__normalization.norm(vector_input))
