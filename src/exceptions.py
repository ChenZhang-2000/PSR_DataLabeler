
class FileLabelException(Exception):
    pass


class FileNotCSVException(FileLabelException):
    pass


class FileDoesNotExist(FileLabelException):
    pass


class InputNotString(FileLabelException):
    pass


class EmptyInput(FileLabelException):
    pass


class TimeFormatIncorrect(FileLabelException):
    pass


class StartTimeFormatIncorrect(TimeFormatIncorrect):
    pass


class TimeZoneCodeFormatIncorrect(TimeFormatIncorrect):
    pass
