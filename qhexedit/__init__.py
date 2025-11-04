from PySide6.QtWidgets import QAbstractScrollArea, QApplication
from PySide6.QtCore import Qt, QRect, QPoint, QIODevice, QBuffer, QTimer, Signal
from PySide6.QtGui import (
    QPainter,
    QFont,
    QFontMetrics,
    QKeySequence,
    QPalette,
    QKeyEvent,
    QMouseEvent,
    QPaintEvent,
    QResizeEvent,
    QFontDatabase,
)
from typing import Optional

from .chunks import Chunks
from .commands import UndoStack, CommandType
from .color_manager import ColorManager, Area


class QHexEdit(QAbstractScrollArea):
    """Hex editor widget for binary data editing"""

    # Signals
    currentAddressChanged = Signal(int)
    currentSizeChanged = Signal(int)
    dataChanged = Signal()
    overwriteModeChanged = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)

        # Properties
        self._addressArea = True
        self._addressWidth = 4
        self._asciiArea = True
        self._addressOffset = 0
        self._bytesPerLine = 16
        self._hexCharsInLine = 47
        self._highlighting = True
        self._overwriteMode = True
        self._readOnly = False
        self._hexCaps = False
        self._dynamicBytesPerLine = True  # enable dynamic resizing by default

        # Internal state
        self._editAreaIsAscii = False
        self._addrDigits = 0
        self._blink = False
        self._modified = False

        # Pixel positions
        self._pxCharWidth = 0
        self._pxCharHeight = 0
        self._pxPosHexX = 0
        self._pxPosAdrX = 0
        self._pxPosAsciiX = 0
        self._pxAreaMargin = 0
        self._pxCursorWidth = 0
        self._pxSelectionSub = 0
        self._pxCursorX = 0
        self._pxCursorY = 0

        # Byte positions
        self._bSelectionBegin = 0
        self._bSelectionEnd = 0
        self._bPosFirst = 0
        self._bPosLast = 0
        self._bPosCurrent = 0

        # Data
        self._bData = QBuffer(self)
        self._chunks = Chunks(self)
        self._cursorPosition = 0
        self._cursorRect = QRect()
        self._data = bytearray()
        self._dataShown = bytearray()
        self._hexDataShown = bytearray()
        self._lastEventSize = 0
        self._markedShown = bytearray()
        self._rowsShown = 0

        # Components
        self._undoStack = UndoStack(self._chunks, self)
        self._colorManager = ColorManager()
        self._cursorTimer = QTimer(self)

        # Setup: align font with app theme but force monospaced family
        app_font = QApplication.font()
        fixed = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        # Use app font point size if available for theme alignment
        if app_font.pointSize() > 0:
            fixed.setPointSize(app_font.pointSize())
        elif app_font.pixelSize() > 0:
            fixed.setPixelSize(app_font.pixelSize())
        self.setFont(fixed)

        # Connect signals
        self._cursorTimer.timeout.connect(self._updateCursor)
        self.verticalScrollBar().valueChanged.connect(self._adjust)
        self.horizontalScrollBar().valueChanged.connect(self._adjust)
        self._undoStack.indexChanged.connect(self._dataChangedPrivate)

        self._cursorTimer.setInterval(500)
        self._cursorTimer.start()

        self.setAddressWidth(4)
        self.setAddressArea(True)
        self.setAsciiArea(True)
        self.setOverwriteMode(True)
        self.setHighlighting(True)
        self.setReadOnly(False)

        self._init()

    # Properties

    def addressArea(self) -> bool:
        """Get address area visibility"""
        return self._addressArea

    def setAddressArea(self, addressArea: bool):
        """Set address area visibility"""
        self._addressArea = addressArea
        self._adjust()
        self.setCursorPosition(self._cursorPosition)
        self.viewport().update()

    def addressOffset(self) -> int:
        """Get address offset"""
        return self._addressOffset

    def setAddressOffset(self, addressOffset: int):
        """Set address offset"""
        self._addressOffset = addressOffset
        self._adjust()
        self.setCursorPosition(self._cursorPosition)
        self.viewport().update()

    def addressWidth(self) -> int:
        """Get address width in characters"""
        size = self._chunks.size()
        n = 1
        if size > 0x100000000:
            n += 8
            size //= 0x100000000
        if size > 0x10000:
            n += 4
            size //= 0x10000
        if size > 0x100:
            n += 2
            size //= 0x100
        if size > 0x10:
            n += 1

        return max(n, self._addressWidth)

    def setAddressWidth(self, addressWidth: int):
        """Set address width in characters"""
        self._addressWidth = addressWidth
        self._adjust()
        self.setCursorPosition(self._cursorPosition)
        self.viewport().update()

    def asciiArea(self) -> bool:
        """Get ASCII area visibility"""
        return self._asciiArea

    def setAsciiArea(self, asciiArea: bool):
        """Set ASCII area visibility"""
        if not asciiArea:
            self._editAreaIsAscii = False
        self._asciiArea = asciiArea
        self._adjust()
        self.setCursorPosition(self._cursorPosition)
        self.viewport().update()

    def bytesPerLine(self) -> int:
        """Get bytes per line"""
        return self._bytesPerLine

    def setBytesPerLine(self, count: int):
        """Set bytes per line"""
        self._bytesPerLine = count
        self._hexCharsInLine = count * 3 - 1
        self._adjust()
        self.setCursorPosition(self._cursorPosition)
        self.viewport().update()

    def cursorPosition(self, pos: Optional[QPoint] = None) -> int:
        """Get cursor position or calculate from point"""
        if pos is None:
            return self._cursorPosition

        # Calculate cursor position from graphical position
        result = -1
        posX = pos.x() + self.horizontalScrollBar().value()
        posY = pos.y() - 3

        if posX >= self._pxPosHexX and posX < (self._pxPosHexX + (1 + self._hexCharsInLine) * self._pxCharWidth):
            self._editAreaIsAscii = False
            x = (posX - self._pxPosHexX) // self._pxCharWidth
            x = (x // 3) * 2 + x % 3
            y = (posY // self._pxCharHeight) * 2 * self._bytesPerLine
            result = self._bPosFirst * 2 + x + y

        if (
            self._asciiArea
            and (posX >= self._pxPosAsciiX)
            and (posX < (self._pxPosAsciiX + (1 + self._bytesPerLine) * self._pxCharWidth))
        ):
            self._editAreaIsAscii = True
            x = 2 * ((posX - self._pxPosAsciiX) // self._pxCharWidth)
            y = (posY // self._pxCharHeight) * 2 * self._bytesPerLine
            result = self._bPosFirst * 2 + x + y

        return result

    def setCursorPosition(self, position: int):
        """Set cursor position"""
        # Delete old cursor
        self._blink = False
        self.viewport().update(self._cursorRect)

        # Check if cursor in range
        if position > (self._chunks.size() * 2 - 1):
            position = self._chunks.size() * 2 - (1 if self._overwriteMode else 0)

        if position < 0:
            position = 0

        # Calculate new position of cursor
        self._bPosCurrent = position // 2
        self._pxCursorY = ((position // 2 - self._bPosFirst) // self._bytesPerLine + 1) * self._pxCharHeight
        x = position % (2 * self._bytesPerLine)

        if self._editAreaIsAscii:
            self._pxCursorX = x // 2 * self._pxCharWidth + self._pxPosAsciiX
            self._cursorPosition = position & 0xFFFFFFFFFFFFFFFE
        else:
            self._pxCursorX = (((x // 2) * 3) + (x % 2)) * self._pxCharWidth + self._pxPosHexX
            self._cursorPosition = position

        pxOfsX = self.horizontalScrollBar().value()

        if self._readOnly:
            self._cursorRect = QRect(
                self._pxCursorX - pxOfsX,
                self._pxCursorY - self._pxCharHeight + self._pxSelectionSub,
                self._pxCharWidth,
                self._pxCharHeight,
            )
        else:
            if self._overwriteMode:
                self._cursorRect = QRect(
                    self._pxCursorX - pxOfsX,
                    self._pxCursorY + self._pxCursorWidth,
                    self._pxCharWidth,
                    self._pxCursorWidth,
                )
            else:
                self._cursorRect = QRect(
                    self._pxCursorX - pxOfsX,
                    self._pxCursorY - self._pxCharHeight + self._pxSelectionSub,
                    self._pxCursorWidth,
                    self._pxCharHeight,
                )

        # Immediately draw new cursor
        self._blink = True
        self.viewport().update(self._cursorRect)
        self.currentAddressChanged.emit(self._bPosCurrent)

    def data(self) -> bytearray:
        """Get all data"""
        return self._chunks.data()

    def setData(self, data):
        """Set data from QByteArray or QIODevice"""
        if isinstance(data, QIODevice):
            self._chunks.setIODevice(data)
        else:
            self._bData.close()
            self._data = bytearray(data)
            self._bData.setData(bytes(self._data))
            self._chunks.setIODevice(self._bData)

        self._init()
        self._adjust()
        self.dataChanged.emit()

    def hexCaps(self) -> bool:
        """Get hex capitalization"""
        return self._hexCaps

    def setHexCaps(self, isCaps: bool):
        """Set hex capitalization"""
        self._hexCaps = isCaps
        self.viewport().update()

    def dynamicBytesPerLine(self) -> bool:
        """Get dynamic bytes per line"""
        return self._dynamicBytesPerLine

    def setDynamicBytesPerLine(self, isDynamic: bool):
        """Set dynamic bytes per line and recalc layout immediately"""
        self._dynamicBytesPerLine = isDynamic
        if isDynamic and self._pxCharWidth > 0:
            # Compute bytes/line from current viewport like in resizeEvent
            pxFixGaps = 0
            if self._addressArea:
                pxFixGaps = self.addressWidth() * self._pxCharWidth + 2 * self._pxAreaMargin
            pxFixGaps += 2 * self._pxAreaMargin
            if self._asciiArea:
                pxFixGaps += 2 * self._pxAreaMargin
            charWidth = (self.viewport().width() - pxFixGaps) // self._pxCharWidth + 1
            self._bytesPerLine = max(charWidth // (4 if self._asciiArea else 3), 1)
            self._hexCharsInLine = self._bytesPerLine * 3 - 1
        self._adjust()

    def highlighting(self) -> bool:
        """Get highlighting enabled"""
        return self._highlighting

    def setHighlighting(self, mode: bool):
        """Set highlighting enabled"""
        self._highlighting = mode
        self.viewport().update()

    def highlightingColor(self):
        """Get highlighting color"""
        return self._colorManager.highlighting().areaColor()

    def setHighlightingColor(self, color):
        """Set highlighting color"""
        self._colorManager.highlighting().setAreaColor(color)
        self.viewport().update()

    def overwriteMode(self) -> bool:
        """Get overwrite mode"""
        return self._overwriteMode

    def setOverwriteMode(self, overwriteMode: bool):
        """Set overwrite mode"""
        self._overwriteMode = overwriteMode
        self.overwriteModeChanged.emit(overwriteMode)
        self.setCursorPosition(self._cursorPosition)

    def isReadOnly(self) -> bool:
        """Get read-only mode"""
        return self._readOnly

    def setReadOnly(self, readOnly: bool):
        """Set read-only mode"""
        self._readOnly = readOnly
        self.setCursorPosition(self._cursorPosition)

    # Data access methods

    def dataAt(self, pos: int, count: int = -1) -> bytearray:
        """Get data at position"""
        return self._chunks.data(pos, count)

    def write(self, ioDevice: QIODevice, pos: int = 0, count: int = -1) -> bool:
        """Write data to IO device"""
        return self._chunks.write(ioDevice, pos, count)

    # Char and ByteArray handling

    def insert(self, pos: int, ch):
        """Insert char or byte array at position"""
        if isinstance(ch, int):
            self._undoStack.insert(pos, ch)
        else:
            self._undoStack.insert(pos, bytes(ch))

    def remove(self, pos: int, length: int = 1):
        """Remove bytes from content"""
        self._undoStack.removeAt(pos, length)

    def replace(self, pos: int, ch_or_len, ba=None):
        """Replace char or bytes at position"""
        if ba is None:
            # replace(pos, ch)
            self._undoStack.overwrite(pos, ch_or_len)
        else:
            # replace(pos, len, ba)
            self._undoStack.overwrite(pos, bytes(ba), ch_or_len)

    # User marking areas

    def addUserArea(self, posStart: int, posEnd: int, fontColor, areaStyle):
        """Add user defined marking area"""
        self._colorManager.addUserArea(posStart, posEnd, fontColor, areaStyle)
        self.viewport().update()

    def clearUserAreas(self):
        """Clear all user defined areas"""
        self._colorManager.clearUserAreas()
        self.viewport().update()

    # Utility functions

    def ensureVisible(self):
        """Ensure the cursor is visible (both vertically and horizontally)"""
        vscroll = self.verticalScrollBar()
        hscroll = self.horizontalScrollBar()

        if self._cursorPosition < (self._bPosFirst * 2):
            vscroll.setValue((self._cursorPosition // 2) // self._bytesPerLine)
        if self._cursorPosition > ((self._bPosFirst + (self._rowsShown - 1) * self._bytesPerLine) * 2):
            vscroll.setValue((self._cursorPosition // 2) // self._bytesPerLine - self._rowsShown + 1)

        if self._pxCursorX < hscroll.value():
            hscroll.setValue(self._pxCursorX)
        if (self._pxCursorX + self._pxCharWidth) > (hscroll.value() + self.viewport().width()):
            hscroll.setValue(self._pxCursorX + self._pxCharWidth - self.viewport().width())

        self.viewport().update()

    def indexOf(self, ba: bytes, from_pos: int) -> int:
        """Find first occurrence of ba in data"""
        pos = self._chunks.indexOf(ba, from_pos)
        if pos > -1:
            curPos = pos * 2
            # Match C++: place cursor at end of the found range
            self.setCursorPosition(curPos + len(ba) * 2)
            self._resetSelection(curPos)
            self._setSelection(curPos + len(ba) * 2)
            self.ensureVisible()
        return pos

    def isModified(self) -> bool:
        """Check if document is modified"""
        return self._modified

    def lastIndexOf(self, ba: bytes, from_pos: int) -> int:
        """Find last occurrence of ba in data"""
        pos = self._chunks.lastIndexOf(ba, from_pos)
        if pos > -1:
            curPos = pos * 2
            self.setCursorPosition(curPos - 1)
            self._resetSelection(curPos)
            self._setSelection(curPos + len(ba) * 2)
            self.ensureVisible()
        return pos

    def selectionToReadableString(self) -> str:
        """Get formatted image of selected content"""
        ba = self._chunks.data(self._getSelectionBegin(), self._getSelectionEnd() - self._getSelectionBegin())
        return self._toReadable(ba)

    def selectedData(self) -> str:
        """Return selected content as hex string"""
        ba = self._chunks.data(self._getSelectionBegin(), self._getSelectionEnd() - self._getSelectionBegin())
        return bytes(ba).hex()

    def setFont(self, font: QFont):
        """Set font"""
        theFont = QFont(font)
        theFont.setStyleHint(QFont.StyleHint.Monospace)
        super().setFont(theFont)

        # Update metrics according to the current font
        self._updateFontMetrics()

    def _updateFontMetrics(self):
        """Recompute metrics from current widget font and refresh"""
        metrics = QFontMetrics(self.font())
        self._pxCharWidth = metrics.horizontalAdvance("2")
        self._pxCharHeight = metrics.height()
        self._pxAreaMargin = self._pxCharWidth // 2
        self._pxCursorWidth = self._pxCharHeight // 7
        self._pxSelectionSub = self._pxCharHeight // 5
        self.viewport().update()

    def toReadableString(self) -> str:
        """Get formatted image of content"""
        ba = self._chunks.data()
        return self._toReadable(ba)

    # Public slots

    def redo(self):
        """Redo last operation"""
        self._undoStack.redo()
        self.setCursorPosition(self._chunks.pos() * (1 if self._editAreaIsAscii else 2))
        self._refresh()

    def undo(self):
        """Undo last operation"""
        self._undoStack.undo()
        self.setCursorPosition(self._chunks.pos() * (1 if self._editAreaIsAscii else 2))
        self._refresh()

    # Event handlers

    def event(self, event):
        """Handle generic events"""
        if event is not None and event.type() == event.Type.PaletteChange:
            palette = self.palette()
            self._colorManager.setPalette(palette)
        # Align font size with app theme when the application font changes
        if event is not None and event.type() == event.Type.ApplicationFontChange:
            app_font = QApplication.font()
            fixed = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
            if app_font.pointSize() > 0:
                fixed.setPointSize(app_font.pointSize())
            elif app_font.pixelSize() > 0:
                fixed.setPixelSize(app_font.pixelSize())
            self.setFont(fixed)
        # Recompute metrics if our own font changed (avoid resetting font to prevent loops)
        if event is not None and event.type() == event.Type.FontChange:
            self._updateFontMetrics()
        return super().event(event)

    def keyPressEvent(self, event: QKeyEvent):
        """Handle key press events"""
        # Cursor movements
        if event.matches(QKeySequence.StandardKey.MoveToNextChar):
            pos = self._cursorPosition + 1
            if self._editAreaIsAscii:
                pos += 1
            self.setCursorPosition(pos)
            self._resetSelection(pos)
        elif event.matches(QKeySequence.StandardKey.MoveToPreviousChar):
            pos = self._cursorPosition - 1
            if self._editAreaIsAscii:
                pos -= 1
            self.setCursorPosition(pos)
            self._resetSelection(pos)
        elif event.matches(QKeySequence.StandardKey.MoveToEndOfLine):
            pos = (
                self._cursorPosition - (self._cursorPosition % (2 * self._bytesPerLine)) + (2 * self._bytesPerLine) - 1
            )
            self.setCursorPosition(pos)
            self._resetSelection(self._cursorPosition)
        elif event.matches(QKeySequence.StandardKey.MoveToStartOfLine):
            pos = self._cursorPosition - (self._cursorPosition % (2 * self._bytesPerLine))
            self.setCursorPosition(pos)
            self._resetSelection(self._cursorPosition)
        elif event.matches(QKeySequence.StandardKey.MoveToPreviousLine):
            self.setCursorPosition(self._cursorPosition - (2 * self._bytesPerLine))
            self._resetSelection(self._cursorPosition)
        elif event.matches(QKeySequence.StandardKey.MoveToNextLine):
            self.setCursorPosition(self._cursorPosition + (2 * self._bytesPerLine))
            self._resetSelection(self._cursorPosition)
        elif event.matches(QKeySequence.StandardKey.MoveToNextPage):
            self.setCursorPosition(self._cursorPosition + ((self._rowsShown - 1) * 2 * self._bytesPerLine))
            self._resetSelection(self._cursorPosition)
        elif event.matches(QKeySequence.StandardKey.MoveToPreviousPage):
            self.setCursorPosition(self._cursorPosition - ((self._rowsShown - 1) * 2 * self._bytesPerLine))
            self._resetSelection(self._cursorPosition)
        elif event.matches(QKeySequence.StandardKey.MoveToEndOfDocument):
            self.setCursorPosition(self._chunks.size() * 2)
            self._resetSelection(self._cursorPosition)
        elif event.matches(QKeySequence.StandardKey.MoveToStartOfDocument):
            self.setCursorPosition(0)
            self._resetSelection(self._cursorPosition)

        # Select commands
        elif event.matches(QKeySequence.StandardKey.SelectAll):
            self._resetSelection(0)
            self._setSelection(2 * self._chunks.size() + 1)
        elif event.matches(QKeySequence.StandardKey.SelectNextChar):
            pos = self._cursorPosition + 1
            if self._editAreaIsAscii:
                pos += 1
            self.setCursorPosition(pos)
            self._setSelection(pos)
        elif event.matches(QKeySequence.StandardKey.SelectPreviousChar):
            pos = self._cursorPosition - 1
            if self._editAreaIsAscii:
                pos -= 1
            self._setSelection(pos)
            self.setCursorPosition(pos)
        elif event.matches(QKeySequence.StandardKey.SelectEndOfLine):
            pos = (
                self._cursorPosition - (self._cursorPosition % (2 * self._bytesPerLine)) + (2 * self._bytesPerLine) - 1
            )
            self.setCursorPosition(pos)
            self._setSelection(pos)
        elif event.matches(QKeySequence.StandardKey.SelectStartOfLine):
            pos = self._cursorPosition - (self._cursorPosition % (2 * self._bytesPerLine))
            self.setCursorPosition(pos)
            self._setSelection(pos)
        elif event.matches(QKeySequence.StandardKey.SelectPreviousLine):
            pos = self._cursorPosition - (2 * self._bytesPerLine)
            self.setCursorPosition(pos)
            self._setSelection(pos)
        elif event.matches(QKeySequence.StandardKey.SelectNextLine):
            pos = self._cursorPosition + (2 * self._bytesPerLine)
            self.setCursorPosition(pos)
            self._setSelection(pos)
        elif event.matches(QKeySequence.StandardKey.SelectNextPage):
            pos = self._cursorPosition + ((self.viewport().height() // self._pxCharHeight - 1) * 2 * self._bytesPerLine)
            self.setCursorPosition(pos)
            self._setSelection(pos)
        elif event.matches(QKeySequence.StandardKey.SelectPreviousPage):
            pos = self._cursorPosition - ((self.viewport().height() // self._pxCharHeight - 1) * 2 * self._bytesPerLine)
            self.setCursorPosition(pos)
            self._setSelection(pos)
        elif event.matches(QKeySequence.StandardKey.SelectEndOfDocument):
            pos = self._chunks.size() * 2
            self.setCursorPosition(pos)
            self._setSelection(pos)
        elif event.matches(QKeySequence.StandardKey.SelectStartOfDocument):
            pos = 0
            self.setCursorPosition(pos)
            self._setSelection(pos)

        # Edit commands
        elif not self._readOnly:
            if event.matches(QKeySequence.StandardKey.Cut):
                ba = self._chunks.data(self._getSelectionBegin(), self._getSelectionEnd() - self._getSelectionBegin())
                hex_data = bytes(ba).hex()
                # Format with newlines every 32 chars
                formatted = "\n".join([hex_data[i : i + 32] for i in range(0, len(hex_data), 32)])
                QApplication.clipboard().setText(formatted)

                if self._overwriteMode:
                    length = self._getSelectionEnd() - self._getSelectionBegin()
                    self.replace(self._getSelectionBegin(), length, bytearray(length))
                else:
                    self.remove(self._getSelectionBegin(), self._getSelectionEnd() - self._getSelectionBegin())

                self.setCursorPosition(2 * self._getSelectionBegin())
                self._resetSelection(2 * self._getSelectionBegin())

            elif event.matches(QKeySequence.StandardKey.Paste):
                clipboard = QApplication.clipboard()
                # Accept all whitespace (spaces, tabs, newlines, etc.) like Qt QByteArray::fromHex
                raw_text = clipboard.text()
                hex_string = "".join(raw_text.split())

                try:
                    ba = bytes.fromhex(hex_string)
                    if self._overwriteMode:
                        length = min(len(ba), self._chunks.size() - self._bPosCurrent)
                        if length > 0:
                            self.replace(self._bPosCurrent, length, ba[:length])
                    else:
                        self.insert(self._bPosCurrent, ba)

                    self.setCursorPosition(self._cursorPosition + 2 * len(ba))
                    # Match C++: keep selection anchored where it was
                    self._resetSelection(2 * self._getSelectionBegin())
                except ValueError:
                    pass  # Invalid hex string

            elif event.matches(QKeySequence.StandardKey.Delete):
                if self._getSelectionBegin() != self._getSelectionEnd():
                    length = self._getSelectionEnd() - self._getSelectionBegin()
                    if self._overwriteMode:
                        self.replace(self._getSelectionBegin(), length, bytearray(length))
                    else:
                        self.remove(self._getSelectionBegin(), length)
                    self.setCursorPosition(2 * self._getSelectionBegin())
                    self._resetSelection(self._cursorPosition)
                elif self._overwriteMode:
                    self.replace(self._bPosCurrent, 0)
                else:
                    self.remove(self._bPosCurrent, 1)

            elif event.key() == Qt.Key.Key_Backspace:
                if self._getSelectionBegin() != self._getSelectionEnd():
                    length = self._getSelectionEnd() - self._getSelectionBegin()
                    if self._overwriteMode:
                        self.replace(self._getSelectionBegin(), length, bytearray(length))
                    else:
                        self.remove(self._getSelectionBegin(), length)
                    self.setCursorPosition(2 * self._getSelectionBegin())
                    self._resetSelection(self._cursorPosition)
                else:
                    # Move cursor left first (nibble for hex, full byte for ASCII)
                    move_nibbles = 2 if self._editAreaIsAscii else 1
                    targetPos = max(self._cursorPosition - move_nibbles, 0)
                    byte_index = targetPos // 2
                    if self._chunks.size() > 0 and byte_index <= self._chunks.size() - 1:
                        if self._overwriteMode:
                            self.replace(byte_index, 0)
                        else:
                            self.remove(byte_index, 1)
                    self.setCursorPosition(targetPos)
                    self._resetSelection(targetPos)

            elif event.matches(QKeySequence.StandardKey.Undo):
                self.undo()

            elif event.matches(QKeySequence.StandardKey.Redo):
                self.redo()

            else:
                # Hex and ASCII input (process only when event.text() yields characters)
                key = 0
                text = event.text()

                if text:
                    if self._editAreaIsAscii:
                        key = ord(text[0])
                    else:
                        key = ord(text[0].lower())

                if (("0" <= chr(key) <= "9" or "a" <= chr(key) <= "f") and not self._editAreaIsAscii) or (
                    key >= ord(" ") and self._editAreaIsAscii
                ):

                    if self._getSelectionBegin() != self._getSelectionEnd():
                        if self._overwriteMode:
                            length = self._getSelectionEnd() - self._getSelectionBegin()
                            self.replace(self._getSelectionBegin(), length, bytearray(length))
                        else:
                            self.remove(self._getSelectionBegin(), self._getSelectionEnd() - self._getSelectionBegin())
                            self._bPosCurrent = self._getSelectionBegin()

                        self.setCursorPosition(2 * self._bPosCurrent)
                        self._resetSelection(2 * self._bPosCurrent)

                    # Insert mode - insert a byte
                    if not self._overwriteMode:
                        if (self._cursorPosition % 2) == 0:
                            self.insert(self._bPosCurrent, 0)

                    # Change content
                    if self._chunks.size() > 0:
                        ch = key
                        if not self._editAreaIsAscii:
                            hexValue = bytes(self._chunks.data(self._bPosCurrent, 1)).hex()
                            hexValue = list(hexValue)
                            if (self._cursorPosition % 2) == 0:
                                hexValue[0] = chr(key)
                            else:
                                hexValue[1] = chr(key)
                            ch = bytes.fromhex("".join(hexValue))[0]

                        self.replace(self._bPosCurrent, ch)

                        if self._editAreaIsAscii:
                            self.setCursorPosition(self._cursorPosition + 2)
                        else:
                            self.setCursorPosition(self._cursorPosition + 1)

                        self._resetSelection(self._cursorPosition)

        # Copy (available in read-only mode too)
        if event.matches(QKeySequence.StandardKey.Copy):
            ba = self._chunks.data(self._getSelectionBegin(), self._getSelectionEnd() - self._getSelectionBegin())
            hex_data = bytes(ba).hex()
            # Format with newlines every 32 chars
            formatted = "\n".join([hex_data[i : i + 32] for i in range(0, len(hex_data), 32)])
            QApplication.clipboard().setText(formatted)

        # Switch between insert/overwrite mode
        if event.key() == Qt.Key.Key_Insert and event.modifiers() == Qt.KeyboardModifier.NoModifier:
            self.setOverwriteMode(not self.overwriteMode())
            self.setCursorPosition(self._cursorPosition)

        # Switch from hex to ASCII edit
        if event.key() == Qt.Key.Key_Tab and not self._editAreaIsAscii:
            self._editAreaIsAscii = True
            self.setCursorPosition(self._cursorPosition)

        # Switch from ASCII to hex edit
        if event.key() == Qt.Key.Key_Backtab and self._editAreaIsAscii:
            self._editAreaIsAscii = False
            self.setCursorPosition(self._cursorPosition)

        # Handle backspace in read-only mode: move cursor even if no edits allowed
        if self._readOnly and event.key() == Qt.Key.Key_Backspace:
            move_nibbles = 2 if self._editAreaIsAscii else 1
            targetPos = max(self._cursorPosition - move_nibbles, 0)
            self.setCursorPosition(targetPos)
            self._resetSelection(targetPos)

        self._refresh()

    def mouseMoveEvent(self, event: QMouseEvent):
        """Handle mouse move events"""
        self._blink = False
        self.viewport().update()
        actPos = self.cursorPosition(event.pos())
        if actPos >= 0:
            self.setCursorPosition(actPos)
            self._setSelection(actPos)

    def mousePressEvent(self, event: QMouseEvent):
        """Handle mouse press events"""
        self._blink = False
        self.viewport().update()
        cPos = self.cursorPosition(event.pos())
        if cPos >= 0:
            if event.button() != Qt.MouseButton.RightButton:
                self._resetSelection(cPos)
            self.setCursorPosition(cPos)

    def paintEvent(self, event: QPaintEvent):
        """Handle paint events"""
        painter = QPainter(self.viewport())
        pxOfsX = self.horizontalScrollBar().value()
        pxPosAsciiX2 = self._pxPosAsciiX - pxOfsX

        if event.rect() != self._cursorRect:
            pxPosStartY = self._pxCharHeight

            # Prepare background
            painter.fillRect(event.rect(), self.viewport().palette().color(QPalette.ColorRole.Base))

            if self._addressArea:
                painter.fillRect(
                    QRect(-pxOfsX, event.rect().top(), self._pxCharWidth * (self._addrDigits + 1), self.height()),
                    self._colorManager.notMarked(Area.Address).areaStyle(),
                )

            if self._asciiArea:
                painter.fillRect(
                    QRect(
                        pxPosAsciiX2 - self._pxAreaMargin,
                        event.rect().top(),
                        self._pxCharWidth * self._bytesPerLine + 2 * self._pxAreaMargin,
                        self.height(),
                    ),
                    self._colorManager.notMarked(Area.Ascii).areaStyle(),
                )

            # Paint central areas
            for row in range(self._rowsShown + 1):
                pxPosY = pxPosStartY + row * self._pxCharHeight
                bPosLine = row * self._bytesPerLine
                pxPosX = self._pxPosHexX - pxOfsX
                pxPosAsciiX2 = self._pxPosAsciiX - pxOfsX

                # Address info
                if self._addressArea and row * self._bytesPerLine < len(self._dataShown):
                    address = f"{self._bPosFirst + row * self._bytesPerLine + self._addressOffset:0{self._addrDigits}x}"
                    addressArea = self._colorManager.notMarked(Area.Address)
                    painter.setPen(addressArea.fontPen())
                    painter.drawText(self._pxPosAdrX - pxOfsX, pxPosY, address.upper() if self._hexCaps else address)

                # Data
                for colIdx in range(min(len(self._dataShown) - bPosLine, self._bytesPerLine)):
                    posBa = self._bPosFirst + bPosLine + colIdx

                    # Hex values
                    hexArea = self._colorManager.markedArea(posBa, Area.Hex, self._chunks)
                    painter.setPen(hexArea.fontPen())

                    if colIdx == 0:
                        rect = QRect(
                            pxPosX,
                            pxPosY - self._pxCharHeight + self._pxSelectionSub,
                            2 * self._pxCharWidth,
                            self._pxCharHeight,
                        )
                    else:
                        rect = QRect(
                            pxPosX - self._pxCharWidth,
                            pxPosY - self._pxCharHeight + self._pxSelectionSub,
                            3 * self._pxCharWidth,
                            self._pxCharHeight,
                        )

                    painter.fillRect(rect, hexArea.areaStyle())

                    hex_str = self._hexDataShown[(bPosLine + colIdx) * 2 : (bPosLine + colIdx) * 2 + 2].decode("ascii")
                    painter.drawText(pxPosX, pxPosY, hex_str.upper() if self._hexCaps else hex_str)
                    pxPosX += 3 * self._pxCharWidth

                    # ASCII values
                    if self._asciiArea:
                        asciiArea = self._colorManager.markedArea(posBa, Area.Ascii, self._chunks)
                        painter.setPen(asciiArea.fontPen())

                        ch = self._dataShown[bPosLine + colIdx]
                        if ch < ord(" ") or ch > ord("~"):
                            ch = ord(".")

                        rect.setRect(
                            pxPosAsciiX2,
                            pxPosY - self._pxCharHeight + self._pxSelectionSub,
                            self._pxCharWidth,
                            self._pxCharHeight,
                        )
                        painter.fillRect(rect, asciiArea.areaStyle())
                        painter.drawText(pxPosAsciiX2, pxPosY, chr(ch))
                        pxPosAsciiX2 += self._pxCharWidth

        # Paint cursor
        hexPos = self._cursorPosition - 2 * self._bPosFirst

        if 0 <= hexPos <= len(self._hexDataShown):
            if self._editAreaIsAscii:
                curArea = self._colorManager.markedArea(hexPos // 2, Area.Ascii, self._chunks)
            else:
                curArea = self._colorManager.markedArea(hexPos // 2, Area.Hex, self._chunks)

            if self._blink and self.hasFocus():
                painter.fillRect(self._cursorRect, curArea.fontColor())

            # Repaint current char
            painter.setPen(curArea.fontColor())

            if self._editAreaIsAscii:
                if hexPos // 2 < len(self._dataShown):
                    ch = self._dataShown[hexPos // 2]
                    if ch < ord(" ") or ch > ord("~"):
                        ch = ord(".")
                    painter.drawText(self._pxCursorX - pxOfsX, self._pxCursorY, chr(ch))
            else:
                if hexPos < len(self._hexDataShown):
                    txt = chr(self._hexDataShown[hexPos])
                    if self._hexCaps:
                        txt = txt.upper()
                    painter.drawText(self._pxCursorX - pxOfsX, self._pxCursorY, txt)

        # Emit size changed event
        if self._lastEventSize != self._chunks.size():
            self._lastEventSize = self._chunks.size()
            self.currentSizeChanged.emit(self._lastEventSize)

    def resizeEvent(self, event: QResizeEvent):
        """Handle resize events"""
        if self._dynamicBytesPerLine:
            pxFixGaps = 0

            if self._addressArea:
                pxFixGaps = self.addressWidth() * self._pxCharWidth + 2 * self._pxAreaMargin

            pxFixGaps += 2 * self._pxAreaMargin

            if self._asciiArea:
                pxFixGaps += 2 * self._pxAreaMargin

            charWidth = (self.viewport().width() - pxFixGaps) // self._pxCharWidth + 1
            self.setBytesPerLine(max(charWidth // (4 if self._asciiArea else 3), 1))

        self._adjust()

    def focusNextPrevChild(self, next: bool) -> bool:
        """Handle tab focus"""
        if self._addressArea:
            if (next and self._editAreaIsAscii) or (not next and not self._editAreaIsAscii):
                return super().focusNextPrevChild(next)
            else:
                return False
        else:
            return super().focusNextPrevChild(next)

    # Private selection methods

    def _resetSelection(self, pos: int = None):
        """Reset selection"""
        if pos is None:
            self._bSelectionBegin = 0
            self._bSelectionEnd = 0
        else:
            pos = pos // 2
            if pos < 0:
                pos = 0
            if pos > self._chunks.size():
                pos = self._chunks.size()

            self._bSelectionBegin = pos
            self._bSelectionEnd = pos

        self._colorManager.selection().setRange(self._bSelectionBegin, self._bSelectionEnd)

    def _setSelection(self, pos: int):
        """Set selection end"""
        pos = pos // 2
        if pos < 0:
            pos = 0
        if pos > self._chunks.size():
            pos = self._chunks.size()

        if pos > self._bSelectionBegin:
            self._bSelectionEnd = pos
        else:
            self._bSelectionBegin = pos

        self._colorManager.selection().setRange(self._bSelectionBegin, self._bSelectionEnd)

    def _getSelectionBegin(self) -> int:
        """Get selection begin"""
        return self._bSelectionBegin

    def _getSelectionEnd(self) -> int:
        """Get selection end"""
        return self._bSelectionEnd

    # Private utility methods

    def _init(self):
        """Initialize editor state"""
        self._undoStack.clear()
        self.setAddressOffset(0)
        self._resetSelection(0)
        self.setCursorPosition(0)
        self.verticalScrollBar().setValue(0)
        self._modified = False

    def _adjust(self):
        """Recalculate pixel positions and scrollbars"""
        # Recalculate graphics
        if self._addressArea:
            self._addrDigits = self.addressWidth()
            self._pxPosHexX = self._pxAreaMargin + self._addrDigits * self._pxCharWidth + 2 * self._pxAreaMargin
        else:
            self._pxPosHexX = self._pxAreaMargin

        self._pxPosAdrX = self._pxAreaMargin
        self._pxPosAsciiX = self._pxPosHexX + self._hexCharsInLine * self._pxCharWidth + 2 * self._pxAreaMargin

        # Set horizontal scrollbar
        pxWidth = self._pxPosAsciiX
        if self._asciiArea:
            pxWidth += self._bytesPerLine * self._pxCharWidth

        self.horizontalScrollBar().setRange(0, max(0, pxWidth - self.viewport().width()))
        self.horizontalScrollBar().setPageStep(self.viewport().width())

        # Set vertical scrollbar
        self._rowsShown = (self.viewport().height() - 4) // self._pxCharHeight
        lineCount = self._chunks.size() // self._bytesPerLine + 1
        self.verticalScrollBar().setRange(0, max(0, lineCount - self._rowsShown))
        self.verticalScrollBar().setPageStep(max(1, self._rowsShown))

        value = self.verticalScrollBar().value()
        self._bPosFirst = value * self._bytesPerLine
        self._bPosLast = self._bPosFirst + (self._rowsShown * self._bytesPerLine) - 1

        if self._bPosLast >= self._chunks.size():
            self._bPosLast = self._chunks.size() - 1

        self._readBuffers()
        self.setCursorPosition(self._cursorPosition)

    def _dataChangedPrivate(self, idx: int = 0):
        """Handle data changed from undo stack"""
        self._modified = self._undoStack.index() != 0
        self._adjust()
        self.dataChanged.emit()

    def _refresh(self):
        """Refresh view"""
        self.ensureVisible()
        self._readBuffers()

    def _readBuffers(self):
        """Read data buffers for display"""
        self._markedShown = bytearray()
        self._dataShown = self._chunks.data(
            self._bPosFirst, self._bPosLast - self._bPosFirst + self._bytesPerLine + 1, self._markedShown
        )
        self._hexDataShown = bytearray(bytes(self._dataShown).hex().encode("ascii"))

    def _toReadable(self, ba: bytearray) -> str:
        """Convert byte array to readable format"""
        result = []

        for i in range(0, len(ba), 16):
            addrStr = f"{self._addressOffset + i:0{self.addressWidth()}x}"
            hexStr = ""
            ascStr = ""

            for j in range(16):
                if (i + j) < len(ba):
                    hexStr += f" {ba[i+j]:02x}"
                    ch = ba[i + j]
                    if ch < 0x20 or ch > 0x7E:
                        ch = ord(".")
                    ascStr += chr(ch)

            result.append(f"{addrStr} {hexStr:<48}  {ascStr:<17}")

        return "\n".join(result)

    def _updateCursor(self):
        """Update cursor blink state"""
        self._blink = not self._blink
        self.viewport().update(self._cursorRect)
