from PySide6.QtGui import QPen, QBrush, QColor, QPalette
from PySide6.QtWidgets import QApplication
from enum import Enum
from typing import Optional


class Area(Enum):
    """Enum for different display areas"""

    Address = 0
    Hex = 1
    Ascii = 2


class ColoredArea:
    """Manages color information for a specific area"""

    def __init__(self, *args):
        self._posStart = 0
        self._posEnd = 0
        self._fontColor = QPen(QColor.fromRgba(0))
        self._areaStyle = QBrush(QColor.fromRgba(0))

        if len(args) == 0:
            pass
        elif len(args) == 2:
            # ColoredArea(pen, background)
            self._fontColor = args[0]
            self._areaStyle = args[1]
        elif len(args) == 4:
            # ColoredArea(posStart, posEnd, pen, background)
            self._posStart = args[0]
            self._posEnd = args[1]
            self._fontColor = args[2]
            self._areaStyle = args[3]

    def fontPen(self) -> QPen:
        """Get font pen"""
        return self._fontColor

    def fontColor(self) -> QColor:
        """Get font color"""
        return self._fontColor.color()

    def setFontColor(self, color: QColor):
        """Set font color"""
        self._fontColor = QPen(color)

    def areaColor(self) -> QColor:
        """Get area background color"""
        return self._areaStyle.color()

    def areaStyle(self) -> QBrush:
        """Get area background style"""
        return self._areaStyle

    def setAreaColor(self, color: QColor):
        """Set area background color"""
        self._areaStyle.setColor(color)

    def setAreaStyle(self, background: QBrush):
        """Set area background style"""
        self._areaStyle = background

    def posStart(self) -> int:
        """Get start position"""
        return self._posStart

    def posEnd(self) -> int:
        """Get end position"""
        return self._posEnd

    def setRange(self, posStart: int, posEnd: int):
        """Set position range"""
        self._posStart = posStart
        self._posEnd = posEnd

    def clear(self):
        """Clear range"""
        self._posStart = 0
        self._posEnd = 0


class ColorManager:
    """Manages colors for all areas in QHexEdit"""

    def __init__(self):
        self._highlighting = ColoredArea()
        self._selection = ColoredArea()
        self._address = ColoredArea()
        self._hex = ColoredArea()
        self._ascii = ColoredArea()
        self._userAreas: list[ColoredArea] = []

        palette = QApplication.palette()
        self.setPalette(palette)

    def setPalette(self, palette: QPalette):
        """Set color palette"""
        self._selection = ColoredArea(QPen(palette.highlightedText().color()), palette.highlight())
        self._highlighting = ColoredArea(QPen(QColor.fromRgb(0, 0, 0)), QBrush(QColor(0xFF, 0xFF, 0x99)))
        self._address = ColoredArea(QPen(palette.windowText().color()), palette.alternateBase())
        self._hex = ColoredArea(QPen(palette.windowText().color()), palette.base())
        self._ascii = ColoredArea(QPen(palette.windowText().color()), palette.alternateBase())

    def markedArea(self, pos: int, area: Area, chunks) -> ColoredArea:
        """Get marked area at position (returns a copy)"""
        # Priority 1: selection
        if pos >= self._selection.posStart() and pos < self._selection.posEnd():
            return self._selection

        # Priority 2: highlighting (changed data)
        if chunks.dataChanged(pos):
            return self._highlighting

        # Priority 3: user defined areas
        for userArea in self._userAreas:
            if pos >= userArea.posStart() and pos < userArea.posEnd():
                return userArea

        # Nothing found -> standard colors
        return self.notMarked(area)

    def notMarked(self, area: Area) -> ColoredArea:
        """Get standard colors for area"""
        if area == Area.Address:
            return self._address
        elif area == Area.Ascii:
            return self._ascii
        elif area == Area.Hex:
            return self._hex
        return self._hex

    def selection(self) -> ColoredArea:
        """Get selection color area"""
        return self._selection

    def highlighting(self) -> ColoredArea:
        """Get highlighting color area"""
        return self._highlighting

    def addUserArea(self, posStart: int, posEnd: int, fontColor: QColor, areaStyle: QBrush):
        """Add user defined marking area"""
        userArea = ColoredArea(posStart, posEnd, QPen(fontColor), areaStyle)
        self._userAreas.append(userArea)

    def clearUserAreas(self):
        """Clear all user defined areas"""
        self._userAreas.clear()
