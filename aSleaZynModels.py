from PyQt5.QtCore import QAbstractListModel, Qt, QModelIndex
from copy import deepcopy

class TrackModel(QAbstractListModel):

    def __init__ (self, *args, **kwargs):
        super(TrackModel, self).__init__(*args, **kwargs)
        self.tracks = []

    def data(self, index, role):
        i = index.row()
        if role == Qt.DisplayRole:
            track = self.tracks[i]
            return f"{track['name']} ({track['synths'][track['current_synth']][2:]}, {round(track['par_norm'] * 100) if not track['mute'] else 'MUTE'}%)"

    def rowCount(self, index = None):
        return len(self.tracks)

    def removeRow(self, row, parent = QModelIndex()):
        self.beginRemoveRows(parent, row, row)
        self.tracks.remove(self.tracks[row])
        self.endRemoveRows()

    def cloneRow(self, row, parent = QModelIndex()):
        self.beginInsertRows(parent, row, row)
        self.tracks.insert(row, deepcopy(self.tracks[row]))
        self.endInsertRows()

    def setSynthList(self, synths):
        for track in self.tracks:
            track['synths'] = synths

class ModuleModel(QAbstractListModel):

    def __init__ (self, *args, **kwargs):
        super(ModuleModel, self).__init__(*args, **kwargs)
        self.modules = []

    def setModules(self, modules):
        self.modules = modules
        self.layoutChanged.emit()

    def data(self, index, role):
        i = index.row()
        module = self.modules[i]
        if role == Qt.DisplayRole:
            return f"{module['pattern']['name']} @ {module['mod_on']:.0f}..{module['mod_on'] + module['pattern']['length']:.0f} ({module['transpose']})"

    def rowCount(self, index = None):
        return len(self.modules)


class PatternModel(QAbstractListModel):

    def __init__ (self, *args, **kwargs):
        super(PatternModel, self).__init__(*args, **kwargs)
        self.patterns = []

    def data(self, index, role):
        i = index.row()
        if role == Qt.DisplayRole:
            pattern = self.patterns[i]
            return f"{pattern['name']} [{pattern['length']}] ({len(pattern['notes'])} Notes)"

    def rowCount(self, index = None):
        return len(self.patterns)


class NoteModel(QAbstractListModel):

    #referenz: C0 = pitch_note 0
    keys = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

    def __init__ (self, *args, **kwargs):
        super(NoteModel, self).__init__(*args, **kwargs)
        self.notes = []

    def setNotes(self, notes):
        self.notes = notes
        self.layoutChanged.emit()

    def data(self, index, role):
        i = index.row()
        if role == Qt.DisplayRole:
            note = self.notes[i]
            key = self.keys[int(note['note_pitch']) % len(self.keys)]
            octave = int(note['note_pitch']) // 12
            return f"{key}{octave} [{note['note_on']}, {note['note_off']}] ({note['note_vel']}, {note['note_pan']}, {note['note_slide']}, {note['note_aux']})"

    def rowCount(self, index = None):
        return len(self.notes)

