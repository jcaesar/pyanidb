#!/usr/bin/env python

import ConfigParser, os, sys, thread, time, getpass, anidb, ed2k

num_threads = 0

def hash_file(name):
	if not os.access(name, os.R_OK):
		print 'Invalid file: %s' % (name)
		return
	size = os.stat(name).st_size
	hash = ed2k.file_hash(name)
	print 'Hashed: ed2k://|file|%s|%d|%s|' % (name, size, hash)
	return name, size, hash

def hash_thread(filelist, hashlist):
	global num_threads
	num_threads += 1
	try:
		while filelist:
			h = hash_file(filelist.pop(0))
			if h:
				hashlist.append(h)
	except IndexError:
		pass
	num_threads -= 1

def auth():
	try:
		c = ConfigParser.ConfigParser()
		c.read(os.path.expanduser('~/.pyanidb.conf'))
		username = c.get('auth', 'username')
		password = c.get('auth', 'password')
	except:
		username = raw_input('Username: ')
		password = getpass.getpass()
	return username, password

username, password = auth()

try:
	a = anidb.AniDB(username, password)
	#t = a.ping()
	#if t:
	#	print 'AniDB is reachable, %.3fs' % (t)
	#else:
	#	print 'AniDB is unreachable.'
	#	sys.exit(1)
	a.auth()
	print 'Logged in as user %s.' % (username)
	if a.new_version:
		print 'New version available.'
	
	filelist = sys.argv[1:]
	hashlist = []
	
	thread.start_new_thread(hash_thread, (filelist, hashlist))
		
	while hashlist or num_threads or filelist:
		if not hashlist:
			time.sleep(0.1)
			continue
		name, size, hash = hashlist.pop(0)
		try:
			while 1:
				try:
					a.add_hash(size, hash)
				except anidb.AniDBTimeout:
					print 'Connection timed out, retrying.'
					continue
				break
		except anidb.AniDBUnknownFile:
			print 'Unknown file: %s' % (name)
			continue
		print 'Added file: %s' % (name)
	print 'All operations finished.'
except anidb.AniDBUserError:
	print 'Invalid username/password.'
	sys.exit(1)
except anidb.AniDBTimeout:
	print 'Connection timed out.'
	sys.exit(1)
except anidb.AniDBError, e:
	print 'Fatal error:', e
	sys.exit(1)
