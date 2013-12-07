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

from time import time
from random import randint, choice

from HttpParser import HttpParser
from StreamBuf import StreamBuf

# missing constant
select.EPOLLRDHUP = 0x2000

# keep-alive params for clients
CLIENT_TIMEOUT = 30
CLIENT_MAX_REQS = 1000

#logging.basicConfig(filename='server.log', filemode='w+', level=logging.DEBUG)

class Server(object):

    def __init__(self, servers, caches, port = 8080, ttl = 170, compress = False, cache = False):
        """ Create an instance of the Shellac server """

        # fd => socket
        self._connections = {}

        # fd => [HttpParser] (Queue)
        self._requests = {}

        # fd => [Response] (Queue)
        self._responses = {}

        # fd_up => [(fd_down, resp_id)] (Queue)
        self._stream_map = {}

        # names of upstream servers to balance traffic on
        self._upstream_servers = servers

        # names of memcached servers to build cache on
        self._cache_servers = caches

        # host => [Connection, Connection, ...]
        self._upstream_connections = {}

        # fd => [Request] (Queue)
        self._upstream_requests = {}

        # compress cache entries?
        self._compress = compress

        # cache objects?
        self._cache = cache

        # Memcached client
        self._mc = None

        # how long should entries live?
        self._ttl = ttl


        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._socket.bind(('0.0.0.0', port))
        self._socket.listen(1)
        self._socket.setblocking(0)

        self._epoll = select.epoll()
        self._epoll.register(self._socket.fileno(), select.EPOLLIN)

        if self._cache:
            self._mc = pylibmc.Client(['%s:%d' % cacher for cacher in caches],
                                        binary=True, 
                                        behaviors={'tcp_nodelay': True, 'ketama': True})


    def _get_upstream_fd(self, fd):
        """ Get the current upstream fd for a given client """

        now = time() 
        dead = []
        close = self._close_connection
        conns = self._upstream_connections

        # already have a valid one?
        conn_fd = self._connections[fd][1]
        if conn_fd in conns and conn_fd != 0:
            c = conns[conn_fd]
            if c[4] == -1:
                return conn_fd
            if now - c[3] < c[4] and c[6] < c[5]:
                return conn_fd

        # try to (re)use an existing one...
        for k, c in conns.viewitems():
            conn_fd = c[0].fileno()
            if c[4] != -1:
                if now - c[3] >= c[4] or c[6] >= c[5]:
                    dead.append(conn_fd)
                    continue
            if c[1] == 0:
                for d_fd in dead:
                    close(d_fd)

                c[1] = fd
                self._connections[fd][1] = conn_fd
                return conn_fd

        # close any dead upstream conns
        for d_fd in dead:
            close(d_fd)

        # else create a new one...
        (host, port) = choice(self._upstream_servers)
        conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        conn_fd = conn.fileno()
        conn.connect((host, port))
        conn.setblocking(0)
        self._epoll.register(conn_fd) 

        # spec: conn, down_fd, ctime, atime, timeout, max, count 
        self._upstream_connections[conn_fd] = [conn, fd, time(), 0, -1, 0, 0]
        self._connections[fd][1] = conn_fd

        #logging.debug('New upstream connection %d => %d', conn_fd, fd)

        return conn_fd
        

    def _new_connection(self):
        """ Initialize a new client connection """

        conn, address = self._socket.accept()
        conn.setblocking(0)
        fd = conn.fileno()

        # reap any dead clients every so often...
        if randint(0, 100) == 1:
            self._gc_connections()

        self._epoll.register(fd, select.EPOLLIN | select.EPOLLRDHUP)

        # spec: conn, up_fd, ctime, atime, timeout, max, count
        self._connections[fd] = [conn, 0, time(), 0, CLIENT_TIMEOUT, CLIENT_MAX_REQS, 0]
        self._requests[fd]    = HttpParser()
        self._responses[fd]   = deque()

        #logging.debug('New connection (%d)...', fd)
    
    def _gc_connections(self):
        """ Clean up any idle client connections """

        close = self._close_connection
        conns = self._connections
        now   = time()

        dead = [fd for fd, c in conns.viewitems() \
                if now - c[3] >= c[4] or c[6] >= c[5]]

        for fd in dead:
            close(fd)

    def _close_connection(self, fd):
        """ Handle EPOLLHUP: a client or upstream connection has been closed """

        #logging.debug('Closed connection %d', fd)

        self._epoll.unregister(fd)

        if fd in self._connections:
            self._close_client(fd)    
        else:
            self._close_upstream(fd)
        
        #logging.debug('Closed connection (%d)', fd)

    def _close_client(self, fd):
        """ Clean up a client connection"""

        #logging.debug('Closed client (%d)', fd)
        
        up_fd = self._connections[fd][1]

        self._connections[fd][0].close()
        del self._connections[fd]

        self._requests.pop(fd, None)
        self._responses.pop(fd, None)

        if up_fd != 0:
            # free the connection for re-use
            if up_fd in self._upstream_connections:
                self._upstream_connections[up_fd][1] = 0

            # close upstream if there are outstanding responses
            if len(self._stream_map.get(up_fd, [])) != 0:
                self._close_connection(up_fd)


    def _close_upstream(self, fd):
        """ Clean up an upstream connection """

        #logging.debug('Closed upstream (%d)', fd)

        dn_fd = self._upstream_connections[fd][1]

        self._upstream_connections[fd][0].close()
        del self._upstream_connections[fd]

        if dn_fd != 0:
            # indicate that this client has no upstream assigned
            if dn_fd in self._connections:
                self._connections[dn_fd][1] = 0
            
            # close client if there are outstanding responses
            if len(self._stream_map.get(fd, [])) != 0:
                self._close_connection(dn_fd)

        self._upstream_requests.pop(fd, None)
        self._stream_map.pop(fd, None)

    def _write_event(self, fd):
        """ Handle EPOLLOUT: a client or upstream connection can be written """

        if fd in self._connections:
            self._write_response(fd)
        else:
            self._write_request(fd)

    def _write_response(self, fd):
        """ Write client responses to the wire """

        assert fd in self._connections
        assert fd in self._responses

        if len(self._responses[fd]) == 0:
            return

        # note: response is None if this is from cache
        (key, response, stream) = self._responses[fd][0]
        if not stream.ready():
            return

        conn = self._connections[fd]
        try:
            sent = conn[0].send( stream.read() )
        except:
            self._close_connection(fd)
            return

        if sent == 0:
            self._close_connection(fd)
            return

        # update atime
        conn[3] = time()
        stream.ack( sent )

        if stream.complete():
            #logging.debug('Sent req-%d to client-%d)', rid, fd)
            #del self._response_index[rid]
            self._responses[fd].popleft()

            if len(self._responses[fd]) == 0:
                self._epoll.modify(fd, select.EPOLLIN | select.EPOLLRDHUP)

    def _write_request(self, fd):
        """ Write requests to the upstream wires """

        #logging.debug('write_request(%d)', fd)

        if len(self._upstream_requests.get(fd, [])) == 0:
            return

        conn = self._upstream_connections[fd]
        stream = self._upstream_requests[fd][0]

        if not stream.ready():
            return

        try:
            sent = conn[0].send( stream.read() )
        except:
            self._close_connection(fd)
            return

        if sent == 0:
            self._close_connection(fd)
            return

        # update atime
        conn[3] = time()
        stream.ack( sent )

        if stream.complete():
            #logging.debug('Sent request to server-%d', fd)
            self._upstream_requests[fd].popleft()

            if len(self._upstream_requests[fd]) == 0:
                self._epoll.modify(fd, select.EPOLLIN | select.EPOLLRDHUP)

    def _read_event(self, fd):
        """ Handle EPOLLIN: a client or upstream connection can be read """

        if fd in self._connections:
            self._read_requests(fd)
        else:
            self._read_responses(fd)

    def _read_requests(self, fd):
        """ Read incoming requests off the wire """

        assert fd in self._connections        
        assert self._requests[fd] != None
        
        conn = self._connections[fd]

        try:
            data = conn[0].recv(4096)
        except:
            self._close_connection(fd)
            return

        # update atime
        conn[3] = time()
        request = self._requests[fd]
        
        while len(data) != 0:

            parsed = request.parse(data, len(data))
            data = data[parsed:]

            if request.message_complete():                

                key = request.url()

                # KILL SWITCH: don't ask.
                if key == '/kill':
                    sys.exit(0)

                # are we caching or just proxy?
                if self._cache:
                    blob = self._mc.get(key)
                    if blob != None:
                        # this is a cache hit!
                        #logging.debug('Cache hit %s (size = %d)', key, len(blob))
                        conn[6] += 1
                        stream = StreamBuf( blob )
                        stream.close()
                        responsev = (key, None, stream)
                        self._responses[fd].append( responsev )
                        self._requests[fd] = HttpParser()
                        self._epoll.modify(fd, select.EPOLLIN | select.EPOLLOUT | select.EPOLLRDHUP)
                        request = self._requests[fd]
                        continue


                # going to have to look up stream
                ufd = self._get_upstream_fd(fd)
                uconn = self._upstream_connections[ufd]
                
                # inc request counts
                conn[6] += 1
                uconn[6] += 1

                # tweak request as needed
                request.headers()['accept-encoding'] = 'gzip'

                # wrap it in a stream buffer
                stream = StreamBuf( str(request) )
                stream.close()

                # watch the fd for r/w
                self._epoll.modify( fd, select.EPOLLIN | select.EPOLLOUT | select.EPOLLRDHUP)
                self._epoll.modify(ufd, select.EPOLLIN | select.EPOLLOUT | select.EPOLLRDHUP)
                
                # queue the request/response
                responsev = (key, HttpParser(), StreamBuf())
                
                self._responses[fd].append( responsev )
                
                self._upstream_requests.setdefault(ufd, deque()).append( stream )
                self._stream_map.setdefault(ufd, deque()).append( responsev )

                self._requests[fd] = HttpParser()
                request = self._requests[fd]


    def _read_responses(self, fd):
        """ Read responses from upstream servers off the wire """

        conn = self._upstream_connections.get(fd, None)

        if conn is None:
            return

        assert fd in self._stream_map
        
        if len(self._stream_map[fd]) == 0:
            return

        try:
            data = conn[0].recv(4096)
        except:
            self._close_connection(fd)
            return

        (key, response, stream) = self._stream_map[fd][0]

        # update atime
        conn[3] = time()

        while len(data) != 0:
            parsed = response.parse(data, len(data))
            data = data[parsed:]

            if response.message_complete():

                # todo: cache the response!!!

                ka = response.keep_alive()
                (timeout, maxr) = response.keep_alive_params()

                headers = response.headers()
                headers['server'] = 'Shellac/0.1.0a'
                headers['keep-alive'] = 'timeout=5, max=100'
                headers['connection'] = 'keep-alive'
                headers.pop('accept-ranges', None)

                obj = str(response)

                stream.write( obj )
                stream.close()
                
                if not ka:
                    self._close_connection(fd)
                    break

                # timeout and max requests
                conn[4] = timeout
                conn[5] = maxr

                if self._cache:
                    #logging.debug('Cached %s\r\n%s\r\n', key, obj)
                    self._mc.set(key, obj, time=self._ttl)

                self._stream_map[fd].popleft()

                if len(self._stream_map[fd]) != 0:
                    (key, response, stream) = self._stream_map[fd][0]                        
                else:
                    self._epoll.modify(fd, select.EPOLLOUT | select.EPOLLRDHUP)
                    break

    def run(self):
        """ Run the server reactor """

        listen_fd        = self._socket.fileno()
        new_connection   = self._new_connection
        read_event       = self._read_event
        write_event      = self._write_event
        close_connection = self._close_connection 

        try:
            while True:
                events = self._epoll.poll(1)

                for fd, event in events:
                    
                    if fd == listen_fd:
                        new_connection()

                    elif event & select.EPOLLIN:
                        read_event(fd)

                    elif event & select.EPOLLOUT:
                        write_event(fd)

                    elif event & select.EPOLLHUP:
                        close_connection(fd)

                    elif event & select.EPOLLRDHUP:
                        close_connection(fd)

                    elif event & select.EPOLLERR:
                        close_connection(fd)
                    
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
                        compress = args.compress,
                        cache = len(caches) != 0)
        shellac.run()
    except (KeyboardInterrupt, IOError) as ex:
        print
        print 'Shutting down...' 

def signal_handler(signal, frame):
    pass

if __name__ == '__main__':
    main()
