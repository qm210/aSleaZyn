from struct import pack, unpack
from itertools import accumulate
from copy import deepcopy

from ma2_synatize import *

class aMaySynBuilder:

    templateFile = "template.matzethemightyemperor"

    def __init__(self, title, tracks, patterns, synths, drumkit, **kwargs):
        self.title = title
        self.tracks = tracks
        self.patterns = patterns
        self.synths = synths
        self.drumkit = drumkit

        self.MODE_headless = False
        self.MODE_debug = False

        self.synatize_form_list = None
        self.synatize_main_list = None
        self.synatize_param_list = None

        self.B_offset = 0
        self.B_stop = float('Inf')
        self.module_shift = 0

    def setInterval(self, from_, to_):
        self.B_offset = from_
        self.B_stop = to_

    def aMaySynatize(self, synfile, reshuffle_randoms = False):
        old_drumkit = self.drumkit

        def_synths = ['D_Drums', 'G_GFX', '__None']
        def_drumkit = ['SideChn']

        self.synatize_form_list, self.synatize_main_list, drumkit, self.stored_randoms, self.synatize_param_list \
            = synatize(synfile, stored_randoms = self.stored_randoms, reshuffle_randoms = reshuffle_randoms)

        self.synths = ['I_' + m['id'] for m in self.synatize_main_list if m['type']=='main']
        self.synths.extend(def_synths)

        self.drumkit = def_drumkit + drumkit

        # remove the 'update' functionality, the idea is: when adding new synths, rerendering your .mayson with aMaySyn, you can re-import it automatically

    def aMaySynInitialized(self):
        return self.synatize_form_list is not None and self.synatize_main_list is not None and self.synatize_param_list is not None

    def getInfo(self, key):
        if key == 'title':
            return self.title
        if key == 'B_offset':
            return self.B_offset
        if key == 'B_stop':
            return self.B_stop
        return None

    def buildGLSL(self, compileGL = False, renderWAV = False, onlyModule = False):
        if not self.aMaySynInitialized():
            print("Tried to build GLSL without having initialized aMay-Synatize. No can't do.")
            return

        filename = self.getInfo('title') + '.glsl'

        if onlyModule:
            test_track = deepcopy(self.tracks[self.current_track])
            test_module = deepcopy(self.getModule())
            test_module.move(0)
            test_track.modules = [test_module]
            test_track.selected_modules = test_track.modules
            tracks = [test_track]
            patterns = [test_module.pattern]
            actually_used_patterns = patterns
            loop_mode = 'seamless'
            offset = 0
            max_mod_off = test_module.getModuleOff()

            # might need to shift
            module_shift = self.getModule().mod_on
            for part in self.getInfo('BPM').split():
                bpm_point = float(part.split(':')[0])
                if bpm_point <= module_shift:
                    bpm_list = ['0:' + part.split(':')[1]]
                else:
                    bpm_list.append(str(bpm_point - module_shift) + ':' + part.split(':')[1])
                print(part, module_shift, bpm_list)

            if self.MODE_debug:
                print(test_track)
                print(tracks)
                print(patterns)

        else:
            tracks = [t for t in self.tracks if t.modules and not t.mute] if self.track_solo is None else [self.tracks[self.track_solo]]
            max_mod_off = min(max(t.getLastModuleOff() for t in tracks), self.getInfo('B_stop'))
            offset = self.getInfo('B_offset')
            loop_mode = self.getInfo('loop')
            bpm_list = self.getInfo('BPM').split()

            actually_used_patterns = [m.pattern for t in tracks for m in t.modules] # if m.getModuleOff() >= offset and m.getModuleOn() <= max_mod_off
            patterns = [p for p in self.patterns if p in actually_used_patterns]

            for t in tracks:
                t.selected_modules = [m for m in t.modules if m.pattern in patterns]


        if self.MODE_headless:
            loop_mode = 'full'

        track_sep = [0] + list(accumulate([len(t.selected_modules) for t in tracks]))
        pattern_sep = [0] + list(accumulate([len(p.notes) for p in patterns]))

        nT  = str(len(tracks))
        nT1 = str(len(tracks) + 1)
        nM  = str(track_sep[-1])
        nP  = str(len(patterns))
        nP1 = str(len(patterns) + 1)
        nN  = str(pattern_sep[-1])

        gf = open(self.templateFile)
        glslcode = gf.read()
        gf.close()

        self.loadSynths()
        actually_used_synths = set(t.getSynthName() for t in tracks if not t.getSynthType() == '_')
        actually_used_drums = set(n.note_pitch for p in patterns if p.synth_type == 'D' for n in p.notes)

        if self.MODE_debug: print("ACTUALLY USED:", actually_used_synths, actually_used_drums)

        self.synatized_code_syn, self.synatized_code_drum, paramcode, filtercode, self.last_synatized_forms = \
            synatize_build(self.synatize_form_list, self.synatize_main_list, self.synatize_param_list, actually_used_synths, actually_used_drums)

        if self.MODE_headless:
            print("ACTUALLY USED SYNTHS:", actually_used_synths)
            names_of_actually_used_drums = [drumkit[d] for d in actually_used_drums]
            print("ACTUALLY USED DRUMS:", names_of_actually_used_drums)
            if len(actually_used_drums) == 1:
                self.file_extra_information += names_of_actually_used_drums[0] + '_'

	# TODO: would be really nice: option to not re-shuffle the last throw of randoms, but export these to WAV on choice... TODOTODOTODOTODO!
	# TODO LATER: great plans -- live looping ability (how bout midi input?)
        if self.stored_randoms:
            timestamp = datetime.datetime.now().strftime('%Y/%m/%d %H:%M')[2:]
            countID = self.file_extra_information + (str(self.getWAVFileCount()) if renderWAV else '(unsaved)')
            with open(self.getInfo('title') + '.rnd', 'a') as of:
                of.write(timestamp + '\t' + countID + '\t' \
                                   + '\t'.join((rnd['id'] + '=' + str(rnd['value'])) for rnd in self.stored_randoms if rnd['store']) + '\n')

        # get release and predraw times
        syn_rel = []
        syn_pre = []
        drum_rel = []
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
        drum_index = str(synths.index('D_Drums')+1)

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

        if offset != 0: loopcode += 'time += ' + GLfloat(time_offset) + ';\n' + 4*' '

        print("START TEXTURE")

        fmt = '@e'
        tex = b''

        # TODO:make it more pythonesk with something like
        # tex += ''.join(pack(fmt, float(s)) for s in track_sep)
        # etc.

        for s in track_sep:
            tex += pack(fmt, float(s))
        for t in tracks:
            tex += pack(fmt, float(t.getSynthIndex()+1))
        for t in tracks:
            tex += pack(fmt, float(t.getNorm()))
        for t in tracks:
            tex += pack(fmt, float(syn_rel[t.getSynthIndex()]))
        for t in tracks:
            tex += pack(fmt, float(syn_pre[t.getSynthIndex()]))
        for t in tracks:
            tex += pack(fmt, float(syn_slide[t.getSynthIndex()]))
        for t in tracks:
            for m in t.selected_modules:
                tex += pack(fmt, float(m.mod_on))
        for t in tracks:
            for m in t.selected_modules:
                tex += pack(fmt, float(m.getModuleOff()))
        for t in tracks:
            for m in t.selected_modules:
                tex += pack(fmt, float(patterns.index(m.pattern))) # this could use some purge-non-used-patterns beforehand...
        for t in tracks:
            for m in t.selected_modules:
                tex += pack(fmt, float(m.transpose))
        for s in pattern_sep:
            tex += pack(fmt, float(s))
        for p in patterns:
            for n in p.notes:
                tex += pack(fmt, float(n.note_on))
        for p in patterns:
            for n in p.notes:
                tex += pack(fmt, float(n.note_off))
        for p in patterns:
            for n in p.notes:
                tex += pack(fmt, float(n.note_pitch))
        for p in patterns:
            for n in p.notes:
                tex += pack(fmt, float(n.note_pan * .01))
        for p in patterns:
            for n in p.notes:
                tex += pack(fmt, float(n.note_vel * .01))
        for p in patterns:
            for n in p.notes:
                tex += pack(fmt, float(n.note_slide))
        for p in patterns:
            for n in p.notes:
                tex += pack(fmt, float(n.note_aux))
        for d in drum_rel:
            tex += pack(fmt, float(d))

        texlength = int(len(tex))
        while ((texlength % 4) != 0):
            tex += bytes(10)
            texlength += 1

        texs = str(int(ceil(sqrt(float(texlength)/4.))))

        # Generate output header file
        array = []
        arrayf = []
        for i in range(int(ceil(texlength/2))):
            array += [ unpack('@H', tex[2*i:2*i+2]) ][0]
            arrayf += [ unpack(fmt, tex[2*i:2*i+2]) ][0]

        text = "// Generated by tx210 / aMaySyn (c) 2018 NR4&QM/Team210\n\n#ifndef SEQUENCE_H\n#define SEQUENCE_H\n\n"
        text += "// Data:\n//"
        for val in arrayf:
            text += ' ' + str(val) + ','
        text += '\n'
        text += "const unsigned short sequence_texture[{:d}]".format(int(ceil(texlength/2)))+" = {"
        for val in array[:-1]:
            text += str(val) + ','
        text += str(array[-1]) + '};\n'
        text += "const int sequence_texture_size = " + str(texs) + ";"
        text += '\n#endif\n'

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
            .replace("TURN_DOWN", GLfloat(self.getInfo('turn_down')))

        glslcode = glslcode.replace('e+00','').replace('-0.)', ')').replace('+0.)', ')')
        glslcode = self.purgeExpendables(glslcode)

        with open("template.textureheader") as f:
            texheadcode = f.read()
            f.close()

        glslcode_frag = '#version 130\n' + glslcode.replace("//TEXTUREHEADER", texheadcode)

        with open("sfx.frag", "w") as out_file:
            out_file.write(glslcode_frag)

        print("GLSL CODE WRITTEN (sfx.frag) -- NR4-compatible fragment shader")

        # for "standalone" version
        tex_n = str(int(ceil(texlength/2)))
        texcode = 'const float sequence_texture[' + tex_n + '] = float[' + tex_n + '](' + ','.join(map(GLfloat, arrayf)) + ');\n'

        glslcode = glslcode.replace("//TEXCODE",texcode).replace('//TEXTUREHEADER', 'float rfloat(int off){return sequence_texture[off];}\n')

        with open(filename, "w") as out_file:
            out_file.write(glslcode)

        print("GLSL CODE WRITTEN (" + filename + ") - QM-compatible standalone fragment shader")

        pyperclip.copy(glslcode)

        if compileGL or renderWAV:
            self.compileShader(glslcode, renderWAV)