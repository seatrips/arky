# -*- encoding: utf8 -*-
# © Toons
from . import api, mgmt, core, slots, ArkyDict, StringIO
import json, hashlib, binascii


class Wallet(object):

	# list of candidate a wallet can vote
	candidates = []
	# list of usernames already upvoted
	votes =   property(lambda obj: [d["username"] for d in api.Account.getVotes(obj.address).get("delegates", [])], None, None, "")
	# get total ARK in wallet
	balance = property(lambda obj: int(api.Account.getBalance(obj.address).get("balance", 0)), None, None, "")

	@staticmethod
	def open(filename):
		"""
"""
		in_ = open(filename, "r")
		serial = json.load(in_)
		in_.close()

		obj = Wallet()
		obj._Wallet__K1 = core.unserializeKeys(serial)
		Wallet.init(obj)
		Wallet.update(obj)
		return obj

	@staticmethod
	def create(secret):
		pass
# Account.openAccount = function(secretKey, callback) {
#   Api.post({
#     url: options.url + '/api/accounts/open',
#     form: {
#       secret: secretKey
#     },
#     json: true
#   }, callback);
# };

	def __init__(self, secret=None, secondSecret=None):
		if secret:
			self.__K1 = core.getKeys(secret=secret)
			self.init()
		self.update()

	def init(self):
		public_key = binascii.hexlify(self.__K1.public)
		self.publicKey = public_key.decode() if isinstance(public_key, bytes) else public_key
		self.address = core.getAddress(self.self.__K1)
		self.wif = self.__K1.wif

	def update(self):
		all_delegates = api.Delegate.getCandidates()
		object.__setattr__(self, "delegate", bool(len([d for d in all_delegates[:51] if d['publicKey'] == self.publicKey])))
		if self.delegate: object.__setattr__(self, "registered", True)
		else: object.__setattr__(self, "registered", bool(len([d for d in all_delegates[51:] if d['publicKey'] == self.publicKey])))
		Wallet.candidates = [d["username"] for d in all_delegates]

	def __setattr__(self, attr, value):
		if attr in["delegate", "registered"]:
			raise core.NotGrantedAttribute("%s can not be set through Wallet interface" % attr)
		object.__setattr__(self, attr, value)

	def sendArk(self, secret, amount, recipientId, **kw):
		tx = core.Transaction(amount=amount*100000000, recipientId=recipientId, **kw)
		return core.sendTransaction(secret, tx)

	def registerAsDelegate(self, secret, username):
		tx = core.Transaction(type=2)
		tx.asset.delegate = ArkyDict(username=username, publicKey=self.publicKey)
		return core.sendTransaction(secret, tx)

	def voteDelegate(self, secret, up=[], down=[]):
		votes = self.votes
		usernames = ['+'+c for c in up if c not in votes and c in Wallet.candidates] + \
		            ['-'+c for c in down if c in Wallet.candidates]
		if len(usernames):
			tx = core.Transaction(type=3, recipientId=self.address)
			tx.asset.votes = usernames
			return core.sendTransaction(secret, tx)

	def save(self, filename):
		in_ = open(filename, "w")
		json.dump(core.serializeKeys(self.__K1), in_, indent=2)
		in_.close()

#	registerSecondSingature(secondSign)
