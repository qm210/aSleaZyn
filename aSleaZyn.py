#!/usr/bin/python3
# -*- coding: utf-8 -*-

###########################################################
#
#   aSleaZyn - a sleazy aMaySyn extension!
#   written, sadly, by QM / Team210 - he will deny this!
#   qm@z10.info
#
###########################################################

import sys
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import Qt, QStringListModel, QItemSelectionModel
from PyQt5.QtWidgets import QApplication, QMainWindow, QAbstractItemView, QFileDialog
from PyQt5.QtMultimedia import QAudioOutput, QAudioFormat, QAudioDeviceInfo, QAudio
from os import path
import json

from aSleaZynUI import Ui_MainWindow
from aSleaZynModels import TrackModel, ModuleModel, PatternModel, NoteModel
from aMaySynBuilder import aMaySynBuilder
from SFXGLWidget import SFXGLWidget

class SleaZynth(QMainWindow):

    autoSaveFile = 'auto.save'

    texsize = 512
    samplerate = 44100

    def __init__(self):
        QMainWindow.__init__(self)
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.show()

        self.initModelView()
        self.initSignals()

        self.initState()
        self.autoLoad()

        self.initAudio()

    def initSignals(self):
        self.ui.btnChooseFilename.clicked.connect(self.loadMayson)
        self.ui.btnImport.clicked.connect(self.importMayson)
        self.ui.btnExport.clicked.connect(self.exportChangedMayson)

        self.ui.editFilename.editingFinished.connect(self.updateStateFromUI)
        self.ui.editBPM.editingFinished.connect(self.updateStateFromUI)
        self.ui.spinBOffset.valueChanged.connect(self.updateStateFromUI)
        self.ui.spinBStop.valueChanged.connect(self.updateStateFromUI)

        self.ui.editTrackName.textChanged.connect(self.trackSetName)
        self.ui.spinTrackVolume.valueChanged.connect(self.trackSetVolume)
        self.ui.checkTrackMute.stateChanged.connect(self.trackSetMute)
        self.ui.spinModOn.valueChanged.connect(self.moduleSetModOn)
        self.ui.spinModTranspose.valueChanged.connect(self.moduleSetTranspose)
        self.ui.btnApplyPattern.clicked.connect(self.moduleSetPattern)
        self.ui.btnApplyNote.clicked.connect(self.noteApplyChanges)
        self.ui.btnTrackAdd.clicked.connect(self.placeholder)
        self.ui.btnTrackClone.clicked.connect(self.placeholder)
        self.ui.btnTrackDelete.clicked.connect(self.placeholder)

        self.ui.btnRenderModule.clicked.connect(self.renderModule)
        self.ui.btnRenderTrack.clicked.connect(self.renderTrack)
        self.ui.btnRenderSong.clicked.connect(self.renderSong)
        self.ui.btnStopPlayback.clicked.connect(self.stopPlayback)

        #model/view signals
        self.ui.trackList.selectionModel().currentChanged.connect(self.trackLoad)
        self.ui.patternCombox.currentIndexChanged.connect(self.patternLoad)
        self.ui.moduleList.selectionModel().currentChanged.connect(self.moduleLoad)
        self.ui.synthList.selectionModel().currentChanged.connect(self.trackSetSynth)
        self.ui.noteList.selectionModel().currentChanged.connect(self.noteLoad)

    def initModelView(self):
        self.trackModel = TrackModel()
        self.ui.trackList.setModel(self.trackModel)
        self.moduleModel = ModuleModel()
        self.ui.moduleList.setModel(self.moduleModel)
        self.patternModel = PatternModel()
        self.ui.patternCombox.setModel(self.patternModel)
        self.noteModel = NoteModel()
        self.ui.noteList.setModel(self.noteModel)
        self.synthModel = QStringListModel()
        self.ui.synthList.setModel(self.synthModel)
        self.drumModel = QStringListModel()
        self.ui.drumList.setModel(self.drumModel)

        # can do this in in qtDesigner? # do I need this at all?
        self.ui.trackList.setEditTriggers(QAbstractItemView.DoubleClicked)


    def initState(self):
        self.state = {}
        self.info = {}
        self.patterns = []
        self.synths = []
        self.drumkit = []

    def loadMayson(self):
        name, _ = QFileDialog.getOpenFileName(self, 'Load MAYSON file', '', 'aMaySyn export *.mayson(*.mayson)')
        if name == '':
            return
        self.state['maysonFile'] = name
        self.state['title'], self.state['synFile'] = self.getTitleAndSynFromMayson(name)
        self.autoSave()

    def importMayson(self):
        try:
            file = open(self.state['maysonFile'], 'r')
            maysonData = json.load(file)
            file.close()
        except FileNotFoundError:
            return

        self.info = maysonData['info']
        self.info.update({'title': self.state['title']})
        self.trackModel.tracks = maysonData['tracks']
        self.patternModel.patterns = maysonData['patterns']
        self.synthModel.setStringList(maysonData['synths'])
        self.drumModel.setStringList(maysonData['drumkit'])

        if self.trackModel.rowCount() > 0:
            self.selectIndex(self.ui.trackList, self.trackModel, 0)

        if self.noteModel.rowCount() > 0:
            self.selectIndex(self.ui.noteList, self.noteModel, 0)

        if self.synthModel.rowCount() > 0:
            self.selectIndex(self.ui.synthList, self.synthModel, 0)
        if self.drumModel.rowCount() > 0:
            self.selectIndex(self.ui.drumList, self.drumModel, 0)

        self.applyStateToUI()


    def exportChangedMayson(self):
        name, _ = QFileDialog.getSaveFileName(self, 'Export with Changes', self.state['maysonFile'], 'aMaySyn export *.mayson(*.mayson)')
        if name == '':
            return
        data = {
            'info': self.info,
            'tracks': self.trackModel.tracks,
            'patterns': self.patternModel.patterns,
            'synths': self.synthModel.stringList(),
            'drumkit': self.drumModel.stringList(),
        }
        file = open(name, 'w')
        json.dump(data, file)
        file.close()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.close()

    def closeEvent(self, event):
        QApplication.quit()

    def updateStateFromUI(self):
        self.state.update({'maysonFile': self.ui.editFilename.text()})
        title, synFile = self.getTitleAndSynFromMayson(self.state['maysonFile'])
        self.state.update({'synFile': synFile})
        self.state.update({'title': title})
        self.info['title'] = title
        self.info['BPM'] = self.ui.editBPM.text()
        self.info['B_offset'] = self.ui.spinBOffset.value()
        self.info['B_stop'] = self.ui.spinBStop.value()

    def applyStateToUI(self):
        self.ui.editFilename.setText(self.state['maysonFile'])

        # TODO: think about - do I want self.state['override']['BPM'] etc.??
        self.ui.editBPM.setText(self.info['BPM'])
        self.ui.spinBOffset.setValue(self.info['B_offset'])
        self.ui.spinBStop.setValue(self.info['B_stop'])

    def autoSave(self):
        file = open(self.autoSaveFile, 'w')
        json.dump(self.state, file)
        file.close()

    def autoLoad(self):
        try:
            file = open(self.autoSaveFile, 'r')
            self.state = json.load(file)
            file.close()
        except FileNotFoundError:
            pass

        if 'maysonFile' not in self.state or self.state['maysonFile'] == '':
            self.loadMayson()

        self.importMayson()

#################################### GENERAL HELPERS ###########################################

    def selectIndex(self, list, model, index):
        list.selectionModel().setCurrentIndex(model.createIndex(index, 0), QItemSelectionModel.SelectCurrent)

    def patternIndexOfName(self, name):
        patternNames = [p['name'] for p in self.patternModel.patterns]
        if name in patternNames:
            return patternNames.index(name)
        else:
            return None

    def getTitleAndSynFromMayson(self, maysonFile):
        synFile = '.'.join(maysonFile.split('.')[:-1]) + '.syn'
        title = '.'.join(path.basename(maysonFile).split('.')[:-1])
        return title, synFile

    def placeholder(self):
        print("FUNCTION NOT IMPLEMENTED. Sorrriiiiiiieee! (not sorry.)")

#################################### TRACK FUNCTIONALITY #######################################

    def track(self):
        return self.trackModel.tracks[self.trackIndex().row()]

    def trackIndex(self):
        return self.ui.trackList.currentIndex()

    def trackModelChanged(self):
        return self.trackModel.dataChanged.emit(self.trackIndex(), self.trackIndex())

    def trackLoad(self, currentIndex):
        cTrack = self.trackModel.tracks[currentIndex.row()]

        self.ui.editTrackName.setText(cTrack['name'])
        self.ui.spinTrackVolume.setValue(100 * cTrack['par_norm'])
        self.ui.checkTrackMute.setChecked(not cTrack['mute'])

        self.moduleModel.setModules(cTrack['modules'])
        if len(cTrack['modules']) > 0:
            self.selectIndex(self.ui.moduleList, self.moduleModel, cTrack['current_module'])
            self.moduleLoad()

    def trackSetName(self, name):
        self.track()['name'] = name
        self.trackModelChanged()

    def trackSetVolume(self, value):
        self.track()['par_norm'] = value * .01
        self.trackModelChanged()

    def trackSetMute(self, state):
        self.track()['mute'] = (state != Qt.Checked)
        self.trackModelChanged()

    def trackSetSynth(self, index):
        self.track()['current_synth'] = self.track()['synths'].index(self.synthModel.data(index, Qt.DisplayRole))
        self.trackModelChanged()

#################################### MODULE FUNCTIONALITY ######################################

    def module(self):
        return self.moduleModel.modules[self.moduleIndex().row()]

    def moduleIndex(self):
        return self.ui.moduleList.currentIndex()

    def moduleModelChanged(self):
        return self.moduleModel.dataChanged.emit(self.moduleIndex(), self.moduleIndex())

    def moduleLoad(self, currentIndex = None):
        if currentIndex is None:
            cModule = self.module()
        else:
            cModule = self.moduleModel.modules[currentIndex.row()]

        self.ui.patternCombox.setCurrentIndex(self.patternIndexOfName(cModule['pattern']['name']))
        self.ui.spinModOn.setValue(cModule['mod_on'])
        self.ui.spinModTranspose.setValue(cModule['transpose'])

    def moduleSetPattern(self):
        self.module()['pattern'] = self.pattern()
        self.moduleModelChanged()

    def moduleSetModOn(self, value):
        self.module()['mod_on'] = self.ui.spinModOn.value()
        self.moduleModelChanged()

    def moduleSetTranspose(self, value):
        self.module()['transpose'] = self.ui.spinModTranspose.value()
        self.moduleModelChanged()

#################################### PATTERN FUNCTIONALITY #####################################

    def pattern(self):
        return self.patternModel.patterns[self.patternIndex()]

    def patternIndex(self):
        return self.ui.patternCombox.currentIndex()

    def patternLoad(self, currentIndex):
        cPattern = self.patternModel.patterns[currentIndex]

        self.noteModel.setNotes(cPattern['notes'])

#################################### NOTE FUNCTIONALITY ########################################

    def note(self):
        return self.noteModel.notes[self.noteIndex().row()]

    def noteIndex(self):
        return self.ui.noteList.currentIndex()

    def noteModelChanged(self):
        return self.noteModel.dataChanged.emit(self.noteIndex(), self.noteIndex())

    def noteLoad(self, currentIndex):
        self.ui.editNote.setText(self.noteModel.data(currentIndex, Qt.DisplayRole))
        self.ui.editNote.setCursorPosition(0)

    def noteApplyChanges(self):
        self.placeholder()

######################################## SleaZYNTHesizer #######################################

    def initAudio(self):
        self.audioformat = QAudioFormat()
        self.audioformat.setSampleRate(self.samplerate)
        self.audioformat.setChannelCount(2)
        self.audioformat.setSampleSize(32)
        self.audioformat.setCodec('audio/pcm')
        self.audioformat.setByteOrder(QAudioFormat.LittleEndian)
        self.audioformat.setSampleType(QAudioFormat.Float)
        self.audiooutput = QAudioOutput(self.audioformat)
        self.audiooutput.setVolume(1.0)

    def stopPlayback(self):
        self.audiooutput.stop()

    def renderModule(self):
        self.placeholder() # TODO remove the onlyModule functionality from aMaySynBuilder and place it here!

    def renderTrack(self):
        self.render(aMaySynBuilder(self, [self.track()], self.patternModel.patterns, self.state['synFile'], self.info))

    def renderSong(self):
        self.render(aMaySynBuilder(self, self.trackModel.tracks, self.patternModel.patterns, self.state['synFile'], self.info))

    def render(self, amaysyn):
        shader = amaysyn.build()
        self.ui.codeEditor.clear()
        self.ui.codeEditor.insertPlainText(shader.replace(4*' ','\t').replace(3*' ', '\t'))
        self.ui.codeEditor.ensureCursorVisible()

        amaysyn.executeShader(shader, self.audiooutput, self.samplerate, self.texsize)


################################################################################################


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = SleaZynth()
    exitCode = app.exec_()
    # print('\n'.join(repr(w) for w in app.allWidgets()))
    sys.exit(exitCode)
