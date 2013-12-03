#!/usr/bin/env python
"""
    A stream buffer abstraction

    StreamBuf is similar to StringIO (or cStringIO)
    but will continue to return the same data on
    read() until you ack(n), which advances the read
    pointer. close()'ing a StreamBuf marks it as
    closed but does not prevent further reads -- useful
    for allowing a producer to let a consumer know
    that there isn't more data coming.

    Usage:
        s = StreamBuf('Hello')
        s.write(', world!')
        print s.read()
        -> 'Hello, world!'
        s.ack(7)
        print s.read()
        -> 'world!'
        s.ack(6)
        print s.read()
        -> ''
        s.close()

    Limitations:
        - StreamBuf has no seatbelt, no checks
        - Not thread safe

"""

import os
import cStringIO

class StreamBuf(object):

    def __init__(self, data = None):
        self._buf = ''
        self._pos = 0
        self._eof = False
        self._ready = False

        if data:
            self.write(data)

    def write(self, data):
        self._ready = True
        self._buf += data

    def ack(self, bytes):
        self._pos += bytes

    def seek(self, pos):
        self._pos = pos

    def read(self):   
        return self._buf[self._pos:]

    def close(self):
        self._eof = True

    def buffer(self):
        return self._buf

    def clear(self):
        self._buf = ''
        self._pos = 0
        self._eof = False
        self._ready = False

    def closed(self):
        return self._eof

    def ready(self):
        return self._ready
