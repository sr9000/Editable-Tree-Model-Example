from typing import Optional

from PySide6.QtCore import QBuffer, QIODevice, QObject

NORMAL = 0
HIGHLIGHTED = 1

BUFFER_SIZE = 0x10000
CHUNK_SIZE = 0x1000
READ_CHUNK_MASK = 0xFFFFFFFFFFFFF000


class Chunk:
    def __init__(self):
        self.data = bytearray()
        self.dataChanged = bytearray()
        self.absPos = 0


class Chunks(QObject):
    """Storage backend for QHexEdit"""

    def __init__(self, parent=None, ioDevice: Optional[QIODevice] = None):
        super().__init__(parent)
        self._ioDevice: Optional[QIODevice] = None
        self._pos = 0
        self._size = 0
        self._chunks: list[Chunk] = []

        if ioDevice is None:
            buf = QBuffer(self)
            self.setIODevice(buf)
        else:
            self.setIODevice(ioDevice)

    def setIODevice(self, ioDevice: QIODevice) -> bool:
        """Set the IO device for reading data"""
        self._ioDevice = ioDevice
        ok = self._ioDevice.open(QIODevice.OpenModeFlag.ReadOnly)
        if ok:
            self._size = self._ioDevice.size()
            self._ioDevice.close()
        else:
            # Fallback to empty buffer
            buf = QBuffer(self)
            self._ioDevice = buf
            self._size = 0

        self._chunks.clear()
        self._pos = 0
        return ok

    def data(self, pos: int = 0, maxSize: int = -1, highlighted: Optional[bytearray] = None) -> bytearray:
        """Get data from chunks"""
        ioDelta = 0
        chunkIdx = 0
        buffer = bytearray()

        if highlighted is not None:
            highlighted.clear()

        if pos >= self._size:
            return buffer

        if maxSize < 0:
            maxSize = self._size
        elif pos + maxSize > self._size:
            maxSize = self._size - pos

        self._ioDevice.open(QIODevice.OpenModeFlag.ReadOnly)

        while maxSize > 0:
            chunk = Chunk()
            chunk.absPos = 2**63 - 1  # LLONG_MAX
            chunksLoopOngoing = True

            while chunkIdx < len(self._chunks) and chunksLoopOngoing:
                chunk = self._chunks[chunkIdx]
                if chunk.absPos > pos:
                    chunksLoopOngoing = False
                else:
                    chunkIdx += 1
                    chunkOfs = pos - chunk.absPos

                    if maxSize > (len(chunk.data) - chunkOfs):
                        count = len(chunk.data) - chunkOfs
                        ioDelta += CHUNK_SIZE - len(chunk.data)
                    else:
                        count = maxSize

                    if count > 0:
                        buffer.extend(chunk.data[chunkOfs : chunkOfs + count])
                        maxSize -= count
                        pos += count
                        if highlighted is not None:
                            highlighted.extend(chunk.dataChanged[chunkOfs : chunkOfs + count])

            if maxSize > 0 and pos < chunk.absPos:
                # Read from original source
                if (chunk.absPos - pos) > maxSize:
                    byteCount = maxSize
                else:
                    byteCount = chunk.absPos - pos

                maxSize -= byteCount
                self._ioDevice.seek(pos + ioDelta)
                # Ensure we extend with Python bytes to match QByteArray semantics
                _qba = self._ioDevice.read(byteCount)
                readBuffer = _qba.data() if hasattr(_qba, "data") else bytes(_qba)
                buffer.extend(readBuffer)
                if highlighted is not None:
                    highlighted.extend(bytearray([NORMAL] * len(readBuffer)))
                pos += len(readBuffer)

        self._ioDevice.close()
        return buffer

    def write(self, iODevice: QIODevice, pos: int = 0, count: int = -1) -> bool:
        """Write data to IO device"""
        if count == -1:
            count = self._size

        ok = iODevice.open(QIODevice.OpenModeFlag.WriteOnly)
        if ok:
            idx = pos
            while idx < count:
                ba = self.data(idx, BUFFER_SIZE)
                # Convert to bytes for PySide6 QIODevice compatibility
                iODevice.write(bytes(ba))
                idx += BUFFER_SIZE
            iODevice.close()
        return ok

    def setDataChanged(self, pos: int, dataChanged: bool):
        """Mark data as changed at position"""
        if pos < 0 or pos >= self._size:
            return

        chunkIdx = self._getChunkIndex(pos)
        posInBa = pos - self._chunks[chunkIdx].absPos
        self._chunks[chunkIdx].dataChanged[posInBa] = int(dataChanged)

    def dataChanged(self, pos: int) -> bool:
        """Check if data at position is changed"""
        for chunk in self._chunks:
            if pos >= chunk.absPos and pos < (chunk.absPos + len(chunk.dataChanged)):
                return bool(chunk.dataChanged[pos - chunk.absPos])
        return False

    def indexOf(self, ba: bytes, from_pos: int) -> int:
        """Find first occurrence of byte array"""
        result = -1
        pos = from_pos

        while pos < self._size and result < 0:
            buffer = bytes(self.data(pos, BUFFER_SIZE + len(ba) - 1))
            findPos = buffer.find(ba)
            if findPos >= 0:
                result = pos + findPos
            pos += BUFFER_SIZE

        return result

    def lastIndexOf(self, ba: bytes, from_pos: int) -> int:
        """Find last occurrence of byte array"""
        result = -1
        pos = from_pos

        while pos > 0 and result < 0:
            sPos = pos - BUFFER_SIZE - len(ba) + 1
            if sPos < 0:
                sPos = 0

            buffer = bytes(self.data(sPos, pos - sPos))
            findPos = buffer.rfind(ba)
            if findPos >= 0:
                result = sPos + findPos
            pos -= BUFFER_SIZE

        return result

    def insert(self, pos: int, b: int) -> bool:
        """Insert byte at position"""
        if pos < 0 or pos > self._size:
            return False

        if pos == self._size:
            # Avoid negative index when file is empty
            chunkIdx = self._getChunkIndex(pos - 1 if self._size > 0 else 0)
        else:
            chunkIdx = self._getChunkIndex(pos)

        posInBa = pos - self._chunks[chunkIdx].absPos
        self._chunks[chunkIdx].data.insert(posInBa, b)
        self._chunks[chunkIdx].dataChanged.insert(posInBa, 1)

        for idx in range(chunkIdx + 1, len(self._chunks)):
            self._chunks[idx].absPos += 1

        self._size += 1
        self._pos = pos
        return True

    def overwrite(self, pos: int, b: int) -> bool:
        """Overwrite byte at position"""
        if pos < 0 or pos >= self._size:
            return False

        chunkIdx = self._getChunkIndex(pos)
        posInBa = pos - self._chunks[chunkIdx].absPos
        self._chunks[chunkIdx].data[posInBa] = b
        self._chunks[chunkIdx].dataChanged[posInBa] = 1
        self._pos = pos
        return True

    def removeAt(self, pos: int) -> bool:
        """Remove byte at position"""
        if pos < 0 or pos >= self._size:
            return False

        chunkIdx = self._getChunkIndex(pos)
        posInBa = pos - self._chunks[chunkIdx].absPos
        del self._chunks[chunkIdx].data[posInBa]
        del self._chunks[chunkIdx].dataChanged[posInBa]

        for idx in range(chunkIdx + 1, len(self._chunks)):
            self._chunks[idx].absPos -= 1

        self._size -= 1
        self._pos = pos
        return True

    def __getitem__(self, pos: int) -> int:
        """Get byte at position"""
        return self.data(pos, 1)[0]

    def pos(self) -> int:
        """Get current position"""
        return self._pos

    def size(self) -> int:
        """Get total size"""
        return self._size

    def _getChunkIndex(self, absPos: int) -> int:
        """Get or create chunk index for absolute position"""
        foundIdx = -1
        insertIdx = 0
        ioDelta = 0

        for idx in range(len(self._chunks)):
            chunk = self._chunks[idx]
            if absPos >= chunk.absPos and absPos < (chunk.absPos + len(chunk.data)):
                foundIdx = idx
                break

            if absPos < chunk.absPos:
                insertIdx = idx
                break

            ioDelta += len(chunk.data) - CHUNK_SIZE
            insertIdx = idx + 1

        if foundIdx == -1:
            # Create new chunk
            newChunk = Chunk()
            readAbsPos = absPos - ioDelta
            if readAbsPos < 0:
                readAbsPos = 0
            readPos = readAbsPos & READ_CHUNK_MASK

            self._ioDevice.open(QIODevice.OpenModeFlag.ReadOnly)
            self._ioDevice.seek(readPos)
            _qba = self._ioDevice.read(CHUNK_SIZE)
            newChunk.data = bytearray(_qba.data() if hasattr(_qba, "data") else bytes(_qba))
            self._ioDevice.close()

            # Ensure non-negative absolute position when creating first chunk
            baseAbs = absPos if absPos >= 0 else 0
            newChunk.absPos = baseAbs - (readAbsPos - readPos)
            newChunk.dataChanged = bytearray([0] * len(newChunk.data))
            self._chunks.insert(insertIdx, newChunk)
            foundIdx = insertIdx

        return foundIdx
