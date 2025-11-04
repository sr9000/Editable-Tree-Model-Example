from enum import Enum
from typing import TYPE_CHECKING

from PySide6.QtGui import QUndoCommand, QUndoStack

if TYPE_CHECKING:
    from .chunks import Chunks


class CommandType(Enum):
    """Command types for CharCommand"""

    INSERT = 0
    REMOVE_AT = 1
    OVERWRITE = 2


class ChunksUndoCommand(QUndoCommand):
    """Undo command for single character operations"""

    def __init__(self, chunks: "Chunks", cmd: CommandType, charPos: int, newChar: int, parent=None):
        super().__init__(parent)
        self._chunks = chunks
        self._charPos = charPos
        self._wasChanged = False
        self._newChar = newChar
        self._oldChar = 0
        self._cmd = cmd

    def undo(self):
        """Undo the command"""
        if self._cmd == CommandType.INSERT:
            self._chunks.removeAt(self._charPos)
        elif self._cmd == CommandType.OVERWRITE:
            self._chunks.overwrite(self._charPos, self._oldChar)
            self._chunks.setDataChanged(self._charPos, self._wasChanged)
        elif self._cmd == CommandType.REMOVE_AT:
            self._chunks.insert(self._charPos, self._oldChar)
            self._chunks.setDataChanged(self._charPos, self._wasChanged)

    def redo(self):
        """Redo the command"""
        if self._cmd == CommandType.INSERT:
            self._chunks.insert(self._charPos, self._newChar)
        elif self._cmd == CommandType.OVERWRITE:
            self._oldChar = self._chunks[self._charPos]
            self._wasChanged = self._chunks.dataChanged(self._charPos)
            self._chunks.overwrite(self._charPos, self._newChar)
        elif self._cmd == CommandType.REMOVE_AT:
            self._oldChar = self._chunks[self._charPos]
            self._wasChanged = self._chunks.dataChanged(self._charPos)
            self._chunks.removeAt(self._charPos)

    def mergeWith(self, command: QUndoCommand) -> bool:
        """Merge with another command"""
        if not isinstance(command, ChunksUndoCommand):
            return False

        nextCommand = command

        if self._cmd != CommandType.REMOVE_AT:
            if nextCommand._cmd == CommandType.OVERWRITE:
                if nextCommand._charPos == self._charPos:
                    self._newChar = nextCommand._newChar
                    return True

        return False

    def id(self) -> int:
        """Return command ID for merging"""
        return 1234


class ChunksUndoStack(QUndoStack):
    """Undo stack for hex editor operations"""

    def __init__(self, chunks: "Chunks", parent=None):
        super().__init__(parent)
        self._chunks = chunks
        self.setUndoLimit(1000)

    def insert(self, pos: int, c=None):
        """Insert character(s) at position
        - insert(pos, int)
        - insert(pos, bytes|bytearray)
        """
        if isinstance(c, int):
            # Insert single character
            if 0 <= pos <= self._chunks.size():
                cc = ChunksUndoCommand(self._chunks, CommandType.INSERT, pos, c)
                self.push(cc)
        elif isinstance(c, (bytes, bytearray)):
            # Insert byte array
            if 0 <= pos <= self._chunks.size():
                txt = self.tr(f"Inserting {len(c)} bytes")
                self.beginMacro(txt)
                for idx, byte in enumerate(c):
                    cc = ChunksUndoCommand(self._chunks, CommandType.INSERT, pos + idx, byte)
                    self.push(cc)
                self.endMacro()

    def removeAt(self, pos: int, length: int = 1):
        """Remove character(s) at position
        - removeAt(pos)
        - removeAt(pos, length)
        """
        if 0 <= pos < self._chunks.size():
            if length == 1:
                cc = ChunksUndoCommand(self._chunks, CommandType.REMOVE_AT, pos, 0)
                self.push(cc)
            else:
                txt = self.tr(f"Delete {length} chars")
                self.beginMacro(txt)
                for _ in range(length):
                    cc = ChunksUndoCommand(self._chunks, CommandType.REMOVE_AT, pos, 0)
                    self.push(cc)
                self.endMacro()

    def overwrite(self, pos: int, c=None, length: int | None = None):
        """Overwrite character(s) at position.
        Supported call forms:
        - overwrite(pos, int)                        # single byte
        - overwrite(pos, bytes|bytearray, length)    # Python order (current)
        - overwrite(pos, length:int, bytes|bytearray)  # C++-style order
        """
        # Single-byte overwrite
        if isinstance(c, int) and (length is None or isinstance(length, bytes) or isinstance(length, bytearray)):
            # Detect C++-style order overload: overwrite(pos, length:int, ba:bytes)
            if isinstance(length, (bytes, bytearray)):
                # Translate to Python order
                ba = length
                ln = c
                if 0 <= pos < self._chunks.size():
                    txt = self.tr(f"Overwrite {ln} chars")
                    self.beginMacro(txt)
                    self.removeAt(pos, ln)
                    self.insert(pos, ba)
                    self.endMacro()
                return

            # Standard single-byte path
            if 0 <= pos < self._chunks.size():
                cc = ChunksUndoCommand(self._chunks, CommandType.OVERWRITE, pos, c)
                self.push(cc)
            return

        # Byte-array overwrite with explicit length (Python order)
        if isinstance(c, (bytes, bytearray)) and isinstance(length, int):
            if 0 <= pos < self._chunks.size():
                txt = self.tr(f"Overwrite {length} chars")
                self.beginMacro(txt)
                self.removeAt(pos, length)
                self.insert(pos, c)
                self.endMacro()
            return
        # No-op for invalid call shapes
        return
