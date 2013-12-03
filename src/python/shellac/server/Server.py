#!/usr/bin/env python

import os
import sys
import signal
import random
import argparse
import logging
import socket, select
import pylibmc
from collections import deque

from HttpParser import HttpParser
from Stream import Stream

logger = logging.getLogger(__name__)

class Server(object):

    def __init__(self, servers, caches, port = 8080, ttl = 170, compress = False):
        """ Create an instance of the Shellac server """

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

        self._id_counter = 0


        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._socket.bind(('0.0.0.0', port))
        self._socket.listen(1)
        self._socket.setblocking(0)

        self._epoll = select.epoll()
        self._epoll.register(self._socket.fileno(), select.EPOLLIN)

    def _get_upstream_socket(self, fd):
        """ Find the socket corresponding to a socket descriptor """

        for host in self._upstream_connections:
            for conn in self._upstream_connections[host]:
                if conn.fileno() == fd:
                    return conn
        return None

    def _get_response_by_id(self, fd, rid):
        """ Find the stream object for a response given it's client and id """

        if not fd in self._responses:
            return (None, None, None)
        for (key, _rid, response, stream) in self._responses[fd]:
            if rid == _rid:
                return (key, response, stream)
        return (None, None) 

    def _get_next_id(self):
        self._id_counter += 1
        return self._id_counter

    def _choose_upstream_fd(self):
        """ Choose at random a valid upstream connection """

        def create_connection(host, port):
            conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            conn.connect((host, port))
            conn.setblocking(0)
            self._epoll.register(conn.fileno(), select.EPOLLIN | select.EPOLLHUP | select.EPOLLERR)
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
        """ Initialize a new client connection """

        conn, address = self._socket.accept()
        conn.setblocking(0)
        fd = conn.fileno()

        self._epoll.register(fd, select.EPOLLIN | select.EPOLLHUP | select.EPOLLERR)
        self._connections[fd] = conn
        self._requests[fd]    = deque([HttpParser()])
        self._responses[fd]   = deque()

    def _close_connection(self, fd):
        """ Handle EPOLLHUP: a client or upstream connection has been closed """

        self._epoll.unregister(fd)

        if fd in self._connections:
            # it's a client
            self._connections[fd].close()
            del self._connections[fd]
            del self._requests[fd]
            del self._responses[fd]
            # todo: what about outstanding upstream requests?
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
            del self._stream_map[fd]
            # todo: what about outstanding client requests.



    def _write_event(self, fd):
        """ Handle EPOLLOUT: a client or upstream connection can be written """

        if fd in self._connections:
            self._write_responses(fd)
        else:
            self._write_request(fd)

    def _write_response(self, fd):
        """ Write client responses to the wire """

        assert fd in self._connections
        assert fd in self._responses

        if len(self._responses[fd]) == 0:
            return

        (key, rid, response, stream) = self._responses[fd][0]
        if not stream.ready():
            return

        sent = self._connections[fd].send( stream.read() )
        stream.ack( sent )

        if stream.complete():
            self._responses[fd].popleft()

    def _write_request(self, fd):
        """ Write requests to the upstream wires """

        if not fd in self._upstream_requests or \
                len(self._upstream_requests[fd]) == 0:
                return

        stream = self._upstream_requests[fd][0]
        if not stream.ready():
            return

        conn = self._get_upstream_socket(fd)

        sent = conn.send( stream.read() )
        stream.ack( sent )

        if stream.complete():
            self._upstream_requests[fd].popleft()

    def _read_event(self, fd):
        """ Handle EPOLLIN: a client or upstream connection can be read """

        if fd in self._connections:
            self._read_requests(fd)
        else:
            self._read_response(fd)

    def _read_requests(self, fd):
        """ Read incoming requests off the wire """

        assert fd in self._connections
        assert fd in self._requests
        assert len(self._requests[fd]) != 0

        data = self._connections[fd].recv(4096)

        request = self._requests[fd][-1]
        
        while len(data) != 0:

            parsed = request.parse(data, len(data))
            data = data[parsed:]

            if request.message_complete():

                key = request.url()
                rid = self._get_next_id()
                ufd = self._choose_upstream_fd()
                request = StreamBuf()
                request.write( str(request) )
                request.close()

                self._responses[fd].append( (key, rid, HttpParser(), StreamBuf()) )

                self._upstream_requests.setdefault(ufd, deque()) \
                                .append( request )

                
                self._stream_map.setdefault(ufd, deque()) \
                                .append( (fd, rid) )

                self._requests[fd].append(HttpParser())
                request = self._requests[fd][-1]


    def _read_responses(self, fd):
        """ Read responses from upstream servers off the wire """

        conn = self._get_upstream_socket(fd)

        assert conn != None
        assert fd in self._stream_map
        assert len(self._stream_map[fd]) != 0

        data = conn.recv(4096)
        
        (dfd, rid) = self._stream_map[fd][0]
        (_, response, stream) = self._get_response_by_id(dfd, rid)
        
        if response is None:
            return

        while len(data) != 0:
            parsed = response.parse(data, len(data))
            data = data[parsed:]

            if response.message_complete():
                stream.write( str(response) )
                stream.close()
                self._stream_map[fd].popleft()
                if len(self._stream_map[fd]) != 0:
                    (dfd, rid) = self._stream_map[fd][0]
                    (_, response, stream) = self._get_response_by_id(dfd, rid)
                    if response is None:
                        break

    def run(self):
        """ Run the server reactor """

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

                    elif event & select.EPOLLERR:
                        self._close_connection(fd)
                    
        finally:
            self._epoll.unregister(self._socket.fileno())
            self._epoll.close()
            self._socket.close()


def cork_socket( sock ):
    """ Apply the TCP_CORK option to a socket, prevent sending packets """
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_CORK, 1)

def flush_socket( sock ):
    """ Remove TCP_CORK from a socket, flush packets to the network """
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_CORK, 0)


def main():
    """ Entry point for the server CLI """

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
