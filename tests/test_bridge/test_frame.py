"""Tests for Frame wrapper."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from morgul.bridge.frame import Frame
from morgul.bridge.types import RegisterValue, Variable

# Ensure the module-level ``lldb`` inside frame.py has the constant we need.
_mock_lldb = MagicMock()
_mock_lldb.LLDB_INVALID_ADDRESS = 0xFFFFFFFFFFFFFFFF


class TestFrame:
    def test_pc(self, mock_sb_frame):
        frame = Frame(mock_sb_frame)
        assert frame.pc == 0x100003F00

    def test_sp(self, mock_sb_frame):
        frame = Frame(mock_sb_frame)
        assert frame.sp == 0x7FF7BFEFF680

    def test_fp(self, mock_sb_frame):
        frame = Frame(mock_sb_frame)
        assert frame.fp == 0x7FF7BFEFF690

    def test_index(self, mock_sb_frame):
        frame = Frame(mock_sb_frame)
        assert frame.index == 0

    def test_function_name(self, mock_sb_frame):
        frame = Frame(mock_sb_frame)
        assert frame.function_name == "main"

    def test_function_name_none(self, mock_sb_frame):
        mock_sb_frame.GetFunctionName.return_value = None
        frame = Frame(mock_sb_frame)
        assert frame.function_name is None

    def test_module_name(self, mock_sb_frame):
        frame = Frame(mock_sb_frame)
        assert frame.module_name == "a.out"

    def test_module_name_no_module(self, mock_sb_frame):
        mock_sb_frame.GetModule.return_value = None
        frame = Frame(mock_sb_frame)
        assert frame.module_name is None

    def test_line_entry(self, mock_sb_frame):
        frame = Frame(mock_sb_frame)
        le = frame.line_entry
        assert le["file"] == "/tmp/main.c"
        assert le["line"] == 10

    def test_line_entry_no_debug_info(self, mock_sb_frame):
        le = MagicMock()
        le.IsValid.return_value = False
        mock_sb_frame.GetLineEntry.return_value = le
        frame = Frame(mock_sb_frame)
        result = frame.line_entry
        assert result["file"] is None
        assert result["line"] is None

    def test_registers(self, mock_sb_frame):
        frame = Frame(mock_sb_frame)
        regs = frame.registers
        assert len(regs) == 1
        assert isinstance(regs[0], RegisterValue)
        assert regs[0].name == "rax"
        assert regs[0].value == 0x42

    def test_variables(self, mock_sb_frame):
        with patch("morgul.bridge.frame.lldb", _mock_lldb):
            frame = Frame(mock_sb_frame)
            vs = frame.variables()
        assert len(vs) == 1
        assert isinstance(vs[0], Variable)
        assert vs[0].name == "argc"
        assert vs[0].children == []

    def test_variables_struct_expansion(self):
        """Test that _to_variable recursively expands struct children."""
        # Build a mock struct variable with two fields
        child1 = MagicMock(name="child_x")
        child1.GetName.return_value = "x"
        child1.GetTypeName.return_value = "int"
        child1.GetValue.return_value = "10"
        child1.GetSummary.return_value = None
        child1.GetLoadAddress.return_value = 0xFFFFFFFFFFFFFFFF
        child1.GetByteSize.return_value = 4
        child1.IsValid.return_value = True
        child1.GetNumChildren.return_value = 0
        child1_type = MagicMock()
        child1_type.GetTypeClass.return_value = 1  # builtin
        child1.GetType.return_value = child1_type

        child2 = MagicMock(name="child_y")
        child2.GetName.return_value = "y"
        child2.GetTypeName.return_value = "int"
        child2.GetValue.return_value = "20"
        child2.GetSummary.return_value = None
        child2.GetLoadAddress.return_value = 0xFFFFFFFFFFFFFFFF
        child2.GetByteSize.return_value = 4
        child2.IsValid.return_value = True
        child2.GetNumChildren.return_value = 0
        child2_type = MagicMock()
        child2_type.GetTypeClass.return_value = 1
        child2.GetType.return_value = child2_type

        # Parent struct
        sb_val = MagicMock(name="struct_point")
        sb_val.GetName.return_value = "pt"
        sb_val.GetTypeName.return_value = "Point"
        sb_val.GetValue.return_value = None
        sb_val.GetSummary.return_value = "(x=10, y=20)"
        sb_val.GetLoadAddress.return_value = 0x1000
        sb_val.GetByteSize.return_value = 8
        sb_val.IsValid.return_value = True
        sb_val.GetNumChildren.return_value = 2
        sb_val.GetChildAtIndex.side_effect = lambda i: [child1, child2][i]
        sb_type = MagicMock()
        sb_type.GetTypeClass.return_value = 2  # eTypeClassStruct (not pointer)
        sb_val.GetType.return_value = sb_type

        with patch("morgul.bridge.frame.lldb", _mock_lldb):
            var = Frame._to_variable(sb_val)

        assert var.name == "pt"
        assert var.type_name == "Point"
        assert var.address == 0x1000
        assert len(var.children) == 2
        assert var.children[0].name == "x"
        assert var.children[0].value == "10"
        assert var.children[1].name == "y"
        assert var.children[1].value == "20"
        assert var.children[0].children == []

    def test_variables_pointer_dereference(self):
        """Test that _to_variable dereferences pointers to expand pointee fields."""
        # Field inside the pointee struct
        field = MagicMock(name="field_val")
        field.GetName.return_value = "value"
        field.GetTypeName.return_value = "int"
        field.GetValue.return_value = "42"
        field.GetSummary.return_value = None
        field.GetLoadAddress.return_value = 0xFFFFFFFFFFFFFFFF
        field.GetByteSize.return_value = 4
        field.IsValid.return_value = True
        field.GetNumChildren.return_value = 0
        field_type = MagicMock()
        field_type.GetTypeClass.return_value = 1
        field.GetType.return_value = field_type

        # Pointee (dereferenced struct)
        pointee = MagicMock(name="pointee")
        pointee.IsValid.return_value = True
        pointee.GetError.return_value = MagicMock(Success=MagicMock(return_value=True))
        pointee.GetNumChildren.return_value = 1
        pointee.GetChildAtIndex.return_value = field

        # Pointer variable
        sb_val = MagicMock(name="ptr_var")
        sb_val.GetName.return_value = "ctx"
        sb_val.GetTypeName.return_value = "Context *"
        sb_val.GetValue.return_value = "0x0000000100200000"
        sb_val.GetSummary.return_value = None
        sb_val.GetLoadAddress.return_value = 0x7FFF5000
        sb_val.GetByteSize.return_value = 8
        sb_val.IsValid.return_value = True
        sb_val.GetNumChildren.return_value = 1  # pointer has 1 synthetic child
        sb_type = MagicMock()
        sb_type.GetTypeClass.return_value = 65536  # eTypeClassPointer
        sb_val.GetType.return_value = sb_type
        sb_val.Dereference.return_value = pointee

        with patch("morgul.bridge.frame.lldb", _mock_lldb):
            var = Frame._to_variable(sb_val)

        assert var.name == "ctx"
        assert var.type_name == "Context *"
        # Should have expanded through the pointer to the pointee's fields
        assert len(var.children) == 1
        assert var.children[0].name == "value"
        assert var.children[0].value == "42"

    def test_evaluate_expression_success(self, mock_sb_frame):
        frame = Frame(mock_sb_frame)
        result = frame.evaluate_expression("argc")
        assert result == "42"

    def test_evaluate_expression_error(self, mock_sb_frame):
        expr_val = MagicMock()
        expr_error = MagicMock()
        expr_error.Fail.return_value = True
        expr_error.__str__ = lambda self: "unknown identifier"
        expr_val.GetError.return_value = expr_error
        mock_sb_frame.EvaluateExpression.return_value = expr_val
        frame = Frame(mock_sb_frame)
        result = frame.evaluate_expression("undefined_var")
        assert "error" in result
