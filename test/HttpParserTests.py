
import math
import zlib
from shellac.server import HttpParser

def test():

    def dump_parser(p):
        print '######'
        if p.is_request():
            print 'Method: %s' % p.method()
            print 'Url: %s' % p.url()

        print 'Version: %f' % p.version()
        
        if p.is_response():
            print 'Status: %d' % p.status()

        headers = p.headers()
        for header in headers:
            print '%s: %s' % (header, str(headers[header]))
        print '------'
        print p.body().getvalue()

    def chunks(l, n):
        for i in xrange(0, len(l), n):
            yield l[i:i+n]

    print 'Testing...'

    req = 'GET /get-request.html HTTP/1.1\r\n'
    req+= 'User-Agent: Safari\r\n'
    req+= 'Date: Jul 25, 2013 5:14:11 GMT\r\n'
    req+= '\r\n'

    p = HttpParser()
    while not p.message_complete():
        c = p.parse(req, len(req))
        req = req[c:]

    dump_parser(p)

    assert p.method() == 'GET'
    assert p.url() == '/get-request.html'
    assert p.version() == 1.1
    assert p.headers()['user-agent'] == 'Safari'

    req = 'POST /post-request.html HTTP/1.1\r\n'
    req+= 'User-Agent: Safari\r\n'
    req+= 'Content-Length: 10\r\n'
    req+= 'Date: Jul 25, 2013 5:14:11 GMT\r\n'
    req+= '\r\n'
    req+= 'XXXXXXXXXX'

    p = HttpParser()
    while not p.message_complete():
        c = p.parse(req, len(req))
        req = req[c:]

    assert p.method() == 'POST'
    assert p.url() == '/post-request.html'
    assert p.version() == 1.1
    assert p.headers()['user-agent'] == 'Safari'

    dump_parser(p)

    # a request stream...
    req = 'GET /stream1.html HTTP/1.1\r\n'
    req+= 'User-Agent: Safari\r\n'
    req+= 'Date: Jul 25, 2013 5:14:11 GMT\r\n'
    req+= '\r\n'
    req+= 'POST /stream2.html HTTP/1.1\r\n'
    req+= 'User-Agent: Safari\r\n'
    req+= 'Content-Length: 10\r\n'
    req+= 'Date: Jul 25, 2013 5:14:11 GMT\r\n'
    req+= '\r\n'
    req+= 'XXXXXXXXXX'
    req+= 'POST /stream3.html HTTP/1.1\r\n'
    req+= 'User-Agent: Safari\r\n'
    req+= 'Content-Length: 20\r\n'
    req+= 'Date: Jul 25, 2013 5:14:11 GMT\r\n'
    req+= '\r\n'
    req+= 'XXXXXXXXXXXXXXXXXXXX'

    p = []
    while len(req):
        h = HttpParser()
        while not h.message_complete():
            c = h.parse(req, len(req))
            req = req[c:]
        p.append(h)

    assert len(p) == 3

    for h in p:
        print
        assert h.message_complete() == True
        dump_parser(h)    

    # a response stream...
    req = 'HTTP/1.1 200 OK\r\n'
    req+= 'User-Agent: Safari\r\n'
    req+= 'Date: Jul 25, 2013 5:14:11 GMT\r\n'
    req+= 'Content-Length: 10\r\n'
    req+= '\r\n'
    req+= 'XXXXXXXXXX'
    req+= 'HTTP/1.1 200 OK\r\n'
    req+= 'User-Agent: Safari\r\n'
    req+= 'Content-Length: 20\r\n'
    req+= 'Date: Jul 25, 2013 5:14:11 GMT\r\n'
    req+= '\r\n'
    req+= 'XXXXXXXXXXXXXXXXXXXX'
    req+= 'HTTP/1.1 200 OK\r\n'
    req+= 'User-Agent: Safari\r\n'
    req+= 'Content-Length: 30\r\n'
    req+= 'Date: Jul 25, 2013 5:14:11 GMT\r\n'
    req+= '\r\n'
    req+= 'XXXXXXXXXXXXXXXXXXXXXXXXXXXXXX'
    req+= 'HTTP/1.1 200 OK\r\n'
    req+= 'User-Agent: Safari\r\n'
    req+= 'Content-Length: 0\r\n'
    req+= 'Date: Jul 25, 2013 5:14:11 GMT\r\n'
    req+= '\r\n'
    req+= 'HTTP/1.1 302 Not Modified\r\n'
    req+= 'User-Agent: Safari\r\n'
    req+= 'Date: Jul 25, 2013 5:14:11 GMT\r\n'
    req+= '\r\n'

    gzipp = zlib.compressobj(6, zlib.DEFLATED, 31)
    data = gzipp.compress('A certain kind of magic.')
    data += gzipp.flush()

    req+= 'HTTP/1.1 200 OK\r\n'
    req+= 'User-Agent: gws\r\n'
    req+= 'Date: Jan 4, 1989 2:51:12 GMT\r\n'
    req+= 'Content-Encoding: gzip\r\n'
    req+= 'Content-Length: %d\r\n' % len(data)
    req+= '\r\n'
    req+= data

    p = []
    while len(req):
        h = HttpParser()
        while not h.message_complete():
            c = h.parse(req, len(req))
            req = req[c:]
        p.append(h)

    assert len(p) == 6

    for h in p:
        print
        assert h.message_complete() == True
        dump_parser(h)

    p = HttpParser()

    # parse in pieces...
    req = 'HTTP/1.1 200 OK\r\n'
    req+= 'User-Agent: Safari\r\n'
    req+= 'Date: Jul 25, 2013 5:14:11 GMT\r\n'

    while len(req) != 0:
        c = p.parse(req, len(req))
        req = req[c:]

    req = 'Content-Length: 10\r\n'
    req+= '\r\n'
    req+= 'XXXXX'

    while len(req) != 0:
        c = p.parse(req, len(req))
        req = req[c:]

    assert p.headers_complete() == True

    req = 'AAAAA'
    
    while len(req) != 0:
        c = p.parse(req, len(req))
        req = req[c:]

    assert p.message_complete() == True
    assert p.body().read() == 'XXXXXAAAAA'

    dump_parser(p)

    # chunked message body...
    req = 'HTTP/1.1 200 OK\r\n'
    req+= 'User-Agent: Safari\r\n'
    req+= 'User-Agent: Mac OS 10.8\r\n'
    req+= 'Transfer-Encoding: chunked\r\n'
    req+= 'Date: Jul 25, 2013 5:14:11 GMT\r\n'
    req+= '\r\n'
    req+= 'A;ext=foo\r\n'
    req+= 'AAAAAAAAAA'
    req+= '\r\n'
    req+= '8;ext="foo"\r\n'
    req+= 'BBBBBBBB'
    req+= '\r\n'
    req+= '6;ext=foo7\r\n'
    req+= 'CCCCCC'
    req+= '\r\n'
    req+= '0\r\n'
    req+= '\r\n'

    p = HttpParser()
    while not p.message_complete():
        c = p.parse(req, len(req))
        req = req[c:]

    assert p.body().read() == 'AAAAAAAAAABBBBBBBBCCCCCC'

    print
    dump_parser(p)

    # compressed + chunked message...
    gzipp = zlib.compressobj(6, zlib.DEFLATED, 31)
    data = gzipp.compress('Romeo, oh Romeo, why are thou so fair.')
    data += gzipp.flush()

    chunk_sz = int(math.floor(len(data)/3))
    data0 = data[:chunk_sz]
    data1 = data[chunk_sz:2*chunk_sz]
    data2 = data[2*chunk_sz:]

    assert zlib.decompress(data0+data1+data2, 31) == 'Romeo, oh Romeo, why are thou so fair.'

    req = 'HTTP/1.1 200 OK\r\n'
    req+= 'User-Agent: Safari\r\n'
    req+= 'Transfer-Encoding: chunked\r\n'
    req+= 'Content-Encoding: gzip\r\n'
    req+= 'Date: Jul 25, 2013 5:14:11 GMT\r\n'
    req+= '\r\n'
    req+= '%x;ext=foo\r\n' % len(data0)
    req+= data0
    req+= '\r\n'
    req+= '%x;ext="foo"\r\n' % len(data1)
    req+= data1
    req+= '\r\n'
    req+= '%x;ext=foo7\r\n' % len(data2)
    req+= data2
    req+= '\r\n'
    req+= '0\r\n'
    req+= '\r\n'

    p = HttpParser()
    while not p.message_complete():
        c = p.parse(req, len(req))
        req = req[c:]

    assert p.body().read() == 'Romeo, oh Romeo, why are thou so fair.'

    print
    dump_parser(p)    

    data = open('data/fish.jpg', 'r').read()

    req = 'HTTP/1.1 200 OK\r\n'
    req+= 'User-Agent: IE 6\r\n'
    req+= 'Content-Length: %d\r\n' % len(data)
    req+= '\r\n'
    req+= data

    # break the response into pieces
    pieces = list(chunks(req, 1024*1024))

    print
    print 'Request broken into %d pieces...' % len(pieces)

    p = HttpParser()
    i = 0
    k = 0

    for chunk in pieces:
        i += 1
        k = 0
        if p.message_complete():
            break
        while len(chunk) != 0 and not p.message_complete():
            k += 1
            print 'Chunk %d, iteration %d (len = %d)' % (i, k, len(chunk)) 
            c = p.parse(chunk, len(chunk))
            chunk = chunk[c:]

    assert p.message_complete() == True

    ddata = p.body().read()
    
    assert len(data) == len(ddata)

    open('data/fish-out.jpg','w+').write(ddata)    

    # test __str__
    req = 'HTTP/1.1 500 Internal Server Error\r\n'
    req+= 'Server: Apache 2.2\r\n'
    req+= 'Date: Never\r\n'
    req+= 'Content-Length: 12\r\n'
    req+= '\r\n'
    req+= 'RRRRRRRRRRRR'

    sreq = req

    p = HttpParser()
    while not p.message_complete():
        c = p.parse(req, len(req))
        req = req[c:]

    print
    print p
    print

    req = 'GET /index.html HTTP/1.1\r\n'
    req+= 'User-Agent: Mozilla/WebKit 2.11\r\n'
    req+= 'Date: Never\r\n'
    req+= '\r\n'

    p = HttpParser()
    while not p.message_complete():
        c = p.parse(req, len(req))
        req = req[c:]

    print
    print p
    print

    print
    print 'Done.'
    print

if __name__ == '__main__':
    test()
