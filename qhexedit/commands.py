from PySide6.QtGui import QUndoStack, QUndoCommand
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .chunks import Chunks


class CommandType(Enum):
    """Command types for CharCommand"""

    INSERT = 0
    REMOVE_AT = 1
    OVERWRITE = 2


class CharCommand(QUndoCommand):
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
        if not isinstance(command, CharCommand):
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


class UndoStack(QUndoStack):
    """Undo stack for hex editor operations"""

    def __init__(self, chunks: "Chunks", parent=None):
        super().__init__(parent)
        self._chunks = chunks
        self.setUndoLimit(1000)

    def insert(self, pos: int, c=None):
        """Insert character(s) at position"""
        if isinstance(c, int):
            # Insert single character
            if 0 <= pos <= self._chunks.size():
                cc = CharCommand(self._chunks, CommandType.INSERT, pos, c)
                self.push(cc)
        elif isinstance(c, (bytes, bytearray)):
            # Insert byte array
            if 0 <= pos <= self._chunks.size():
                txt = self.tr(f"Inserting {len(c)} bytes")
                self.beginMacro(txt)
                for idx, byte in enumerate(c):
                    cc = CharCommand(self._chunks, CommandType.INSERT, pos + idx, byte)
                    self.push(cc)
                self.endMacro()

    def removeAt(self, pos: int, length: int = 1):
        """Remove character(s) at position"""
        if 0 <= pos < self._chunks.size():
            if length == 1:
                cc = CharCommand(self._chunks, CommandType.REMOVE_AT, pos, 0)
                self.push(cc)
            else:
                txt = self.tr(f"Delete {length} chars")
                self.beginMacro(txt)
                for cnt in range(length):
                    cc = CharCommand(self._chunks, CommandType.REMOVE_AT, pos, 0)
                    self.push(cc)
                self.endMacro()

    def overwrite(self, pos: int, c=None, length: int = None):
        """Overwrite character(s) at position"""
        if isinstance(c, int) and length is None:
            # Overwrite single character
            if 0 <= pos < self._chunks.size():
                cc = CharCommand(self._chunks, CommandType.OVERWRITE, pos, c)
                self.push(cc)
        elif isinstance(c, (bytes, bytearray)) and isinstance(length, int):
            # Overwrite with byte array
            if 0 <= pos < self._chunks.size():
                txt = self.tr(f"Overwrite {length} chars")
                self.beginMacro(txt)
                self.removeAt(pos, length)
                self.insert(pos, c)
                self.endMacro()
