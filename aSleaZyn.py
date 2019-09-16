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
from PyQt5.QtCore import Qt, QStringListModel, QItemSelectionModel, QIODevice, QByteArray, QBuffer
from PyQt5.QtWidgets import QApplication, QMainWindow, QAbstractItemView, QFileDialog
from PyQt5.QtMultimedia import QAudioOutput, QAudioFormat, QAudioDeviceInfo, QAudio
from watchdog.observers import Observer
from os import path
from random import randint
from shutil import move
import json

from aSleaZynUI import Ui_MainWindow
from aSleaZynModels import TrackModel, ModuleModel, PatternModel, NoteModel
from aMaySynBuilder import aMaySynBuilder
from SFXGLWidget import SFXGLWidget
from FileModifiedHandler import FileModifiedHandler


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

        self.initAMaySyn()
        self.initAudio()


    def initSignals(self):
        self.ui.btnChooseFilename.clicked.connect(self.loadMayson)
        self.ui.btnImport.clicked.connect(self.importMayson)
        self.ui.btnExport.clicked.connect(self.exportChangedMayson)
        self.ui.checkAutoRender.clicked.connect(self.toggleAutoRender)

        self.ui.editFilename.editingFinished.connect(self.updateStateFromUI)
        self.ui.editBPM.editingFinished.connect(self.updateStateFromUI)
        self.ui.spinBOffset.valueChanged.connect(self.updateStateFromUI)
        self.ui.spinBStop.valueChanged.connect(self.updateStateFromUI)
        self.ui.btnApplyBPM.clicked.connect(self.placeholder)
        self.ui.btnApplyBPM.hide()

        self.ui.editTrackName.textChanged.connect(self.trackSetName)
        self.ui.spinTrackVolume.valueChanged.connect(self.trackSetVolume)
        self.ui.checkTrackMute.stateChanged.connect(self.trackSetMute)
        self.ui.spinModOn.valueChanged.connect(self.moduleSetModOn)
        self.ui.spinModTranspose.valueChanged.connect(self.moduleSetTranspose)
        self.ui.btnApplyPattern.clicked.connect(self.moduleSetPattern)
        self.ui.btnApplyNote.clicked.connect(self.noteApplyChanges)
        self.ui.btnTrackClone.clicked.connect(self.trackClone)
        self.ui.btnTrackDelete.clicked.connect(self.trackDelete)
        self.ui.btnRandomSynth.clicked.connect(self.trackSetRandomSynth)
        self.ui.btnRandomizeSynth.clicked.connect(self.synthRandomize)
        self.ui.btnSaveSynth.clicked.connect(self.synthHardClone)
        self.ui.btnApplySynthName.clicked.connect(self.synthChangeName)
        self.ui.btnReloadSyn.clicked.connect(self.loadSynthsFromSynFile)

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


    def initState(self):
        self.state = {'maysonFile': '', 'autoRender': False}
        self.info = {}
        self.patterns = []
        self.synths = []
        self.drumkit = []
        self.amaysyn = None
        self.fileObserver = None

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
            print(".mayson file could not be loaded. check that it exists, and/or choose another one via '...' button.")
            return

        self.info = maysonData['info']
        self.info.update({'title': self.state['title']})
        self.trackModel.tracks = maysonData['tracks']
        self.patternModel.patterns = maysonData['patterns']
        self.synthModel.setStringList(maysonData['synths'])
        self.drumModel.setStringList(maysonData['drumkit'])

        self.trackModel.layoutChanged.emit()
        if self.trackModel.rowCount() > 0:
            self.selectIndex(self.ui.trackList, self.trackModel, 0)

        self.synthModel.layoutChanged.emit()
        if self.noteModel.rowCount() > 0:
            self.selectIndex(self.ui.noteList, self.noteModel, 0)

        self.drumModel.layoutChanged.emit()
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
        if self.amaysyn is not None:
            self.amaysyn.updateState(info = self.info, synFile = synFile)

    def applyStateToUI(self):
        self.ui.editFilename.setText(self.state['maysonFile'])
        # TODO: think about - do I want self.state['override']['BPM'] etc.??
        self.ui.editBPM.setText(self.info['BPM'])
        self.ui.spinBOffset.setValue(self.info['B_offset'])
        self.ui.spinBStop.setValue(self.info['B_stop'])
        self.ui.checkAutoRender.setChecked(self.state['autoRender'])

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
        if 'autoRender' in self.state:
            self.toggleAutoRender(self.state['autoRender'])

        self.importMayson()


    def toggleAutoRender(self, checked):
        self.state['autoRender'] = checked
        self.autoSave()

        if self.fileObserver is not None:
            self.fileObserver.stop()
            self.fileObserver.join()
            self.fileObserver = None

        if checked:
            file = self.state['maysonFile']
            eventHandler = FileModifiedHandler(file)
            eventHandler.fileChanged.connect(self.importAndRender)
            self.fileObserver = Observer()
            self.fileObserver.schedule(eventHandler, path=path.dirname(file), recursive = False)
            self.fileObserver.start()

    def importAndRender(self):
        self.importMayson()
        if self.amaysyn is not None:
            self.amaysyn.updateState(info = self.info)
        self.renderSong() # TODO: store whether last rendered button was "Module", "Track" or "Song" --> do this again :)


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
        self.trackModel.dataChanged.emit(self.trackIndex(), self.trackIndex())

    def trackLoad(self, currentIndex):
        cTrack = self.trackModel.tracks[currentIndex.row()]
        self.ui.editTrackName.setText(cTrack['name'])
        self.ui.spinTrackVolume.setValue(100 * cTrack['par_norm'])
        self.ui.checkTrackMute.setChecked(not cTrack['mute'])
        self.moduleModel.setModules(cTrack['modules'])
        if len(cTrack['modules']) > 0:
            self.selectIndex(self.ui.moduleList, self.moduleModel, cTrack['current_module'])
            self.moduleLoad()
        self.selectIndex(self.ui.synthList, self.synthModel, cTrack['current_synth'])

    def trackClone(self):
        self.trackModel.cloneRow(self.trackIndex().row())

    def trackDelete(self):
        self.trackModel.removeRow(self.trackIndex().row())

    def trackSetName(self, name):
        self.track()['name'] = name
        self.trackModelChanged()

    def trackSetVolume(self, value):
        self.track()['par_norm'] = round(value * .01, 3)
        self.trackModelChanged()

    def trackSetMute(self, state):
        self.track()['mute'] = (state != Qt.Checked)
        self.trackModelChanged()

    def trackSetSynth(self, index):
        self.track()['current_synth'] = self.synthModel.stringList().index(self.synthModel.data(index, Qt.DisplayRole)) #self.track()['synths'].index(self.synthModel.data(index, Qt.DisplayRole))
        self.ui.editSynthName.setText(self.synthName())
        self.trackModelChanged()

    def trackSetRandomSynth(self):
        randomIndex = self.synthModel.createIndex(randint(0, len(self.instrumentSynths()) - 1), 0)
        self.trackSetSynth(randomIndex)

#################################### MODULE FUNCTIONALITY ######################################

    def module(self):
        return self.moduleModel.modules[self.moduleIndex().row()]

    def moduleIndex(self):
        return self.ui.moduleList.currentIndex()

    def moduleModelChanged(self):
        self.moduleModel.dataChanged.emit(self.moduleIndex(), self.moduleIndex())

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
        self.noteModel.dataChanged.emit(self.noteIndex(), self.noteIndex())

    def noteLoad(self, currentIndex):
        self.ui.editNote.setText(self.noteModel.data(currentIndex, Qt.DisplayRole))
        self.ui.editNote.setCursorPosition(0)

    def noteApplyChanges(self):
        self.placeholder()

###################################### SYNTH FUNCTIONALITY #####################################

    def synth(self):
        return self.synthModel.data(self.ui.synthList.currentIndex(), Qt.DisplayRole)

    def synthName(self):
        return self.synth()[2:]

    def instrumentSynths(self):
        return [I_synth for I_synth in self.synthModel.stringList() if I_synth[0] == 'I']

    def synthRandomize(self):
        self.amaysyn.aMaySynatize(reshuffle_randoms = True)

    def synthHardClone(self):
        # in aSleaZyn, cloning is only implemented for synths (not drums), because the idea is to design your drums via Drumatize
        count = 0
        oldID = self.synthName()
        synths = self.instrumentSynths()
        while True:
            formID = oldID + '.' + str(count)
            print("TRYING", formID, synths)
            if 'I_' + formID not in synths: break
            count += 1

        try:
            formTemplate = next(form for form in self.amaysyn.last_synatized_forms if form['id'] == oldID)
            formType = formTemplate['type']
            formMode = formTemplate['mode']
            formBody = ' '.join(key + '=' + formTemplate[key] for key in formTemplate if key not in  ['type', 'id', 'mode'])
            if formMode: formBody += ' mode=' + ','.join(formMode)
        except StopIteration:
            print("Current synth is not compiled yet. Do so and try again.")
            return
        except:
            print("could not CLONE HARD:", formID, formTemplate)
            raise
        else:
            with open(self.state['synFile'], mode='a') as filehandle:
                filehandle.write('\n' + formType + 4*' ' + formID + 4*' ' + formBody)
            self.loadSynthsFromSynthFile()

    def synthChangeName(self):
        if self.synth()[0] != 'I':
            print("Nah. Select an instrument synth (I_blabloo)")
            return
        newID = self.ui.editSynthName.text()
        if newID == '':
            return
        formID = self.synthName()
        tmpFile = self.state['synFile'] + '.tmp'
        move(self.state['synFile'], tmpFile)
        with open(tmpFile, mode='r') as tmp_handle:
            with open(self.state['synFile'], mode='w') as new_handle:
                for line in tmp_handle.readlines():
                    lineparse = line.split()
                    if len(lineparse)>2 and lineparse[0] in ['main', 'maindrum'] and lineparse[1] == formID:
                        new_handle.write(line.replace(' '+formID+' ', ' '+newID+' '))
                    else:
                        new_handle.write(line)
        self.loadSynthsFromSynFile()

    def loadSynthsFromSynFile(self):
        self.amaysyn.aMaySynatize()
        self.synthModel.setStringList(self.amaysyn.synths)
        self.synthModel.dataChanged.emit(self.synthModel.createIndex(0, 0), self.synthModel.createIndex(self.synthModel.rowCount(), 0))
        self.drumModel.setStringList(self.amaysyn.drumkit)
        self.drumModel.dataChanged.emit(self.drumModel.createIndex(0, 0), self.drumModel.createIndex(self.drumModel.rowCount(), 0))
        self.trackModel.setSynthList(self.amaysyn.synths)
        self.trackModelChanged()

# TODO: function to change drumkit order / assignment?

######################################## SleaZYNTHesizer #######################################

    def initAMaySyn(self):
        self.amaysyn = aMaySynBuilder(self, self.state['synFile'], self.info)

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
        self.placeholder()
        #shader = self.amaysyn.build(tracks = [self.track()], patterns = [self.module()['pattern']], onlyModule = self.module()) # module_shift = self.module()['mod_on']
        #self.executeShader(shader)

    def renderTrack(self):
        shader = self.amaysyn.build(tracks = [self.track()], patterns = self.patternModel.patterns)
        self.executeShader(shader)

    def renderSong(self):
        shader = self.amaysyn.build(tracks = self.trackModel.tracks, patterns = self.patternModel.patterns)
        self.executeShader(shader)

    def executeShader(self, shader):
        self.ui.codeEditor.clear()
        self.ui.codeEditor.insertPlainText(shader.replace(4*' ','\t').replace(3*' ', '\t'))
        self.ui.codeEditor.ensureCursorVisible()

        self.bytearray = self.amaysyn.executeShader(shader, self.samplerate, self.texsize)
        self.audiobuffer = QBuffer(self.bytearray)
        self.audiobuffer.open(QIODevice.ReadOnly)
        self.audiooutput.stop()
        self.audiooutput.start(self.audiobuffer)



################################################################################################


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = SleaZynth()
    exitCode = app.exec_()
    # print('\n'.join(repr(w) for w in app.allWidgets()))
    sys.exit(exitCode)
