from enum import Enum, auto


class DateTimeCategory(Enum):
    Date = auto()
    Time = auto()
    DateTime = auto()
    DateTimeWithTZ = auto()
    DateTimeUTC = auto()
