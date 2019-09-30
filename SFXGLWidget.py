#!/usr/bin/env python
#
# #
# # # THIS IS WHAT QM HAD TO STEAL FROM NR4 (and modify it accordingly)
# #
#
#
# toy210 - the team210 live shader editor
#
# Copyright (C) 2017/2018 Alexander Kraus <nr4@z10.info>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

from PyQt5.QtWidgets import QOpenGLWidget
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from OpenGL.GL import *
from OpenGL.GLU import *
from math import ceil, sqrt
from struct import pack, unpack
import numpy as np


class SFXGLWidget(QOpenGLWidget):

    def __init__(self, parent, samplerate, duration, texsize, moreUniforms = {}):
        QOpenGLWidget.__init__(self, parent)
        self.move(10000.,1000.)
        self.program = 0
        self.iSampleRateLocation = 0
        self.iBlockOffsetLocation = 0
        self.hasShader = False
        self.duration = duration
        self.samplerate = samplerate
        self.texsize = texsize
        self.blocksize = self.texsize * self.texsize
        self.nsamples = self.duration*self.samplerate # it was *2
        self.nblocks = int(ceil(float(self.nsamples)/float(self.blocksize)))
        self.nsamples_real = self.nblocks*self.blocksize # this too was *2
        self.duration_real = float(self.nsamples_real)/float(self.samplerate)
        self.image = None
        self.music = None
        self.floatmusic = None
        self.moreUniforms = moreUniforms
        self.sequence_texture_handle = None
        self.sequence_texture = None
        self.sequence_texture_size = None

    def initializeGL(self):
        print("Init.")

        if self.sequence_texture is not None:
            self.initSequenceTexture()

        self.framebuffer = glGenFramebuffers(1)
        glBindFramebuffer(GL_FRAMEBUFFER, self.framebuffer)
        print("Bound buffer with id", self.framebuffer)
        self.texture = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, self.texture)
        print("Bound texture with id", self.texture)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, self.texsize, self.texsize, 0, GL_RGBA, GL_UNSIGNED_BYTE, self.image)
        print("Teximage2D returned.")
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP)

        glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, self.texture, 0)


    def setSequenceTexture(self, sequence):
        self.sequence_texture = np.array(sequence, dtype = np.int16)
        self.sequence_texture_size = ceil(sqrt(len(sequence)/4.))

        print('size:', self.sequence_texture_size, '\n')
        c = 0
        for s,t in zip(self.sequence_texture, sequence):
            print(s, t)
            c += 1
            if c > 100:
                break


    def initSequenceTexture(self):
        print("Init Sequence Texture. DOES NOT WORK..!")

        glActiveTexture(GL_TEXTURE0)

        # port of NR4s C code...
        self.sequence_texture_handle = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, self.sequence_texture_handle)
        print("Bound texture with id", self.sequence_texture_handle, "(for sequence)")
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_REPEAT)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_REPEAT)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, self.sequence_texture_size, self.sequence_texture_size, 0, GL_RGBA, GL_UNSIGNED_SHORT, self.sequence_texture)

        glPixelStorei(GL_PACK_ALIGNMENT, 4)
        glPixelStorei(GL_UNPACK_ALIGNMENT, 4)


    def computeShader(self, source) :
        useSequenceTexture = (self.sequence_texture is not None)

        self.shader = glCreateShader(GL_FRAGMENT_SHADER)
        glShaderSource(self.shader, source)
        glCompileShader(self.shader)

        status = glGetShaderiv(self.shader, GL_COMPILE_STATUS)
        if status != GL_TRUE :
            log = glGetShaderInfoLog(self.shader)
            if not log:
                return 'Error occurred in GL Shader, but info log was empty O.o'
            return log.decode('utf-8')

        self.program = glCreateProgram()
        glAttachShader(self.program, self.shader)
        glLinkProgram(self.program)

        status = glGetProgramiv(self.program, GL_LINK_STATUS)
        if status != GL_TRUE :
            log = glGetProgramInfoLog(self.program)
            if not log:
                return 'Error occurred in GL Program. but info log was empty O.o'
            return log.decode('utf-8')

        glBindFramebuffer(GL_FRAMEBUFFER, self.framebuffer)
        glUseProgram(self.program)

        self.iTexSizeLocation = glGetUniformLocation(self.program, 'iTexSize')
        self.iBlockOffsetLocation = glGetUniformLocation(self.program, 'iBlockOffset')
        self.iSampleRateLocation = glGetUniformLocation(self.program, 'iSampleRate')
        if useSequenceTexture:
            self.sfx_sequence_texture_location = glGetUniformLocation(self.program, 'iSequence');
            self.sfx_sequence_texture_width_location = glGetUniformLocation(self.program, 'iSequenceWidth');


        self.uniformLocation = {}
        for uniform in self.moreUniforms:
            self.uniformLocation[uniform] = glGetUniformLocation(self.program, uniform)
            glUniform1f(self.uniformLocation[uniform], np.float32(self.moreUniforms[uniform]))

        OpenGL.UNSIGNED_BYTE_IMAGES_AS_STRING = True
        music = bytearray(self.nblocks*self.blocksize*4)

        glViewport(0, 0, self.texsize, self.texsize)

        glUniform1f(self.iTexSizeLocation, np.float32(self.texsize))
        glUniform1f(self.iSampleRateLocation, np.float32(self.samplerate))
        if useSequenceTexture: # DOESN'T WORK YET
            glUniform1i(self.sfx_sequence_texture_location, 0)
            glUniform1f(self.sfx_sequence_texture_width_location, np.float32(self.sequence_texture_size))
            glActiveTexture(GL_TEXTURE0)
            glBindTexture(GL_TEXTURE_2D, self.sequence_texture_handle)

        for i in range(self.nblocks) :
            glUniform1f(self.iBlockOffsetLocation, np.float32(i*self.blocksize))

            glBegin(GL_QUADS)
            glVertex2f(-1,-1)
            glVertex2f(-1,1)
            glVertex2f(1,1)
            glVertex2f(1,-1)
            glEnd()

            glFlush()

            music[4*i*self.blocksize:4*(i+1)*self.blocksize] = glReadPixels(0, 0, self.texsize, self.texsize, GL_RGBA, GL_UNSIGNED_BYTE)

        music = unpack('<'+str(self.blocksize*self.nblocks*2)+'H', music)
        music = (np.float32(music)-32768.)/32768.
        self.floatmusic = music

        music = pack('<'+str(self.blocksize*self.nblocks*2)+'f', *music)
        self.music = music

        #glBindFramebuffer(GL_FRAMEBUFFER, 0)
        #glDeleteTextures([self.texture])

        return 'Success.'
