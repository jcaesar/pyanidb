import socket, time

protover = 3
client = 'pyanidb'
clientver = 7

storages = {
	'normal': 0,
	'corrupted': 1,
	'edited': 2,
	'ripped': 10,
	'dvd': 11,
	'vhs': 12,
	'tv': 13,
	'theatre': 14,
	'streamed': 15,
	'other': 100}
states = {
	'unknown': 0,
	'hdd': 1,
	'cd': 2,
	'deleted': 3,
	'shared': 4,
	'release': 5}

fcode = (
	'', 'aid', 'eid', 'gid', 'lid', '', '', '',
	'state', 'size', 'ed2k', 'md5', 'sha1', 'crc32', '', '',
	'dublang', 'sublang', 'quality', 'source', 'acodec', 'abitrate', 'vcodec', 'vbitrate',
	'vres', 'filetype', 'length', 'description', '', '', '', '')

acode = (
	'gname', 'gtag', '', '', '', '', '', '',
	'epno', 'epname', 'epromaji', 'epkanji', '', '', '', '',
	'eptotal', 'eplast', 'year', 'type', 'romaji', 'kanji', 'english', 'other',
	'short', 'synonym', 'category', '', '', '', '', '')

info = fcode + acode
info = dict([(info[i], 1 << i) for i in range(len(info)) if info[i]])

def static_vars(**kwargs):
	def decorate(func):
		for k in kwargs:
			setattr(func, k, kwargs[k])
		return func
	return decorate

class AniDBError(Exception):
	pass

class AniDBTimeout(AniDBError):
	pass

class AniDBLoginError(AniDBError):
	pass

class AniDBUserError(AniDBLoginError):
	pass

class AniDBReplyError(AniDBError):
	pass

class AniDBUnknownFile(AniDBError):
	pass

class AniDBNotInMylist(AniDBError):
	pass

class AniDBUnknownAnime(AniDBError):
	pass

class AniDBUnknownDescription(AniDBError):
	pass

class AniDB:
	def __init__(self, username, password, localport = 1234, server = ('api.anidb.info', 9000)):
		self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		self.sock.bind(('0.0.0.0', localport))
		self.sock.settimeout(10)
		self.username = username
		self.password = password
		self.server = server
		self.session = ''
		self.lasttime = 0
	
	def __del__(self):
		self.logout()
		self.sock.close()
	
	def newver_msg(self):
		print('New version available.')
	
	def retry_msg(self):
		print('Connection timed out, retrying.')
	
	def execute(self, cmd, args = None, retry = False):
		if not args:
			args = {}
		while 1:
			data = '{0} {1}\n'.format(cmd, '&'.join(['{0}={1}'.format(*a) for a in args.items()]))
			t = time.time()
			if t < self.lasttime + 2:
				time.sleep(self.lasttime + 2 - t)
			self.lasttime = time.time()
			self.sock.sendto(data.encode(), 0, self.server)
			try:
				data = self.sock.recv(8192).decode().split('\n')
			except socket.timeout:
				if retry:
					self.retry_msg()
				else:
					raise AniDBTimeout()
			else:
				break
		code, text = data[0].split(' ', 1)
		data = [line.split('|') for line in data[1:-1]]
		code = int(code)
		return code, text, data
	
	def ping(self):
		t = time.time()
		try:
			return self.execute('PING')[0] == 300 and time.time() - t or None
		except AniDBTimeout:
			return None
	
	def auth(self):
		code, text, data = self.execute('AUTH', {'user': self.username, 'pass': self.password, 'protover': protover, 'client': client, 'clientver': clientver, 'enc': 'utf-8'})
		if code in (200, 201):
			self.session = text.split(' ', 1)[0]
			if code == 201:
				self.newver_msg()
		elif code == 500:
			raise AniDBUserError()
		else:
			raise AniDBReplyError(code, text)
	
	def logout(self):
		if self.session:
			try:
				self.execute('LOGOUT', {'s': self.session})
				self.session = ''
			except AniDBError:
				pass
	
	def get_file(self, fid, info_codes, retry = False):
		try:
			size, ed2k = fid
			args = {'size': size, 'ed2k': ed2k}
		except TypeError:
			args = {'fid': fid}
		info_codes = list(info_codes)
		info_codes.sort(key = lambda x: info[x])
		info_code = sum([info[code] for code in info_codes])
		args.update({'s': self.session, 'fcode': info_code & 0xffffffff, 'acode': info_code >> 32})
		while 1:
			code, text, data = self.execute('FILE', args, retry)
			if code == 220:
				return dict([(name, data[0].pop(0)) for name in ['fid'] + info_codes])
			elif code == 320:
				raise AniDBUnknownFile()
			elif code in (501, 506):
				self.auth()
			else:
				raise AniDBReplyError(code, text)

	def get_mylist(self, fid, retry = False):
		try:
			size, ed2k = fid
			args = {'size': size, 'ed2k': ed2k}
		except TypeError:
			args = {'fid': fid}
		args.update({'s': self.session})
		while 1:
			code, text, data = self.execute('MYLIST', args, retry)
			if code == 221:
				return dict([(name, data[0].pop(0)) for name in 
					['lid', 'fid', 'eid', 'aid', 'gid', 'date', 'state', 'viewdate', 'storage', 'source', 'other', 'filestate']])
			elif code == 321:
				raise AniDBUnknownFile()
			elif code in (501, 506):
				self.auth()
			else:
				raise AniDBReplyError(code, text)
	@static_vars(try_edit=0)
	def add_file(self, fid = None, lid = None, state = None, viewed = False, source = None, storage = None, other = None, edit = None, retry = False):
		if lid is not None:
			args = {'lid': lid}
			edit = True
		else:
			try:
				size, ed2k = fid
				args = {'size': size, 'ed2k': ed2k}
			except TypeError:
				args = {'fid': fid}
		if viewed != None:
			args['viewed'] = int(bool(viewed))
		if source != None:
			args['source'] = source
		if storage != None:
			args['storage'] = storages[storage]
		if state != None:
			args['state'] = states[state]
		if other != None:
			args['other'] = other
		if edit is not None:
			args['edit'] = (1 if edit else 0)
		args['s'] = self.session
		while 1:
			if edit is None:
				if AniDB.add_file.try_edit:
					args['edit'] = 1
				else:
					args.pop('edit', 0)
			code, text, data = self.execute('MYLISTADD', args, retry)
			if code in (210, 311):
				return
			elif code == 310:
				AniDB.add_file.try_edit = True
				if edit is False:
					return
			elif code == 320:
				raise AniDBUnknownFile()
			elif code == 411:
				AniDB.add_file.try_edit = False
				if edit is True:
					raise AniDBNotInMylist()
			elif code in (501, 506):
				self.auth()
			else:
				raise AniDBReplyError(code, text)

	def get_anime(self, aid = None, aname = None, amask = None, retry = False):
		args = {}
		if not aid == None:
			args['aid'] = aid
		elif not aname == None:
			args['aname'] == aname
		else:
			raise TypeError('must set either aid or aname')

		args['amask'] = amask or '00'*7
		args['s'] = self.session

		while 1:
			code, text, data = self.execute('ANIME', args, retry)
			if code == 230:
				return data[0]
			elif code == 330:
				raise AniDBUnknownAnime()
			elif code in (501, 506):
				self.auth()
			else:
				raise AniDBReplyError(code, text)

	def get_animedesc(self, aid, retry = False):
		args = {'aid': aid, 'part': 0, 's': self.session}
		description = ''
		while 1:
			code, text, data = self.execute('ANIMEDESC', args, retry)
			if code == 233:
				curpart, maxpart, desc = data[0]
				description += desc
				if curpart == maxpart:
					return description
				else:
					args['part'] = int(curpart)+1
			elif code == 330:
				raise AniDBUnknownAnime()
			elif code == 333:
				raise AnidBUnknownDescription()
			elif code in (501, 506):
				self.auth()
			else:
				raise AniDBReplyError(code, text)
