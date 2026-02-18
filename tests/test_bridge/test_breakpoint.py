"""Tests for Breakpoint wrapper."""

from __future__ import annotations

from unittest.mock import MagicMock

from morgul.bridge.breakpoint import Breakpoint, _BP_CALLBACKS, _invoke_bp_callback


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

    def test_set_callback_registers_in_module(self, mock_sb_breakpoint):
        bp = Breakpoint(mock_sb_breakpoint)
        called_with = {}

        def my_cb(frame, bp_loc, extra):
            called_with["frame"] = frame
            return True

        bp.set_callback(my_cb)

        # Callback should be in the module-level registry
        assert id(bp) in _BP_CALLBACKS
        assert _BP_CALLBACKS[id(bp)] is my_cb

        # SetScriptCallbackBody should have been called with dispatch code
        body_call = mock_sb_breakpoint.SetScriptCallbackBody.call_args[0][0]
        assert "_invoke_bp_callback" in body_call
        assert str(id(bp)) in body_call

    def test_set_callback_dispatch(self, mock_sb_breakpoint):
        bp = Breakpoint(mock_sb_breakpoint)
        results = []

        def my_cb(frame, bp_loc, extra):
            results.append((frame, bp_loc))
            return False

        bp.set_callback(my_cb)

        # Simulate LLDB calling the dispatch function
        stop = _invoke_bp_callback(id(bp), "fake_frame", "fake_loc", None, {})
        assert stop is False
        assert results == [("fake_frame", "fake_loc")]

    def test_set_callback_missing_returns_true(self):
        """Dispatch with unknown id should return True (stop by default)."""
        stop = _invoke_bp_callback(99999, None, None, None, {})
        assert stop is True

    def test_delete_cleans_up_callback(self, mock_sb_breakpoint):
        bp = Breakpoint(mock_sb_breakpoint)
        bp.set_callback(lambda f, l, e: True)
        assert id(bp) in _BP_CALLBACKS
        bp.delete()
        assert id(bp) not in _BP_CALLBACKS
