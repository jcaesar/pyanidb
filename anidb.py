#!/usr/bin/env python

import pyanidb, pyanidb.hash
import ConfigParser, optparse, os, sys, getpass, multihash

# Colors.

red    = lambda x: '\x1b[1;31m' + x + '\x1b[0m'
green  = lambda x: '\x1b[1;32m' + x + '\x1b[0m'
yellow = lambda x: '\x1b[1;33m' + x + '\x1b[0m'
blue   = lambda x: '\x1b[1;34m' + x + '\x1b[0m'

# Config.

config = {}
try:
	cp = ConfigParser.ConfigParser()
	cp.read(os.path.expanduser('~/.pyanidb.conf'))
	for option in cp.options('pyanidb'):
		config[option] = cp.get('pyanidb', option)
except:
	pass

# Options.

op = optparse.OptionParser()

op.add_option('-u', '--username', help = 'AniDB username.',
	action = 'store', dest = 'username', default = config.get('username'))
op.add_option('-p', '--password', help = 'AniDB password.',
	action = 'store', dest = 'password', default = config.get('password'))

op.add_option('-r', '--recursive', help = 'Recurse into directories.',
	action = 'store_true', dest = 'recursive', default = False)
op.add_option('-s', '--suffix', help = 'File suffix for recursive matching.',
	action = 'append', dest = 'suffix', default = config.get('suffix', '').split())

op.add_option('-i', '--identify', help = 'Identify files.',
	action = 'store_true', dest = 'identify', default = False)
op.add_option('-a', '--add', help = 'Add files to mylist.',
	action = 'store_true', dest = 'add', default = False)
op.add_option('-n', '--rename', help = 'Rename files.',
	action = 'store_true', dest = 'rename', default = False)
op.add_option('-f', '--format', help = 'Filename format.',
	action = 'store', dest = 'format', default = config.get('format'))

options, args = op.parse_args(sys.argv[1:])

# Defaults.

options.identify = options.identify or options.rename
options.login = options.add or options.identify
if not options.suffix:
	options.suffix = ['avi', 'ogm', 'mkv']
if not options.format:
	options.format = r'_[%group]_%anime_-_%epno%ver_[%CRC].%suf'

if options.login:
	if not options.username:
		options.username = raw_input('Username: ')
	if not options.password:
		options.passord = getpass.getpass()

# Input files.

files = []
for name in args:
	if not os.access(name, os.R_OK):
		print red('Invalid file:'), name
	elif os.path.isfile(name):
		files.append(name)
	elif os.path.isdir(name):
		if not options.recursive:
			print red('Is a directory:'), name
		else:
			for root, subdirs, subfiles in os.walk(name):
				subdirs.sort()
				subfiles.sort()
				files += [os.path.join(root, file) for file in subfiles if sum([file.endswith('.' + suffix) for suffix in options.suffix])]

if not files:
	print blue('Nothing to do.')
	sys.exit(0)

# Authorization.

if options.login:
	a = pyanidb.AniDB(options.username, options.password)
	try:
		a.auth()
		print blue('Logged in as user:'), options.username
	except pyanidb.AniDBUserError:
		print red('Invalid username/password.')
		sys.exit(1)
	except pyanidb.AniDBTimeout:
		print red('Connection timed out.')
		sys.exit(1)
	except pyanidb.AniDBError, e:
		print red('Fatal error:'), e
		sys.exit(1)

# Hashing.

hashed = unknown = 0

for filename, hash in pyanidb.hash.hash_files(files):
	size = os.path.getsize(filename)
	print blue('Hashed:'),  'ed2k://|file|%s|%d|%s|' % (filename, size, hash.ed2k())
	fid = (size, hash.ed2k())
	hashed += 1
	
	try:
		
		# Identify.
		
		if options.identify:
			info = a.get_file(fid, ('gtag', 'romaji', 'epno', 'state', 'epromaji', 'crc32', 'filetype'), True)
			fid = int(info['fid'])
			print green('Identified:'), '[%s] %s - %s - %s' % (info['gtag'], info['romaji'], info['epno'], info['epromaji'])
		
		# Renaming.
		
		if options.rename:
			s = options.format
			rename_data = {
				'group': info['gtag'],
				'anime': info['romaji'],
				'epno': info['epno'],
				'ver': {0: '', 4: 'v2', 8: 'v3', 16: 'v4', 32: 'v5'}[(int(info['state']) & 0x3c)],
				'crc': info['crc32'],
				'CRC': info['crc32'].upper(),
				'suf': info['filetype']}
			for name, value in rename_data.iteritems():
				s = s.replace(r'%' + name, value)
			if s[0] == '_':
				s = s[1:].replace(' ', '_')
			s = s.replace('/', '_')
			
			print yellow('Renaming to:'), s
			os.rename(filename, os.path.join(os.path.split(filename)[0], s))
		
		# Adding.
		
		if options.add:
			a.add_file(fid, retry = True)
			print green('Added to mylist.')
		
	except pyanidb.AniDBUnknownFile:
		print red('Unknown file.')
		unknown += 1

# Finished.

print blue('Hashed %d files%s.' % (hashed, (', %d unknown' % unknown) if unknown else ''))