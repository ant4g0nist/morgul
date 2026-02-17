"""Tests for Breakpoint wrapper."""

from __future__ import annotations

from unittest.mock import MagicMock

from morgul.bridge.breakpoint import Breakpoint


class TestBreakpoint:
    def test_id(self, mock_sb_breakpoint):
        bp = Breakpoint(mock_sb_breakpoint)
        assert bp.id == 1

    def test_enabled(self, mock_sb_breakpoint):
        bp = Breakpoint(mock_sb_breakpoint)
        assert bp.enabled is True

    def test_hit_count(self, mock_sb_breakpoint):
        bp = Breakpoint(mock_sb_breakpoint)
        assert bp.hit_count == 0

    def test_num_locations(self, mock_sb_breakpoint):
        bp = Breakpoint(mock_sb_breakpoint)
        assert bp.num_locations == 1

    def test_condition_none(self, mock_sb_breakpoint):
        bp = Breakpoint(mock_sb_breakpoint)
        assert bp.condition is None

    def test_condition_set(self, mock_sb_breakpoint):
        mock_sb_breakpoint.GetCondition.return_value = "x > 5"
        bp = Breakpoint(mock_sb_breakpoint)
        assert bp.condition == "x > 5"

    def test_set_condition(self, mock_sb_breakpoint):
        bp = Breakpoint(mock_sb_breakpoint)
        bp.set_condition("argc == 2")
        mock_sb_breakpoint.SetCondition.assert_called_once_with("argc == 2")

    def test_enable(self, mock_sb_breakpoint):
        bp = Breakpoint(mock_sb_breakpoint)
        bp.enable()
        mock_sb_breakpoint.SetEnabled.assert_called_with(True)

    def test_disable(self, mock_sb_breakpoint):
        bp = Breakpoint(mock_sb_breakpoint)
        bp.disable()
        mock_sb_breakpoint.SetEnabled.assert_called_with(False)

    def test_delete(self, mock_sb_breakpoint):
        bp = Breakpoint(mock_sb_breakpoint)
        bp.delete()
        target = mock_sb_breakpoint.GetTarget()
        target.BreakpointDelete.assert_called_once_with(1)
