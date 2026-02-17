"""Tests for memory utility functions."""

from __future__ import annotations

import struct
from unittest.mock import MagicMock, patch

import pytest

from morgul.bridge.memory import (
    get_memory_regions,
    read_pointer,
    read_string,
    read_uint8,
    read_uint16,
    read_uint32,
    read_uint64,
    search_memory,
    write_uint8,
    write_uint16,
    write_uint32,
    write_uint64,
)
from morgul.bridge.types import MemoryRegion


@pytest.fixture()
def mock_process():
    proc = MagicMock()
    proc.read_memory = MagicMock()
    proc.write_memory = MagicMock()
    return proc


class TestReadString:
    def test_basic(self, mock_process):
        mock_process.read_memory.return_value = b"hello\x00world"
        result = read_string(mock_process, 0x1000)
        assert result == "hello"

    def test_no_null_terminator(self, mock_process):
        mock_process.read_memory.return_value = b"hello"
        result = read_string(mock_process, 0x1000, max_length=5)
        assert result == "hello"

    def test_empty_string(self, mock_process):
        mock_process.read_memory.return_value = b"\x00rest"
        result = read_string(mock_process, 0x1000)
        assert result == ""

    def test_utf8_decode_errors(self, mock_process):
        mock_process.read_memory.return_value = b"\xff\xfe\x00"
        result = read_string(mock_process, 0x1000)
        assert isinstance(result, str)


class TestReadPointer:
    def test_8_byte_pointer(self, mock_process):
        sb_target = MagicMock()
        sb_target.GetAddressByteSize.return_value = 8
        mock_process._sb = MagicMock()
        mock_process._sb.GetTarget.return_value = sb_target
        mock_process.read_memory.return_value = struct.pack("<Q", 0xDEADBEEF)
        result = read_pointer(mock_process, 0x1000)
        assert result == 0xDEADBEEF

    def test_4_byte_pointer(self, mock_process):
        sb_target = MagicMock()
        sb_target.GetAddressByteSize.return_value = 4
        mock_process._sb = MagicMock()
        mock_process._sb.GetTarget.return_value = sb_target
        mock_process.read_memory.return_value = struct.pack("<I", 0xCAFEBABE)
        result = read_pointer(mock_process, 0x1000)
        assert result == 0xCAFEBABE


class TestFixedWidthReads:
    def test_read_uint8(self, mock_process):
        mock_process.read_memory.return_value = b"\x42"
        assert read_uint8(mock_process, 0x1000) == 0x42

    def test_read_uint16(self, mock_process):
        mock_process.read_memory.return_value = struct.pack("<H", 0x1234)
        assert read_uint16(mock_process, 0x1000) == 0x1234

    def test_read_uint32(self, mock_process):
        mock_process.read_memory.return_value = struct.pack("<I", 0xDEADBEEF)
        assert read_uint32(mock_process, 0x1000) == 0xDEADBEEF

    def test_read_uint64(self, mock_process):
        mock_process.read_memory.return_value = struct.pack("<Q", 0x123456789ABCDEF0)
        assert read_uint64(mock_process, 0x1000) == 0x123456789ABCDEF0


class TestFixedWidthWrites:
    def test_write_uint8(self, mock_process):
        write_uint8(mock_process, 0x1000, 0x42)
        mock_process.write_memory.assert_called_once_with(0x1000, struct.pack("B", 0x42))

    def test_write_uint16(self, mock_process):
        write_uint16(mock_process, 0x1000, 0x1234)
        mock_process.write_memory.assert_called_once_with(0x1000, struct.pack("<H", 0x1234))

    def test_write_uint32(self, mock_process):
        write_uint32(mock_process, 0x1000, 0xDEADBEEF)
        mock_process.write_memory.assert_called_once_with(0x1000, struct.pack("<I", 0xDEADBEEF))

    def test_write_uint64(self, mock_process):
        write_uint64(mock_process, 0x1000, 0x123456789ABCDEF0)
        mock_process.write_memory.assert_called_once_with(
            0x1000, struct.pack("<Q", 0x123456789ABCDEF0)
        )


class TestSearchMemory:
    def test_find_pattern(self, mock_process):
        data = b"\x00\x00\xDE\xAD\x00\x00\xDE\xAD\x00"
        mock_process.read_memory.return_value = data
        matches = search_memory(mock_process, 0x1000, len(data), b"\xDE\xAD")
        assert matches == [0x1002, 0x1006]

    def test_no_match(self, mock_process):
        mock_process.read_memory.return_value = b"\x00" * 16
        matches = search_memory(mock_process, 0x1000, 16, b"\xFF\xFF")
        assert matches == []

    def test_pattern_at_start(self, mock_process):
        mock_process.read_memory.return_value = b"\xAB\xCD\x00\x00"
        matches = search_memory(mock_process, 0x2000, 4, b"\xAB\xCD")
        assert matches == [0x2000]


class TestGetMemoryRegions:
    def test_empty_regions(self, mock_process):
        region_list = MagicMock()
        region_list.GetSize.return_value = 0
        mock_process._sb = MagicMock()
        mock_process._sb.GetMemoryRegions.return_value = region_list

        with patch("morgul.bridge.memory.lldb") as mock_lldb:
            mock_lldb.SBMemoryRegionInfo.return_value = MagicMock()
            regions = get_memory_regions(mock_process)
        assert regions == []
