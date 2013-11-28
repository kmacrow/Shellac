#!/usr/bin/env python

import os
import cStringIO

class Stream(object):

    def __init__(self, data = None):
        self._buf = cStringIO.StringIO()
        self._eof = False
        self._ready = False

        if data:
            self.write(data)

    def write(self, data):
        self._ready = True
        pos = self._buf.tell()
        self._buf.seek(0, os.SEEK_END)
        self._buf.write(data)
        self._buf.seek(pos)

    def read(self):   
        return self._buf.read()

    def close(self):
        self._eof = True

    def buffer(self):
        return self._buf.getvalue()

    def complete(self):
        return self._eof

    def ready(self):
        return self._ready
