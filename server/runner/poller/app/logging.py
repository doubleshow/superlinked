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

import logging
import os
from typing import cast

import structlog
from structlog.contextvars import merge_contextvars
from structlog.typing import Processor

from poller.app.custom_structlog_processor import CustomStructlogProcessor


# TODO: Copied from Superlinked logging.py, FAI-2280 to remove it
class LoggerConfigurator:

    @staticmethod
    def configure_default_logger(
        processors: list[Processor] | None = None,
    ) -> None:
        if structlog.is_configured():
            return
        processors = processors or []
        processors.append(structlog.stdlib.render_to_log_kwargs)
        structlog.configure(
            processors=processors,
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )

    @staticmethod
    def configure_structlog_logger(
        json_log_file_path: str | None = None,
        processors: list[Processor] | None = None,
        expose_pii: bool = False,
        log_as_json: bool = False,
    ) -> None:
        if not processors:
            processors = LoggerConfigurator._get_structlog_processors(
                json_log_file_path, expose_pii, log_as_json
            )
        structlog.configure(
            processors=processors
            + [
                # Prepare event dict for `ProcessorFormatter`.
                structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
            ],
            logger_factory=structlog.stdlib.LoggerFactory(),
            cache_logger_on_first_use=True,
        )

        log_renderer = cast(
            Processor,
            (
                structlog.processors.JSONRenderer()
                if log_as_json
                else structlog.dev.ConsoleRenderer()
            ),
        )

        LoggerConfigurator._format_standard_logs_with_structlog(
            log_renderer, processors
        )

    @staticmethod
    def _format_standard_logs_with_structlog(
        log_renderer: Processor, shared_processors: list[Processor]
    ) -> None:
        stdlib_processors: list[Processor] = [
            # Remove _record & _from_structlog.
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            log_renderer,
        ]
        formatter = structlog.stdlib.ProcessorFormatter(
            # These run ONLY on `logging` entries that do NOT originate within structlog.
            foreign_pre_chain=shared_processors,
            # These run on ALL entries after the pre_chain is done.
            processors=stdlib_processors,
        )
        # Use OUR `ProcessorFormatter` to format all `logging` entries.
        handler = logging.StreamHandler()
        handler.setFormatter(formatter)
        logging.getLogger().addHandler(handler)

    @staticmethod
    def _get_structlog_processors(
        json_log_file_path: str | None, expose_pii: bool, log_as_json: bool
    ) -> list[Processor]:
        json_file_processors: list[Processor] = (
            [CustomStructlogProcessor._get_json_file_renderer(json_log_file_path)]
            if json_log_file_path is not None
            else []
        )
        json_console_processors: list[Processor] = (
            [
                structlog.processors.EventRenamer("message"),
                structlog.processors.format_exc_info,
            ]
            if log_as_json
            else []
        )
        return (
            LoggerConfigurator._get_common_processors(expose_pii)
            + json_file_processors
            + json_console_processors
        )

    @staticmethod
    def _get_common_processors(expose_pii: bool = False) -> list[Processor]:
        shared_processors: list[Processor] = [
            merge_contextvars,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.stdlib.ExtraAdder(),
            structlog.processors.TimeStamper(fmt="iso"),
            CustomStructlogProcessor._set_log_var("process_id", os.getpid()),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.UnicodeDecoder(),
        ]
        if not expose_pii:
            shared_processors.append(CustomStructlogProcessor.filter_pii)
        return shared_processors
