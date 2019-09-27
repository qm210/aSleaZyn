from PyQt5.QtCore import QAbstractListModel, Qt, QModelIndex, pyqtSignal
from copy import deepcopy

class TrackModel(QAbstractListModel):

    def __init__ (self, *args, **kwargs):
        super(TrackModel, self).__init__(*args, **kwargs)
        self.tracks = []

    def setTracks(self, tracks):
        self.beginRemoveRows(QModelIndex(), self.createIndex(0,0).row(), self.createIndex(self.rowCount(),0).row())
        self.tracks = tracks
        self.layoutChanged.emit()
        self.endRemoveRows()

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

    def updateModulesWithChangedPattern(self, pattern):
        for track in self.tracks:
            for module in track['modules']:
                if module['pattern']['name'] == pattern['name']:
                    module['pattern'] = pattern # deepcopy(pattern)

class ModuleModel(QAbstractListModel):

    def __init__ (self, *args, **kwargs):
        super(ModuleModel, self).__init__(*args, **kwargs)
        self.modules = []

    def setModules(self, modules):
        self.beginRemoveRows(QModelIndex(), self.createIndex(0,0).row(), self.createIndex(self.rowCount(),0).row())
        self.modules = modules
        self.layoutChanged.emit()
        self.endRemoveRows()

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

    def setPatterns(self, patterns):
        self.beginRemoveRows(QModelIndex(), self.createIndex(0,0).row(), self.createIndex(self.rowCount(),0).row())
        self.patterns = patterns
        self.layoutChanged.emit()
        self.endRemoveRows()

    def data(self, index, role):
        i = index.row()
        if role == Qt.DisplayRole:
            pattern = self.patterns[i]
            return f"{pattern['name']} [{pattern['length']}] ({len(pattern['notes'])} Notes)"

    def rowCount(self, index = None):
        return len(self.patterns)


class NoteModel(QAbstractListModel):

    reloadNoteParameters = pyqtSignal(QModelIndex)

    #referenz: C0 = pitch_note 0
    keys = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

    def __init__ (self, *args, **kwargs):
        super(NoteModel, self).__init__(*args, **kwargs)
        self.notes = []
        self.drumkit = None

    def setNotes(self, notes):
        self.notes = notes
        self.layoutChanged.emit()

    def useDrumkit(self, drumkit = None):
        self.drumkit = drumkit

    def data(self, index, role):
        i = index.row()
        if role == Qt.DisplayRole:
            note = self.notes[i]
            if self.drumkit is None:
                key = self.keys[int(note['note_pitch']) % len(self.keys)]
                octave = int(note['note_pitch']) // 12
                return f"{key}{octave} [{note['note_on']}, {note['note_off']}] ({note['note_vel']}, {note['note_pan']}, {note['note_slide']}, {note['note_aux']})"
            else:
                drumname = self.drumkit[note['note_pitch']] if note['note_pitch'] < len(self.drumkit) else f"undef{note['note_pitch']}"
                return f"{drumname} [{note['note_on']}, {note['note_off']}] ({note['note_vel']}, {note['note_pan']}, {note['note_slide']}, {note['note_aux']})"

    def rowCount(self, index = None):
        return len(self.notes)

    def changeByString(self, index, parString):
        note = self.notes[index.row()]
        note_name = parString.split()[0]

        try:
            if self.drumkit is None:
                if parString[1] == '#':
                    key = self.keys.index(note_name[0:2])
                    oct = int(note_name[2:])
                else:
                    key = self.keys.index(note_name[0])
                    oct = int(note_name[1:])
                pitch = key + 12 * oct
            else:
                pitch = self.drumkit.index(note_name)

            beatStrings = parString.split('[')[1].split(']')[0].replace(' ','').split(',')
            detailStrings = parString.split('(')[1].split(')')[0].replace(' ','').split(',')

        except:
            print("NOTE PARAMETER STRING ERRONEOUS... ADHERE TO THE PATTERN (and valid note/drum names)!")
            #self.reloadNoteParameters.emit(index)
            return

        note['note_pitch'] = pitch
        note['note_on'] = float(beatStrings[0])
        note['note_off'] = float(beatStrings[1])
        note['note_vel'] = int(detailStrings[0])
        note['note_pan'] = int(detailStrings[1])
        note['note_slide'] = float(detailStrings[2])
        note['note_aux'] = float(detailStrings[2])

        self.dataChanged.emit(index, index)

    def changeDrumTo(self, index, drum):
        if drum is None or self.drumkit is None or not index.isValid():
            return
        if drum not in self.drumkit:
            print("weird. this drum seems not to be in the drumkit?", drum, self.drumkit)
            return
        print("set drum to", drum)
        self.notes[index.row()]['note_pitch'] = self.drumkit.index(drum)

        self.dataChanged.emit(index, index)
        self.reloadNoteParameters.emit(index)