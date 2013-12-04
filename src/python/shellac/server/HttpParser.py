#!/usr/bin/env python
"""
    Simple, fast HTTP parsing with no dependencies.

    Usage:
        buf = '...an HTTP stream...' 
        p = HttpParser()
        while not p.message_complete():
            c = p.parse(buf, len(buf))
            buf = buf[c:]

        print p.headers()
        print p.body().read()

    Limitations:
        - poor support for chunk extensions
        - no support for chunk trailers
        - only gzip compression is supported
        - some pythonic but unnecessary string copying
        - test coverage could be better
        - not thread safe, designed for a reactor
        - no support for constructing messages
        - no order is maintained for headers 
            - WWW-Authenticate and others will not work

    Credits:
        - Kalan MacRow @k16w github.com/kmacrow

    License:
        - GPL <http://www.gnu.org/licenses/gpl.html>

"""

import re
import os
import zlib
import cStringIO

CHUNK_HEADER_RX = r'(\r\n)?[a-z0-9]+(;[a-z0-9]+="?[a-z0-9\-_]+"?)?\r\n'

class HttpParser(object):

    def __init__(self):
        self._method = None
        self._version = None
        self._url = None
        self._status = None
        self._message = None
        self._headers = {}
        self._body = cStringIO.StringIO()
        self._buf = ''
        self._is_request = True
        self._content_len = None
        self._chunked = False
        self._last_chunk = False
        self._gzip = zlib.decompressobj(31)

        self._on_first_line = True
        self._on_headers = False
        self._on_body = False

        self._headers_complete = False
        self._message_complete = False

    def method(self):
        return self._method

    def url(self):
        return self._url

    def status(self):
        return self._status

    def version(self):
        return self._version

    def message(self):
        return self._message

    def headers(self):
        return self._headers

    def body(self):
        return self._body

    def is_request(self):
        return self._is_request

    def is_response(self):
        return not self._is_request

    def headers_complete(self):
        return self._headers_complete

    def message_complete(self):
        return self._message_complete

    def __str__(self):

        def header_case(k):
            return '-'.join(map(lambda x: x.capitalize(), k.split('-')))

        def header_value(v):
            if isinstance(v, list):
                return ', '.join(v)
            else:
                return v

        s = ''
        if self.is_request():
            s = '%s %s HTTP/%.1f' % (self.method(), self.url(), self.version())
        else:
            s = 'HTTP/%.1f %d %s' % (self.version(), self.status(), self.message())
        s += '\r\n'

        self._headers.pop('transfer-encoding', None)
        self._headers.pop('content-length', None)

        for k in self._headers:
            s += '%s: %s\r\n' % (header_case(k), header_value(self._headers[k]))
        
        self._body.seek(0)
        b = self._body.read()
        
        if self._headers.get('content-encoding', 'identity') == 'gzip':
            zz = zlib.compressobj(6, zlib.DEFLATED, 31)
            b  = zz.compress(b)
            b += zz.flush()

        if len(b) != 0:
            s += 'Content-Length: %d\r\n' % len(b)
                 
        s += '\r\n'
        s += b
        return s

    def parse(self, data, length):
        """ Parse data, return number of bytes consumed. """
        
        if length == 0:
            return

        nb_parsed = 0

        while True:

            if self._on_first_line:

                buf_len = len(self._buf)
                self._buf += data

                idx = self._buf.find('\r\n')
                if idx < 0:
                    return length
                
                self._buf = self._buf[:idx + 2]

                self._parse_first_line()

                nb_parsed = len(self._buf) - buf_len

                self._buf = ''
                self._on_first_line = False
                self._on_headers = True
                
                return nb_parsed
                    
            elif self._on_headers:

                buf_len = len(self._buf)
                self._buf += data

                idx = self._buf.find('\r\n\r\n')
                if idx < 0:
                    return length

                self._buf = self._buf[:idx + 4]

                self._parse_headers()

                nb_parsed = len(self._buf) - buf_len

                self._buf = ''
                self._headers_complete = True
                self._on_headers = False
                self._on_body = True

                if self._method in ['GET','HEAD']:
                    self._message_complete = True

                self._chunked = self._headers.get('transfer-encoding', 'none') == 'chunked'
                
                if not self._chunked:
                    self._content_len = int(self._headers.get('content-length', 0))
                    if self._content_len == 0:
                        self._on_body = False
                        self._message_complete = True

                return nb_parsed

            elif self._on_body:

                if not self._chunked:

                    if length < self._content_len:
                        self._buf += data
                        self._content_len -= length
                        return length
                    else:
                        self._buf += data[:self._content_len]
                        self._parse_body()
                        self._flush_body()
                        self._buf = ''

                        nb_parsed = self._content_len

                        self._content_len = 0
                        self._on_body = False
                        self._message_complete = True
                        return nb_parsed

                else:

                    # read chunked message body
                    return self._parse_chunked(data, length)


            else:
                return 0

    def _parse_chunk_size(self, line):
        """ Parse chunk header size """

        size = line.strip()
        if ';' in size:
            return int(size.split(';')[0], 16) 
        else:
            return int(size, 16)

    def _parse_chunked(self, data, length):
        """ Parse a chunked response """

        buf_len = len(self._buf)
        self._buf += data
        
        nb_parsed = 0

        if self._content_len is None:

            match = re.match(CHUNK_HEADER_RX, self._buf, flags=re.IGNORECASE)

            if match is None:
                return length

            idx = len(match.group())

            line = self._buf[:idx]
            self._content_len = self._parse_chunk_size(line)
            
            nb_parsed = idx - buf_len
            self._buf = self._buf[idx:]

            left = len(self._buf)

            if self._content_len == 0:
                if self._buf.startswith('\r\n'):
                    nb_parsed += 2
                    self._flush_body()
                    self._on_body = False
                    self._message_complete = True

                self._buf = ''
                return nb_parsed
        
        elif self._content_len == 0:
            if self._buf.startswith('\r\n'):
                nb_parsed = 2 - buf_len
                self._flush_body()
                self._buf = ''
                self._on_body = False
                self._message_complete = True
                return nb_parsed
            else:
                return length
        else:
            left = length

        if left < self._content_len:
            self._content_len -= left
            nb_parsed += left
            return nb_parsed
        else:
            self._buf = self._buf[:buf_len + self._content_len]
            self._parse_body()
            self._buf = ''
            nb_parsed += self._content_len
            self._content_len = None
            return nb_parsed


    def _parse_first_line(self):
        """ Parse a request/response line """

        (a, b, c) = self._buf.rstrip().split(' ', 2)
        if a.startswith('HT'):
            # response...
            self._is_request = False
            (_, version) = a.split('/')
            self._version = float(version)
            self._status = int(b)
            self._message = c
        else:
            # request...
            self._is_request = True
            (_, version) = c.split('/')
            self._version = float(version)
            self._method = a
            self._url = b

    def _parse_headers(self):
        """ Parse raw headers into a dict of scalars/lists """

        headers = self._buf.strip().split('\r\n')
        for header in headers:
            (key, value) = header.split(': ')
            value = value.strip()
            key = key.lower()
            if key in self._headers:
                if isinstance(self._headers[key], list):
                    self._headers[key].append(value)
                else:
                    self._headers[key] = [self._headers[key], value]
            else:
                self._headers[key] = value


    def _parse_body(self):
        pos = self._body.tell()
        self._body.seek(0, os.SEEK_END)
        if self._headers.get('content-encoding', 'identity') == 'gzip':
            self._body.write(self._gzip.decompress(self._buf))
        else:
            self._body.write(self._buf)
        self._body.seek(pos)

    def _flush_body(self):
        if self._headers.get('content-encoding', 'identity') == 'gzip':
            self._body.write(self._gzip.flush())


