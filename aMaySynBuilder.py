from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt, QByteArray
from struct import pack, unpack
from itertools import accumulate
from copy import deepcopy
from os import path, mkdir
from scipy.io import wavfile
from math import ceil, sqrt
import datetime
import re
import numpy as np

from SFXGLWidget import SFXGLWidget
from ma2_synatize import *
from aMaySynClassPorts import *

class aMaySynBuilder:

    templateFile = "template.matzethemightyemperor"
    shaderHeader = '#version 130\nuniform float iTexSize;\nuniform float iBlockOffset;\nuniform float iSampleRate;\n\n'

    outdir = './out/'

    def __init__(self, parent, synFile = None, info = None, **kwargs):
        self.parent = parent
        self.synFile = synFile
        self.info = info

        self.useSequenceTexture = True # if this is True: ignore 'shader' completely and use [self.fragment_shader, self.sequence]

        self.MODE_debug = False
        self.MODE_headless = False
        self.MODE_renderwav = kwargs.pop('renderWAV') if 'renderWAV' in kwargs else False
        if self.MODE_renderwav:
            self.initWavOut()

        self.synths = None
        self.drumkit = None
        self.synatize_form_list = None
        self.synatize_main_list = None
        self.synatize_param_list = None
        self.last_synatized_forms = None
        self.stored_randoms = []
        if self.aMaySynFileExists():
            self.aMaySynatize()

        self.fragment_shader = None
        self.sequence = []

        # debug stuff
        self.extra_time_shift = 0

    def updateState(self, info = None, synFile = None, stored_randoms = None, extra_time_shift = None):
        if info is not None:
            self.info = info
        if synFile is not None:
            self.synFile = synFile
        if stored_randoms is not None:
            self.stored_randoms = stored_randoms
        if extra_time_shift is not None:
            self.extra_time_shift = extra_time_shift

    def initWavOut(self, outdir = None):
        self.MODE_renderwav = True
        if outdir is not None:
            self.outdir = outdir

        if not path.isdir('./' + self.outdir):
            mkdir(self.outdir)

    def aMaySynatize(self, synFile = None,  reshuffle_randoms = False):
        if synFile is not None:
            self.synFile = synFile
        if not self.aMaySynFileExists():
            print(f"Don't have a valid aMaySyn-File ({self.synFile}). No can't do.\n")
            raise FileNotFoundError

        # TODO: Exception Handling instead of just quitting!!
        self.synatize_form_list, self.synatize_main_list, drumkit, self.stored_randoms, self.synatize_param_list \
            = synatize(self.synFile, stored_randoms = self.stored_randoms, reshuffle_randoms = reshuffle_randoms)

        def_synths = ['D_Drums', 'G_GFX', '__None']
        self.synths = ['I_' + m['id'] for m in self.synatize_main_list if m['type']=='main']
        self.synths.extend(def_synths)

        def_drumkit = ['SideChn']
        self.drumkit = def_drumkit + drumkit

        # TODO: might also require some exception handling, we'll see
        _, _, _, _, self.last_synatized_forms = synatize_build(self.synatize_form_list, self.synatize_main_list, self.synatize_param_list, self.synths, self.drumkit)

    def aMaySynFileExists(self):
        return self.synFile is not None and path.exists(self.synFile)

##################################### REQUIRED FUNCTION PORTS ###########################################

    def getInfo(self, key):
        try:
            info = self.info[key]
        except:
            print("Tried to build GLSL without having provided all required information (BPM etc.). Call getInfo() beforehand!")
            raise ValueError
        else:
            return info

    def printIfDebug(self, *messages):
        if self.MODE_debug:
            print(*messages)

    def getWAVFileName(self, count):
        return './' + self.outdir + '/' + self.getInfo('title') + '_' + str(count) + '.wav'

    def getWAVFileCount(self):
        if not path.isdir('./' + self.outdir): return '001'
        count = 1
        while path.isfile(self.getWAVFileName(f'{count:03d}')): count += 1
        return f'{count:03d}'

    def getTimeOfBeat(self, beat, bpmlist = None):
        return round(self.getTimeOfBeat_raw(beat, bpmlist = self.getInfo('BPM') if bpmlist is None else ' '.join(bpmlist)), 4)

    def getTimeOfBeat_raw(self, beat, bpmlist):
        beat = float(beat)
        if(type(bpmlist) != str):
            return beat * 60./bpmlist

        bpmdict = {float(part.split(':')[0]): float(part.split(':')[1]) for part in bpmlist.split()}
        if beat < 0:
            return 0
        if len(bpmdict) == 1:
            return beat * 60./bpmdict[0]
        time = 0
        for b in range(len(bpmdict) - 1):
            last_B = [*bpmdict][b]
            next_B = [*bpmdict][b+1]
            if beat < next_B:
                return time + (beat - last_B) * 60./ bpmdict[last_B]
            else:
                time += (next_B - last_B) * 60./ bpmdict[last_B]
        return time + (beat - next_B) * 60./ bpmdict[next_B]


############################################### BUILD #####################################################

    def build(self, tracks, patterns, renderWAV = False):
        if not self.aMaySynFileExists():
            print(f"Tried to build GLSL without valid aMaySyn-File ({self.synFile}). No can't do.\n")
            raise FileNotFoundError

        offset = self.getInfo('B_offset')
        stop = self.getInfo('B_stop')
        reduced_tracks = []
        actually_used_patterns = []
        for track in tracks:
            t = decodeTrack(track)
            if t.modules and not t.mute:
                t.modules = [m for m in t.modules if m.getModuleOff() > offset and m.getModuleOn() < stop]
                if t.modules:
                    reduced_tracks.append(t)
                    actually_used_patterns += [m.pattern for m in t.modules if m.pattern not in actually_used_patterns]
        tracks = reduced_tracks
        patterns = actually_used_patterns

        if len(tracks) == 0:
            print("Nothing to play..!")
            return 'Empty track :P'

        #tracks = [t for t in self.tracks if t.modules and not t.mute]
        max_mod_off = min(max(t.getLastModuleOff() for t in tracks), self.getInfo('B_stop')) # TODO. this min() should be redundant, check again
        loop_mode = self.getInfo('loop')

        filename = self.getInfo('title') + '.glsl'

        print('\nUSE TRACKS: ', tracks, '\nUSE PATTERNS: ', patterns, '\n')

        # TODO: after several changes, I'm not sure whether this is now still required or makes any sense at all, even..!
        self.module_shift = offset
        if self.module_shift > 0:
            for part in self.getInfo('BPM').split():
                bpm_point = float(part.split(':')[0])
                if bpm_point <= self.module_shift:
                    bpm_list = ['0:' + part.split(':')[1]]
                else:
                    bpm_list.append(str(bpm_point - self.module_shift) + ':' + part.split(':')[1])
                print(part, self.module_shift, bpm_list)
        else:
            bpm_list = self.getInfo('BPM').split()

        if self.MODE_headless:
            loop_mode = 'full'

        track_sep = [0] + list(accumulate([len(t.modules) for t in tracks]))
        pattern_sep = [0] + list(accumulate([len(p.notes) for p in patterns]))

        print('BPM LIST:', bpm_list)

        nT  = str(len(tracks))
        nM  = str(track_sep[-1])
        nP  = str(len(patterns))
        nN  = str(pattern_sep[-1])

        gf = open(self.templateFile)
        glslcode = gf.read()
        gf.close()

        self.aMaySynatize(self.synFile)
        actually_used_synths = set(t.getSynthName() for t in tracks if not t.getSynthType() == '_')
        actually_used_drums = set(n.note_pitch for p in patterns if p.synth_type == 'D' for n in p.notes)

        if self.MODE_debug: print("ACTUALLY USED:", actually_used_synths, actually_used_drums)

        self.synatized_code_syn, self.synatized_code_drum, paramcode, filtercode, self.last_synatized_forms = \
            synatize_build(self.synatize_form_list, self.synatize_main_list, self.synatize_param_list, actually_used_synths, actually_used_drums)

        self.file_extra_information = ''
        if self.MODE_headless:
            print("ACTUALLY USED SYNTHS:", actually_used_synths)
            names_of_actually_used_drums = [self.drumkit[d] for d in actually_used_drums]
            print("ACTUALLY USED DRUMS:", names_of_actually_used_drums)
            if len(actually_used_drums) == 1:
                self.file_extra_information += names_of_actually_used_drums[0] + '_'

        # get release and predraw times
        syn_rel = []
        syn_pre = []
        drum_rel = [0]
        max_rel = 0
        max_drum_rel = 0
        if self.MODE_debug: print(self.synatize_main_list)
        for m in self.synatize_main_list:
            rel = float(m['release']) if 'release' in m else 0
            pre = float(m['predraw']) if 'predraw' in m else 0
            if m['type'] == 'main':
                syn_rel.append(rel)
                syn_pre.append(pre)
                if m['id'] in actually_used_synths:
                    max_rel = max(max_rel, rel)
            elif m['type'] == 'maindrum':
                drum_rel.append(rel)
                max_drum_rel = max(max_drum_rel, rel)

        syn_rel.append(max_drum_rel)
        syn_pre.append(0)

        nD = str(len(drum_rel)) # number of drums - not required right now, maybe we need to add something later
        drum_index = str(self.synths.index('D_Drums')+1)

        # get slide times
        syn_slide = []
        for m in self.synatize_main_list:
            if m['type'] == 'main':
                syn_slide.append((float(m['slidetime']) if 'slidetime' in m else 0))
        syn_slide.append(0) # because of drums

        defcode  = '#define NTRK ' + nT + '\n'
        defcode += '#define NMOD ' + nM + '\n'
        defcode += '#define NPTN ' + nP + '\n'
        defcode += '#define NNOT ' + nN + '\n'
        defcode += '#define NDRM ' + nD + '\n'

        # construct arrays for beat / time correspondence
        pos_B = [B for B in (float(part.split(':')[0]) for part in bpm_list) if B < max_mod_off] + [max_mod_off]
        pos_t = [self.getTimeOfBeat(B, bpm_list) for B in pos_B]
        pos_BPS = []
        pos_SPB = []
        for b in range(len(pos_B)-1):
            pos_BPS.append(round((pos_B[b+1] - pos_B[b]) / (pos_t[b+1] - pos_t[b]), 4))
            pos_SPB.append(round(1./pos_BPS[-1], 4))

        ntime = str(len(pos_B))
        ntime_1 = str(len(pos_B)-1)

        beatheader = '#define NTIME ' + ntime + '\n'
        beatheader += 'const float pos_B[' + ntime + '] = float[' + ntime + '](' + ','.join(map(GLfloat, pos_B)) + ');\n'
        beatheader += 'const float pos_t[' + ntime + '] = float[' + ntime + '](' + ','.join(map(GLfloat, pos_t)) + ');\n'
        beatheader += 'const float pos_BPS[' + ntime_1 + '] = float[' + ntime_1 + '](' + ','.join(map(GLfloat, pos_BPS)) + ');\n'
        beatheader += 'const float pos_SPB[' + ntime_1 + '] = float[' + ntime_1 + '](' + ','.join(map(GLfloat, pos_SPB)) + ');'

        self.song_length = self.getTimeOfBeat(max_mod_off, bpm_list)
        if loop_mode == 'full':
            self.song_length = self.getTimeOfBeat(max_mod_off + max_rel, bpm_list)

        time_offset = self.getTimeOfBeat(offset, bpm_list)
        self.song_length -= time_offset

        loopcode = ('time = mod(time, ' + GLfloat(self.song_length) + ');\n' + 4*' ') if loop_mode != 'none' else ''

        if offset != 0:
            loopcode += f'time += {GLfloat(time_offset)};\n    '
        if self.extra_time_shift > 0:
            loopcode += f'time += {GLfloat(self.extra_time_shift)};\n    '

        print("SONG LENGTH: ", self.song_length)

        print("START TEXTURE")

        fmt = '@e'
        tex = b''
        tex += b''.join(pack(fmt, float(s)) for s in track_sep)
        tex += b''.join(pack(fmt, float(t.getSynthIndex()+1)) for t in tracks)
        tex += b''.join(pack(fmt, float(t.getNorm())) for t in tracks)
        tex += b''.join(pack(fmt, float(syn_rel[t.getSynthIndex()])) for t in tracks)
        tex += b''.join(pack(fmt, float(syn_pre[t.getSynthIndex()])) for t in tracks)
        tex += b''.join(pack(fmt, float(syn_slide[t.getSynthIndex()])) for t in tracks)
        tex += b''.join(pack(fmt, float(m.mod_on)) for t in tracks for m in t.modules)
        tex += b''.join(pack(fmt, float(m.getModuleOff())) for t in tracks for m in t.modules)
        tex += b''.join(pack(fmt, float(patterns.index(m.pattern))) for t in tracks for m in t.modules)
        tex += b''.join(pack(fmt, float(m.transpose)) for t in tracks for m in t.modules)
        tex += b''.join(pack(fmt, float(s)) for s in pattern_sep)
        tex += b''.join(pack(fmt, float(n.note_on)) for p in patterns for n in p.notes)
        tex += b''.join(pack(fmt, float(n.note_off)) for p in patterns for n in p.notes)
        tex += b''.join(pack(fmt, float(n.note_pitch)) for p in patterns for n in p.notes)
        tex += b''.join(pack(fmt, float(n.note_pan * .01)) for p in patterns for n in p.notes)
        tex += b''.join(pack(fmt, float(n.note_vel * .01)) for p in patterns for n in p.notes)
        tex += b''.join(pack(fmt, float(n.note_slide)) for p in patterns for n in p.notes)
        tex += b''.join(pack(fmt, float(n.note_aux)) for p in patterns for n in p.notes)
        tex += b''.join(pack(fmt, float(d)) for d in drum_rel)

        while len(tex) % 4 != 0:
            tex += bytes(1)
        texlength = int(len(tex))

        tex_s = int(ceil(sqrt(float(texlength)/4.)))
        tex_n = int(ceil(texlength/2))

        # Generate output header file
        array = []
        arrayf = []
        array4 = []
        for i in range(int(ceil(texlength/2))):
            array += unpack('@H', tex[2*i:2*i+2])
            arrayf += unpack(fmt, tex[2*i:2*i+2])

        text = "// Generated by tx210 / aMaySyn (c) 2018 NR4&QM/Team210\n\n#ifndef SEQUENCE_H\n#define SEQUENCE_H\n\n"
        text += f"// Data:\n//{', '.join(str(val) for val in arrayf)}\n"
        text += f"const unsigned short sequence_texture[{tex_n}] = {{{','.join(str(val) for val in array)}}};\n"
        text += f"const int sequence_texture_size = {tex_s};"
        text += '\n#endif\n'

        self.sequence = tex

        # Write to file
        with open("sequence.h", "wt") as f:
            f.write(text)
            f.close()

        print("TEXTURE FILE WRITTEN (sequence.h)")

        glslcode = glslcode\
            .replace("//DEFCODE", defcode)\
            .replace("//SYNCODE", self.synatized_code_syn)\
            .replace("//DRUMSYNCODE", self.synatized_code_drum)\
            .replace("DRUM_INDEX", drum_index)\
            .replace("//PARAMCODE", paramcode)\
            .replace("//FILTERCODE",filtercode)\
            .replace("//LOOPCODE", loopcode)\
            .replace("//BEATHEADER", beatheader)\
            .replace("STEREO_DELAY", GLfloat(self.getInfo('stereo_delay')))\
            .replace("LEVEL_SYN", GLfloat(self.getInfo('level_syn')))\
            .replace("LEVEL_DRUM", GLfloat(self.getInfo('level_drum')))

        glslcode = glslcode.replace('e+00','').replace('-0.)', ')').replace('+0.)', ')')
        glslcode = self.purgeExpendables(glslcode)

        with open("template.textureheader") as f:
            texheadcode = f.read()
            f.close()

        glslcode_frag = '#version 130\n' + glslcode.replace("//TEXTUREHEADER", texheadcode)

        filename_frag = 'sfx.frag'

        with open(filename_frag, 'w') as out_file:
            out_file.write(glslcode_frag)

        print(f"GLSL CODE WRITTEN ({filename_frag}) -- NR4-compatible fragment shader")

        # for "standalone" version
        texcode = f"const float sequence_texture[{tex_n}] = float[{tex_n}]({','.join(map(GLfloat, arrayf))});\n"

        glslcode = self.shaderHeader + glslcode

        glslcode = glslcode.replace("//TEXCODE",texcode).replace('//TEXTUREHEADER', 'float rfloat(int off){return sequence_texture[off];}\n')

        with open(filename, "w") as out_file:
            out_file.write(glslcode)

        print("GLSL CODE WRITTEN (" + filename + ") - QM-compatible standalone fragment shader")

        self.fragment_shader = glslcode_frag

        return glslcode

    def purgeExpendables(self, code):
        chars_before = len(code)
        purged_code = ''

        while True:
            func_list = {}
            for i,l in enumerate(code.splitlines()):
                func_head = re.findall('(?<=float )\w*(?=[ ]*\(.*\))', l)
                if func_head:
                    func_list.update({func_head[0]:i})

            print(func_list)

            expendable = []
            self.printIfDebug("The following functions will be purged")
            for f in func_list.keys():
                #print(f, code.count(f), len(re.findall(f + '[ \n]*\(', code)))
                if len(re.findall(f + '[ \n]*\(', code)) == 1:
                    f_from = code.find('float '+f)
                    if f_from == -1: continue
                    f_iter = f_from
                    n_open = 0
                    n_closed = 0
                    while True:
                        n_open += int(code[f_iter] == '{')
                        n_closed += int(code[f_iter] == '}')
                        f_iter += 1
                        if n_open > 0 and n_closed == n_open: break

                    expendable.append(code[f_from:f_iter])
                    self.printIfDebug(f, 'line', func_list[f], '/', f_iter-f_from, 'chars')

            for e in expendable: code = code.replace(e + '\n', '')

            if code == purged_code:
                break
            else:
                purged_code = code
                self.printIfDebug('try to purge next iteration')

        purged_code = re.sub('\n[\n]*\n', '\n\n', purged_code)

        chars_after = len(purged_code)
        print('// total purge of', chars_before-chars_after, 'chars.')

        return purged_code


    def executeShader(self, shader, samplerate, texsize, renderWAV = False):
        if not shader:
            print("you need to build() some shader before executeShader(). shady boi...")
            return None

        # TODO: would be really nice: option to not re-shuffle the last throw of randoms, but export these to WAV on choice... TODOTODOTODOTODO!
        # TODO LATER: great plans -- live looping ability (how bout midi input?)
        if self.stored_randoms:
            timestamp = datetime.datetime.now().strftime('%Y/%m/%d %H:%M')[2:]
            countID = self.file_extra_information + (str(self.getWAVFileCount()) if renderWAV else '(unsaved)')
            with open(self.getInfo('title') + '.rnd', 'a') as of:
                of.write(timestamp + '\t' + countID + '\t' \
                                + '\t'.join((rnd['id'] + '=' + str(rnd['value'])) for rnd in self.stored_randoms if rnd['store']) + '\n')


        starttime = datetime.datetime.now()

        glwidget = SFXGLWidget(self.parent, duration = self.song_length, samplerate = samplerate, texsize = texsize)
        if self.useSequenceTexture and self.fragment_shader is not None:
            glwidget.setTextureFromSequence(self.sequence)
            glwidget.show()
            log = glwidget.computeShader(self.fragment_shader)
        else:
            glwidget.show()
            log = glwidget.computeShader(shader)

        print(log)
        self.music = glwidget.music
        self.fmusic = glwidget.floatmusic
        glwidget.hide()
        glwidget.destroy()

        if not self.music:
            print('dämmit. music is empty.')
            return None

        self.bytearray = QByteArray(self.music)

        endtime = datetime.datetime.now()
        el = endtime - starttime

        print("Execution time", str(el.total_seconds()) + 's')

        if renderWAV:
            floatmusic_L = []
            floatmusic_R = []
            for n, sample in enumerate(self.fmusic):
                if n % 2 == 0:
                    floatmusic_L.append(sample)
                else:
                    floatmusic_R.append(sample)
            floatmusic_stereo = np.transpose(np.array([floatmusic_L, floatmusic_R], dtype = np.float32))
            wavfile.write(self.getInfo('title') + '.wav', samplerate, floatmusic_stereo)


        if self.MODE_headless:
            QApplication.quit()

        return self.bytearray