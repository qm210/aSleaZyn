from PyQt5.QtCore import QObject, pyqtSignal
from watchdog.events import FileSystemEventHandler
from datetime import datetime, timedelta


class FileModifiedHandler(FileSystemEventHandler, QObject):

    fileChanged = pyqtSignal()

    def __init__(self, filename):
        super().__init__()
        self.filename = filename
        self.lastModTime = datetime.now()

    def on_modified(self, event):
        if event.src_path != self.filename:
            return

        if datetime.now() - self.lastModTime < timedelta(seconds = 1):
            return
        else:
            self.lastModTime = datetime.now()

        print(event.event_type, event.src_path, event.is_directory, self.filename)
        self.fileChanged.emit()