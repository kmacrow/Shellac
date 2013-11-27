#!/usr/bin/env python

class Stream(object):

    def __init__(self, data = None, buffered = False):
        self._buf = None
        self._pos = 0
        self._eos = False
        self._ready = False
        self._buffered = buffered

        if data != None:
            self.push(data)

    def push(self, buf):
        if self._buf is None:
            self._buf = buf
            self._ready = True
        else:
            self._buf += buf

    def read(self):   
        if not self._ready:
            return None
        if self._buffered:
            return self._buf[self._pos:]
        else:
            return self._buf

    def ack(self, bytes):
        if not self._ready:
            return
        if bytes > 0:
            if self._buffered:
                self._pos += bytes
            else:
                self._buf = self._buf[bytes:]

    def close(self):
        self._eos = True

    def buffer(self):
        return self._buf

    def complete(self):
        if self._buffered:
            return self._eos and self._pos == len(self._buf)
        else:
            return self._eos and len(self._buf) == 0

    def ready(self):
        return self._ready
        