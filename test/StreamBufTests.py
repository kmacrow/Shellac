
from shellac.server import StreamBuf

def test():
	print 'Testing StreamBuf...'

	s = StreamBuf()
	assert s.ready() == False
	assert s.closed() == False

	s.write('Hello')
	assert s.ready() == True

	assert s.read() == 'Hello'
	assert s.read() == 'Hello'

	s.ack(2)
	assert s.read() == 'llo'

	s.ack(3)
	assert s.read() == ''

	s.close()
	assert s.closed() == True

	assert s.buffer() == 'Hello'

	s.clear()
	assert s.buffer() == ''
	assert s.ready() == False
	assert s.closed() == False

	s.write('Romeo, oh Romeo.')
	s.close()
	s.ack(16)
	assert s.complete() == True
	

	print
	print 'Done.'
	print

if __name__ == '__main__':
	test()