#!/usr/bin/env python

import re
import os
import cStringIO

class HttpParser(object):

    def __init__(self):
    	self._method = None
    	self._version = None
    	self._url = None
        self._headers = {}
        self._body = cStringIO.StringIO()
        self._buf = ''
        self._is_request = True
        self._content_len = 0
        self._chunked = False

        self._on_first_line = True
        self._on_headers = False
        self._on_body = False

        self._headers_complete = False
        self._message_complete = False

    def method(self):
    	return self._method

    def url(self):
    	return self._url

    def version(self):
    	return self._version

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

    def execute(self, data, length):
    	""" parse data, return number of bytes consumed """
        
    	if length == 0:
    		self._message_complete = True
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

        		self._chunked = self._headers.get('Transfer-Encoding', 'none') == 'chunked'
        		
        		if not self._chunked:
        			self._content_len = int(self._headers.get('Content-Length', 0))
        			if self._content_len == 0:
        				self._on_body = False
        				self._message_complete = True

        		return nb_parsed

        	elif self._on_body:

        		if not self._chunked:
        			
        			if length <= self._content_len:
        				self._buf = data
        				self._parse_body()
        				self._buf = ''
        				self._content_len -= length
        				return length
        			else:
        				self._buf = data[:self._content_len]
        				self._parse_body()
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

    def _parse_chunked(self, data, length):

    	buf_len = len(self._buf)
		self._buf += data
		nb_parsed = length

    	while True:	

			idx = self._buf.find('\r\n')
			if idx < 0:
				return nb_parsed

			line = self._buf[:idx]
			self._content_len = self._parse_chunk_size(line)
			
			nb_parsed = idx + 2 - buf_len
			self._buf = self._buf[idx + 2:]

			# read chunk data
			left = len(self._buf)

			if left <= self._content_len:
				self._parse_body()
				self._content_len -= left
				self._buf = ''
				nb_parsed += left
				return nb_parsed
			else:
				next = self._buf[self._content_len:]
				self._buf = self._buf[:self._content_len]
				self._parse_body()
				nb_parsed += self._content_len
				self._content_len = 0
				self._buf = next


    def _parse_first_line(self):
    	pass

    def _parse_headers(self):
    	pass

    def _parse_body(self):
    	pos = self._body.tell()
		self._body.seek(0, os.SEEK_END)
		self._body.write(self._buf)
		self._body.seek(pos)
