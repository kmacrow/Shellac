#!/usr/bin/env python

import os
import sys
import argparse
import logging
import socket, select

logger = logging.getLogger(__name__)

class Server(object):

    def __init__(self, port = 8080):

        self._connections = {}
        self._requests    = {}
        self._responses   = {}

        self._cache_connections = {}
        self._cache_requests    = {}
        self._cache_responses   = {}

        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._socket.bind(('0.0.0.0', port))
        self._socket.listen(1)
        self._socket.setblocking(0)

        self._epoll = select.epoll()
        self._epoll.register(self._socket.fileno(), select.EPOLLIN)

    def _new_connection(self):
    
        connection, address = self._socket.accept()
        connection.setblocking(0)
        fileno = connection.fileno()

        self._epoll.register(fileno, select.EPOLLIN)
        self._connections[fileno] = connection
        self._requests[fileno]    = b''
        self._responses[fileno]   = b''
    
    def _close_connection(self, fileno):

        self._epoll.unregister(fileno)
        self._connections[fileno].close()
        del self._connections[fileno]

    def _send_response(self, fileno):

        sent = self._connections[fileno].send(self._responses[fileno])
        self._responses[fileno] = self._responses[fileno][sent:]
        if len(self._responses[fileno]) == 0:
            self._epoll.modify(fileno, 0)
            self._connections[fileno].shutdown(socket.SHUT_RDWR)

    def _read_request(self, fileno):

        self._requests[fileno] += self._connections[fileno].recv(4096)
        if '\r\n\r\n' in self._requests[fileno]:
            self._epoll.modify(fileno, select.EPOLLOUT)
                

    def run():
        
        try:
            while True:
                events = self._epoll.poll(1)
                for fileno, event in events:
                    
                    if fileno == self._socket.fileno():
                        self._new_connection()

                    elif event & select.EPOLLIN:
                        self._read_request(fileno)

                    elif event & select.EPOLLOUT:
                        self._send_response(fileno)

                    elif event & select.EPOLLHUP:
                        self._close_connection(fileno)
                    
        finally:
            self._epoll.unregister(serversocket.fileno())
            self._epoll.close()
            self._socket.close()

def main():
    parser = argparse.ArgumentParser(description='Shellac Accelerator')
    parser.add_argument('-p', '--port', type=int, default=8080, 
                            help='Port to listen for connections on.')
    args = parser.parse_args()

    print
    print "Hello!"
    print 
    #shellac = ShellacServer(port = args.port)
    #shellac.run()

if __name__ == '__main__':
    main()
