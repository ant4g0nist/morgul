"""Tests for REPLLogger — per-iteration telemetry."""

from __future__ import annotations

import json

from morgul.core.agent.repl_logger import REPLLogger
from morgul.core.types.repl import REPLCodeBlock, REPLIteration


class TestREPLLogger:
    def test_iteration_tracking(self):
        logger = REPLLogger()
        logger.begin_iteration(1, "thinking...")
        logger.begin_code_block()
        logger.end_code_block(code="x = 1", stdout="", stderr="", succeeded=True)
        iteration = logger.end_iteration()

        assert iteration.step_number == 1
        assert iteration.llm_response == "thinking..."
        assert len(iteration.code_blocks) == 1
        assert iteration.code_blocks[0].code == "x = 1"
        assert iteration.duration > 0.0

    def test_multiple_code_blocks(self):
        logger = REPLLogger()
        logger.begin_iteration(1, "response")
        logger.begin_code_block()
        logger.end_code_block(code="x = 1", stdout="", stderr="", succeeded=True)
        logger.begin_code_block()
        logger.end_code_block(code="y = 2", stdout="", stderr="", succeeded=True)
        iteration = logger.end_iteration()

        assert len(iteration.code_blocks) == 2
        assert iteration.code_blocks[0].code == "x = 1"
        assert iteration.code_blocks[1].code == "y = 2"

    def test_iterations_property(self):
        logger = REPLLogger()
        logger.begin_iteration(1, "r1")
        logger.begin_code_block()
        logger.end_code_block(code="a", succeeded=True)
        logger.end_iteration()

        logger.begin_iteration(2, "r2")
        logger.begin_code_block()
        logger.end_code_block(code="b", succeeded=True)
        logger.end_iteration()

        assert len(logger.iterations) == 2
        assert logger.iterations[0].step_number == 1
        assert logger.iterations[1].step_number == 2

    def test_code_block_records_stderr(self):
        logger = REPLLogger()
        logger.begin_iteration(1, "resp")
        logger.begin_code_block()
        logger.end_code_block(
            code="1/0", stdout="", stderr="ZeroDivisionError", succeeded=False,
        )
        iteration = logger.end_iteration()

        block = iteration.code_blocks[0]
        assert not block.succeeded
        assert "ZeroDivisionError" in block.stderr

    def test_llm_sub_queries_field(self):
        logger = REPLLogger()
        logger.begin_iteration(1, "resp")
        logger.begin_code_block()
        logger.end_code_block(code="query()", succeeded=True, llm_sub_queries=3)
        iteration = logger.end_iteration()

        assert iteration.code_blocks[0].llm_sub_queries == 3

    def test_jsonl_output(self, tmp_path):
        log_file = tmp_path / "repl.jsonl"
        logger = REPLLogger(log_path=log_file)

        logger.begin_iteration(1, "resp")
        logger.begin_code_block()
        logger.end_code_block(code="x = 1", succeeded=True)
        logger.end_iteration()

        logger.begin_iteration(2, "resp2")
        logger.begin_code_block()
        logger.end_code_block(code="y = 2", succeeded=True)
        logger.end_iteration()

        lines = log_file.read_text().strip().split("\n")
        assert len(lines) == 2
        record = json.loads(lines[0])
        assert record["step_number"] == 1
        assert record["code_blocks"][0]["code"] == "x = 1"
