"""Tests for Thread wrapper."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from morgul.bridge.thread import Thread
from morgul.bridge.types import StopReason


class TestThread:
    def test_id(self, mock_sb_thread):
        thread = Thread(mock_sb_thread)
        assert thread.id == 1

    def test_name(self, mock_sb_thread):
        thread = Thread(mock_sb_thread)
        assert thread.name == "main"

    def test_name_none(self, mock_sb_thread):
        mock_sb_thread.GetName.return_value = None
        thread = Thread(mock_sb_thread)
        assert thread.name is None

    def test_num_frames(self, mock_sb_thread):
        thread = Thread(mock_sb_thread)
        assert thread.num_frames == 2

    def test_step_over(self, mock_sb_thread):
        thread = Thread(mock_sb_thread)
        thread.step_over()
        mock_sb_thread.StepOver.assert_called_once()

    def test_step_into(self, mock_sb_thread):
        thread = Thread(mock_sb_thread)
        thread.step_into()
        mock_sb_thread.StepInto.assert_called_once()

    def test_step_out(self, mock_sb_thread):
        thread = Thread(mock_sb_thread)
        thread.step_out()
        mock_sb_thread.StepOut.assert_called_once()

    def test_step_instruction(self, mock_sb_thread):
        thread = Thread(mock_sb_thread)
        thread.step_instruction(over=False)
        mock_sb_thread.StepInstruction.assert_called_once_with(False)

    def test_step_instruction_over(self, mock_sb_thread):
        thread = Thread(mock_sb_thread)
        thread.step_instruction(over=True)
        mock_sb_thread.StepInstruction.assert_called_once_with(True)

    def test_get_frames(self, mock_sb_thread):
        mock_frame = MagicMock()
        mock_sb_thread.GetFrameAtIndex.return_value = mock_frame
        thread = Thread(mock_sb_thread)
        frames = thread.get_frames()
        assert len(frames) == 2

    def test_get_frames_with_count(self, mock_sb_thread):
        mock_frame = MagicMock()
        mock_sb_thread.GetFrameAtIndex.return_value = mock_frame
        thread = Thread(mock_sb_thread)
        frames = thread.get_frames(count=1)
        assert len(frames) == 1

    def test_selected_frame(self, mock_sb_thread):
        mock_frame = MagicMock()
        mock_sb_thread.GetSelectedFrame.return_value = mock_frame
        thread = Thread(mock_sb_thread)
        frame = thread.selected_frame
        assert frame is not None
