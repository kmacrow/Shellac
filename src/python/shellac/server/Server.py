#!/usr/bin/env python

import os
import sys
import signal
import random
import argparse
import logging
import socket, select
import pylibmc
from http_parser.parser import HttpParser

logger = logging.getLogger(__name__)

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

class Server(object):

    def __init__(self, servers, caches, port = 8080, ttl = 170, compress = False):

        # fd => socket
        self._connections = {}

        # fd => [HttpParser] (Queue)
        self._requests    = {}

        # fd => [Response] (Queue)
        self._responses   = {}

        # (fd_up, req_num) => (fd_down, resp_num)
        self._stream_map = {}

        # names of upstream servers to balance traffic on
        self._upstream_servers = servers

        # names of memcached servers to build cache on
        self._cache_servers = caches

        # fd => socket
        self._upstream_connections = {}

        # fd => [Request] (Queue)
        self._upstream_requests    = {}

        # compress cache entries?
        self._compress = compress

        # how long should entries live?
        self._ttl = ttl


        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._socket.bind(('0.0.0.0', port))
        self._socket.listen(1)
        self._socket.setblocking(0)

        self._epoll = select.epoll()
        self._epoll.register(self._socket.fileno(), select.EPOLLIN)

    def _choose_upstream_fd(self):

        def create_connection(host, port):
            conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            conn.connect((host, port))
            conn.setblocking(0)
            self._epoll.register(conn.fileno(), select.EPOLLIN | select.EPOLLHUP)
            return conn

        (host, port) = random.choice(self._upstream_servers)

        if host in self._upstream_connections:
            if len(self._upstream_connections[host]) < 4:
                conn = create_connection(host, port)
                self._upstream_connections[host].append(conn)
                return conn.fileno()
            else:
                conn = random.choice(self._upstream_connections[host])
                return conn.fileno()
        else:
            conn = create_connection(host, port)
            self._upstream_connections[host] = [conn]
            return conn.fileno() 

    def _new_connection(self):
    
        connection, address = self._socket.accept()
        connection.setblocking(0)
        fd = connection.fileno()

        self._epoll.register(fd, select.EPOLLIN | select.EPOLLHUP)
        self._connections[fd] = connection
        self._requests[fd]    = [HttpParser()]
        self._responses[fd]   = []
        
        cork_socket(connection)

    def _close_connection(self, fd):

        self._epoll.unregister(fd)

        if fd in self._connections:
            # it's a client
            self._connections[fd].close()
            del self._connections[fd]
            del self._requests[fd]
            del self._responses[fd]
        else:
            # it's an upstream server
            found = False
            for host in self._upstream_connections:
                for i in range(len(self._upstream_connections[host])):
                    if self._upstream_connections[host][i].fileno() == fd:
                        self._upstream_connections[host][i].close()
                        del self._upstream_connections[host][i]
                        found = True
                        break
                if found:
                    break
            del self._upstream_requests[fd]
            # todo: clean up the stream_map


    def _write_event(self, fd):

        if fd in self._connections:

            # write response to client
            if len(self._responses[fd]) == 0:
                return

            (key, stream) = self._responses[fd][0]
            if not stream.ready():
                return

            sent = self._connections[fd].send( stream.read() )
            stream.ack( sent )

            if stream.complete():
                flush_socket(self._connections[fd])
                # cache.put(key, stream.buffer())
                self._responses[fd] = self._responses[fd][1:]
                    
        else:
            # write request to upstream server
            if len(self._upstream_requests[fd]) == 0:
                return

            stream = self._upstream_requests[fd][0]
            if not stream.ready():
                return

            sent = self._upstream_connections[fd].send( stream.read() )
            stream.ack( sent )

            if stream.complete():
                flush_socket(self._upstream_connections[fd])
                self._upstream_requests[fd] = self._upstream_requests[fd][1:]


    def _read_event(self, fileno):

        if fd in self._connections:
            # read request from client
            data = self._connections[fd].recv(4096)

            request = self._requests[fd][-1]
            request.execute(data, len(data))

            if request.is_message_complete():
                # create a response
                #key = request.get_url()
                #if cache.has(key):
                #    self._responses[fd].append( ( key, Stream(cache.get(key)) ) )
                #else:
                self._responses[fd].append( ( key, Stream(data=None, buffered=True) ) )
                
                up_fd = self._choose_upstream_fd()
                self._upstream_requests[up_fd].append( Stream( http_request_str(request) ) )
                
                self._stream_map[up_fd].append(fd)
            
            
        else:
            # read response from upstream server
            data = self._upstream_connections[fd].recv(4096)
            
            down_fd = self._stream_map[fd][0]
            (_, response) = self._responses[down_fd][0]
            response.push(data)

            if len(data) == 0:
                response.close()
                self._stream_map[fd] = self._stream_map[fd][1:]

    def run(self):
        
        try:
            while True:
                events = self._epoll.poll(1)
                for fd, event in events:
                    
                    if fd == self._socket.fileno():
                        self._new_connection()

                    elif event & select.EPOLLIN:
                        self._read_event(fd)

                    elif event & select.EPOLLOUT:
                        self._write_event(fd)

                    elif event & select.EPOLLHUP:
                        self._close_connection(fd)
                    
        finally:
            self._epoll.unregister(self._socket.fileno())
            self._epoll.close()
            self._socket.close()

def cork_socket( sock ):
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_CORK, 1)

def flush_socket( sock ):
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_CORK, 0)

def http_request_str( request ):
    req = ''
    req = '%s %s HTTP/1.1\r\n' % (request.get_method(), request.get_url())
    
    headers = request.get_headers()
    headers['Connection'] = 'keep-alive'

    for header in headers:
        req += '%s: %s\r\n' % (header, headers[header])

    req += '\r\n'
    req += request.recv_body()
    return req

def main():

    def parse_server_list(slist, default_port):
        result = []
        if ',' in slist:
            raw = slist.split(',')
        else:
            raw = [slist]
        for srv in raw:
            if ':' in srv:
                (host, port) = srv.split(':')
                result.append((socket.gethostbyname(host), int(port)))
            else:
                result.append((socket.gethostbyname(srv), default_port))
        return result

    parser = argparse.ArgumentParser(description='Shellac Accelerator')
    parser.add_argument('-s', '--servers',
                            help='Web servers to cache: host:port,host:port,... (port defaults to 80)')
    parser.add_argument('-c', '--caches',
                            help='Cache servers to use: host:port,host:port,... (port defaults to 11211)')
    parser.add_argument('-p', '--port', type=int, default=8080, 
                            help='Port to listen for connections on.')
    parser.add_argument('-t', '--ttl', type=int, default=170,
                            help='Lifetime of cached objects.')
    parser.add_argument('-z', '--compress', action='store_true',
                            help='Compress cached objects.')

    args = parser.parse_args()

    servers = parse_server_list(args.servers, 80)
    caches = parse_server_list(args.caches, 11211)

    if len(servers) == 0:
        print 'No upstream web servers specified. See shellac -h for help.'
        sys.exit(1)
    
    if len(caches) == 0:
        print 'No cache servers specified. See shellac -h for help.'
        sys.exit(1)

    # todo: check that servers are responsive
    
    print 'Running Shellac on port %d...' % args.port

    signal.signal(signal.SIGINT, signal_handler)

    try:
        shellac = Server(servers, caches, 
                        port = args.port,
                        ttl = args.ttl,
                        compress = args.compress)
        shellac.run()
    except (KeyboardInterrupt, IOError) as ex:
        print
        print 'Shutting down...' 

def signal_handler(signal, frame):
    pass

if __name__ == '__main__':
    main()
