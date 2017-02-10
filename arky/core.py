# -*- encoding: utf8 -*-
# © Toons

from ecdsa.keys import SigningKey
from ecdsa.util import sigencode_der
from ecdsa.curves import SECP256k1

from . import __PY3__, StringIO, ArkyDict, cfg, slots
import base58, struct, hashlib, binascii, requests, json


# define core exceptions 
class NotGrantedAttribute(Exception): pass
class NoSecretDefinedError(Exception): pass
class NoSenderDefinedError(Exception): pass
class NotSignedTransactionError(Exception): pass
class StrictDerSignatureError(Exception): pass


# byte as int conversion
basint = (lambda e:e) if __PY3__ else \
         (lambda e:ord(e))
# read value binary data from buffer
unpack = lambda fmt, fileobj: struct.unpack(fmt, fileobj.read(struct.calcsize(fmt)))
# write value binary data into buffer
pack =  lambda fmt, fileobj, value: fileobj.write(struct.pack(fmt, *value))
# write bytes as binary data into buffer
pack_bytes = (lambda f,v: pack("<"+"%ss"%len(v), f, (v,))) if __PY3__ else \
             (lambda f,v: pack("<"+"s"*len(v), f, v))


def use(net="testnet"):
	"""
select ARK net to use
>>> use("ark") # use testnet
>>> cfg.__NET__
'mainnet'
>>> use("bitcoin2") # use testnet
Traceback (most recent call last):
...
Exception: bitcoin2 net properties not known
"""
	if net == "testnet":
		cfg.__NET__ = "testnet"
		cfg.__URL_BASE__ = "http://node1.arknet.cloud:4000"
		cfg.__HEADERS__.update({
			'Content-Type' : 'application/json; charset=utf-8',
			'os'           : 'arkwalletapp',
			'version'      : '0.5.0',
			'port'         : '1',
			'nethash'      : "8b2e548078a2b0d6a382e4d75ea9205e7afc1857d31bf15cc035e8664c5dd038"
		})
		cfg.__NETWORK__.update({
			"messagePrefix" : b"\x18Ark Testnet Signed Message:\n",
			"bip32"         : ArkyDict(public=0x043587cf, private=0x04358394),
			"pubKeyHash"    : b"\x52",
			"wif"           : b"\xef",
		})
	else:
		cfg.__NET__ = "mainnet"
		cfg.__URL_BASE__ = "http://node1.arknet.cloud:4000"
		cfg.__HEADERS__.update({
			'Content-Type' : 'application/json; charset=utf-8',
			'os'           : 'arkwalletapp',
			'version'      : '0.5.0',
			'port'         : '1',
			'nethash'      : "ed14889723f24ecc54871d058d98ce91ff2f973192075c0155ba2b7b70ad2511"
		})
		cfg.__NETWORK__.update({
			"messagePrefix" : b"\x18Ark Signed Message:\n",
			"bip32"         : ArkyDict(public=0x0488b21e, private=0x0488ade4),
			"pubKeyHash"    : b"\x17",
			"wif"           : b"\xaa"
		} if net == "ark" else {
			"messagePrefix" : b"\x18Bitcoin Signed Message:\n",
			"bip32"         : ArkyDict(public=0x0488b21e, private=0x0488ade4),
			"pubKeyHash"    : b"\x00",
			"wif"           : b"\x80"
		} if net == "bitcoin" else {
			"messagePrefix" : b"\x19Litecoin Signed Message:\n",
			"bip32"         : ArkyDict(public=0x019da462, private=0x019d9cfe),
			"pubKeyHash"    : b"\x30",
			"wif"           : b"\xb0"
		} if net == "litecoin" else {
			"messagePrefix" : b"",
			"bip32"         : ArkyDict(public=0, private=0),
			"pubKeyHash"    : b"",
			"wif"           : b""
		})
 
	if cfg.__NETWORK__.wif == b"":
		raise Exception("%s net properties not known" % net)

# initailize testnet by default
use("testnet")


def _compressEcdsaPublicKey(pubkey):
	first, last = pubkey[:32], pubkey[32:]
	# check if last digit of second part is even (2%2 = 0, 3%2 = 1)
	even = not bool(basint(last[-1]) % 2)
	return (b"\x02" if even else b"\x03") + first


def getKeys(secret="passphrase", seed=None, network=None):
	"""
Generate keyring containing `network`, `public` and `private` key as attribute.
`secret` or `seed` have to be provided, if `network` is not, `cfg.__NETWORK__` is
automatically selected.

Keyword arguments:
secret (str or bytes) -- a human pass phrase
seed (byte)           -- a sha256 sequence bytes
network (object)      -- a python object

Returns ArkyDict

>>> binascii.hexlify(getKeys("secret").public)
b'03a02b9d5fdd1307c2ee4652ba54d492d1fd11a7d1bb3f3a44c4a05e79f19de933'
"""
	network = cfg.__NETWORK__ if network == None else network # use cfg.__NETWORK__ network by default
	seed = hashlib.sha256(secret.encode("utf8") if not isinstance(secret, bytes) else secret).digest() if not seed else seed

	keys = ArkyDict()
	# save wallet address
	keys.wif = getWIF(seed, network)
	# save network option
	keys.network = network
	# generate signing and verifying object and public key
	keys.signingKey = SigningKey.from_secret_exponent(int(binascii.hexlify(seed), 16), SECP256k1, hashlib.sha256)
	keys.checkingKey = keys.signingKey.get_verifying_key()
	keys.public = _compressEcdsaPublicKey(keys.checkingKey.to_string())

	return keys


def serializeKeys(keys):
	"""
Serialize `keys`.

Argument:
keys (ArkyDict) -- keyring returned by `getKeys`

Returns ArkyDict

>>> serializeKeys(getKeys("secret"))['signingKey']
'2d2d2d2d2d424547494e2045432050524956415445204b45592d2d2d2d2d0a4d485143415145454943753444\
564e374861506a69394d4459617146566f6139344f724e63574c2b39714a66365876314a364a626f416347425\
375424241414b0a6f555144516741456f4375645839305442384c75526c4b36564e5353306630527039473750\
7a7045784b42656566476436544f5353714a5941476d564b7746410a3249336948445a2b354b3938537042754\
64a6a7943726a324c6b777049513d3d0a2d2d2d2d2d454e442045432050524956415445204b45592d2d2d2d2d\
0a'
"""
	skeys = ArkyDict()
	sk = binascii.hexlify(keys.signingKey.to_pem())
	skeys.signingKey = sk.decode() if isinstance(sk, bytes) else sk
	skeys.wif = keys.wif
	return skeys


def unserializeKeys(serial, network=None):
	"""
Unserialize `serial`.

Argument:
keys (ArkyDict) -- serialized keyring returned by `serializeKeys`

Returns ArkyDict ready to be used as keyring

>>> binascii.hexlify(unserializeKeys({
...	'wif': 'SB3BGPGRh1SRuQd52h7f5jsHUg1G9ATEvSeA7L5Bz4qySQww4k7N',
...	'signingKey': '2d2d2d2d2d424547494e2045432050524956415445204b45592d2d2d2d2d0a4d485143\
415145454943753444564e374861506a69394d4459617146566f6139344f724e63574c2b39714a66365876314\
a364a626f416347425375424241414b0a6f555144516741456f4375645839305442384c75526c4b36564e5353\
3066305270394737507a7045784b42656566476436544f5353714a5941476d564b7746410a3249336948445a2\
b354b393853704275464a6a7943726a324c6b777049513d3d0a2d2d2d2d2d454e442045432050524956415445\
204b45592d2d2d2d2d0a'}).public)
b'03a02b9d5fdd1307c2ee4652ba54d492d1fd11a7d1bb3f3a44c4a05e79f19de933'
"""
	keys = ArkyDict()
	keys.network = cfg.__NETWORK__ if network == None else network # use cfg.__NETWORK__ network by default
	keys.signingKey = SigningKey.from_pem(binascii.unhexlify(serial["signingKey"]))
	keys.checkingKey = keys.signingKey.get_verifying_key()
	keys.public = _compressEcdsaPublicKey(keys.checkingKey.to_string())
	keys.wif = serial["wif"]
	return keys


def getAddress(keys):
	"""
Computes ARK address from keyring.

Argument:
keys (ArkyDict) -- keyring returned by `getKeys`

Returns str

>>> getAddress(getKeys("secret"))
'a3T1iRdHFt35bKY8RX1bZBGbenmmKZ12yR'
"""
	network = keys.network
	ripemd160 = hashlib.new('ripemd160', keys.public).digest()[:20]
	seed = network.pubKeyHash + ripemd160
	return base58.b58encode_check(seed)


def getWIF(seed, network):
	"""
Computes WIF address from keyring.

Argument:
seed (bytes)     -- a sha256 sequence bytes
network (object) -- a python object

Returns str

>>> getWIF(hashlib.sha256("secret".encode("utf8")).digest(), cfg.__NETWORK__)
'cP3giX8Vmcev97Y5BvMH1kPteesGk3AQ9vd9ifyis5r5sFiV8H26'
"""
	network = network
	compressed = network.get("compressed", True)
	seed = network.wif + seed[:32] + (b"\x01" if compressed else b"")
	return base58.b58encode_check(seed)


def getBytes(transaction):
	"""
Computes transaction object as bytes data.

Argument:
transaction (arky.core.Transaction) -- transaction object

Returns sequence bytes
>>> binascii.hexlify(getBytes(Transaction(amount=100000000, secret="secret", timestamp=22\
030978, recipientId=getAddress(getKeys("recipient")))))
b'00822a500103a02b9d5fdd1307c2ee4652ba54d492d1fd11a7d1bb3f3a44c4a05e79f19de93352016190701\
176bf429e8c9e0a89d13069d072e1700000000000000000000000000000000000000000000000000000000000\
000000000000000000000000000000000000000000000000000000000000000000000000e1f50500000000809\
6980000000000'
"""
	buf = StringIO() # create a buffer

	# write type as byte in buffer
	pack("<b", buf, (transaction.type,))
	# write timestamp as integer in buffer (see if uint is better)
	pack("<i", buf, (int(transaction.timestamp),))
	# write senderPublicKey as bytes in buffer
	try:
		pack_bytes(buf, transaction.senderPublicKey)
	# raise NoSenderDefinedError if no sender defined
	except AttributeError:
		raise NoSenderDefinedError("%r does not belong to any ARK account" % transaction)

	if hasattr(transaction, "requesterPublicKey"):
		pack_bytes(buf, transaction.requesterPublicKey)

	if hasattr(transaction, "recipientId"):
		# decode reciever adress public key
		recipientId = base58.b58decode_check(transaction.recipientId)
	else:
		# put a blank
		recipientId = b"\x00"*21
	pack_bytes(buf,recipientId)

	if hasattr(transaction, "vendorField"):
		# put vendor field value (64 bytes limited)
		n = min(64, len(transaction.vendorField))
		vendorField = transaction.vendorField[:n].encode() + b"\x00"*(64-n)
	else:
		# put a blank
		vendorField = b"\x00"*64
	pack_bytes(buf, vendorField)

	# write amount value
	pack("<Q", buf, (transaction.amount,))
	pack("<Q", buf, (transaction.fee,))

	# more test to confirm the good bytification of type 1 to 4...
	typ  = transaction.type
	if typ == 1 and "signature" in transaction.asset:
		pack_bytes(buf, transaction.asset.signature)
	elif typ == 2 and "delegate" in transaction.asset:
		pack_bytes(buf, transaction.asset.delegate.username.encode())
	elif typ == 3 and "votes" in transaction.asset:
		pack_bytes(buf, ("".join(transaction.asset.votes)).encode())
	elif typ == 4 and "multisignature" in transaction.asset:
		pack("<b", buf, (transaction.asset.multisignature.min,))
		pack("<b", buf, (transaction.asset.multisignature.lifetime,))
		pack_bytes(buf, ("".join(transaction.asset.multisignature.keysgroup)).encode())

	# if there is a signature
	if hasattr(transaction, "signature"):
		pack_bytes(buf, transaction.signature)
	
	# if there is a second signature
	if hasattr(transaction, "signSignature"):
		pack_bytes(buf, transaction.signSignature)

	result = buf.getvalue()
	buf.close()
	return result.encode() if not isinstance(result, bytes) else result


def checkStrictDER(sig):
	"""
https://github.com/bitcoin/bips/blob/master/bip-0066.mediawiki#der-encoding-reference
Check strict DER signature compliance.

Argument:
sig (bytes) -- signature sequence bytes

Raises StrictDerSignatureError exception or return sig

>>> sig = checkStrictDER(binascii.unhexlify('3044022003e6f032a119ad552804792822d84bbd34b5\
8fe710bca59f6ca4bb332404957402207d761b265ce8405ae7f1fceac56ebae6eae010ad7524aff38eef6167c\
3e916cb'))
>>> binascii.hexlify(sig)
b'3044022003e6f032a119ad552804792822d84bbd34b58fe710bca59f6ca4bb332404957402207d761b265ce\
8405ae7f1fceac56ebae6eae010ad7524aff38eef6167c3e916cb'
>>> sig = checkStrictDER(binascii.unhexlify('3044122003e6f032a119ad552804792822d84bbd34b5\
8fe710bca59f6ca4bb332404957402207d761b265ce8405ae7f1fceac56ebae6eae010ad7524aff38eef6167c\
3e916cb'))
Traceback (most recent call last):
...
arky.core.StrictDerSignatureError: R element is not an integer
"""
	sig_len = len(sig)
	# Extract the length of the R element.
	r_len = basint(sig[3])
	# Extract the length of the S element.
	s_len = basint(sig[5+r_len])

	# Minimum and maximum size constraints.
	if 8 > sig_len > 72:
		raise StrictDerSignatureError("bad signature size (<8 or >72)")
	# A signature is of type 0x30 (compound).
	if basint(sig[0]) != 0x30:
		raise StrictDerSignatureError("A signature is not of type 0x30 (compound)")
	# Make sure the length covers the entire signature.
	if basint(sig[1]) != (sig_len - 2):
		raise StrictDerSignatureError("length %d does not covers the entire signature (%d)" % (sig[1], sig_len))
	# Make sure the length of the S element is still inside the signature.
	if (5 + r_len) >= sig_len:
		raise StrictDerSignatureError("S element is not inside the signature")
	# Verify that the length of the signature matches the sum of the length of the elements.
	if (r_len + s_len + 6) != sig_len:
		raise StrictDerSignatureError("signature length does not matches sum of the elements")
	# Check whether the R element is an integer.
	if basint(sig[2]) != 0x02:
		raise StrictDerSignatureError("R element is not an integer")
	# Zero-length integers are not allowed for R.
	if r_len == 0:
		raise StrictDerSignatureError("Zero-length is not allowed for R element")
	# Negative numbers are not allowed for R.
	if basint(sig[4]) & 0x80:
		raise StrictDerSignatureError("Negative number is not allowed for R element")
	# Null bytes at the start of R are not allowed, unless R would otherwise be interpreted as a negative number.
	if r_len > 1 and basint(sig[4]) == 0x00 and not basint(sig[5]) & 0x80:
		raise StrictDerSignatureError("Null bytes at the start of R element is not allowed")
	# Check whether the S element is an integer.
	if basint(sig[r_len+4]) != 0x02:
		raise StrictDerSignatureError("S element is not an integer")
	# Zero-length integers are not allowed for S.
	if s_len == 0:
		raise StrictDerSignatureError("Zero-length is not allowed for S element")
	# Negative numbers are not allowed for S.
	if basint(sig[r_len+6]) & 0x80:
		raise StrictDerSignatureError("Negative number is not allowed for S element")
	# Null bytes at the start of S are not allowed, unless S would otherwise be interpreted as a negative number.
	if s_len > 1 and basint(sig[r_len+6]) == 0x00 and not basint(sig[r_len+7]) & 0x80:
		raise StrictDerSignatureError("Null bytes at the start of S element is not allowed")
	return sig


class Transaction(object):
	r'''
Transaction object is the core of the API. This object is a container with smart
behaviour according to attribute value that are settled in. 

Attributes that can be set using object interface :
type               (int)
amount             (int)
timestamp          (float)
asset              (ArkyDict)
secret             (str)
vendorField        (str)
recipientId        (str)
requesterPublicKey (str)

Public address attribute can only be set by secret passphrase, there are three way to do it:
>>> import arky.core as core
>>> tx1 = core.Transaction(secret="secret") # first way
>>> tx1.address
'a3T1iRdHFt35bKY8RX1bZBGbenmmKZ12yR'
>>> tx2 = core.Transaction()
>>> tx2.address = 'a3T1iRdHFt35bKY8RX1bZBGbenmmKZ12yR'
Traceback (most recent call last):
  File "<stdin>", line 1, in <module>
  File "C:\Users\Bruno\Python\../GitHub/arky\arky\core.py", line 268, in __setattr__
    self.amount = kwargs.pop("amount", 0)
arky.core.NotGrantedAttribute: address attribute can not be set using object interface
>>> tx2.secret = 'secret' # second way
>>> tx2.address
'a3T1iRdHFt35bKY8RX1bZBGbenmmKZ12yR'
>>> tx3 = core.Transaction()
>>> tx3.sign('secret') # third way
>>> tx3.address
'a3T1iRdHFt35bKY8RX1bZBGbenmmKZ12yR'

Note that if secret is set, signature is done so:
>>> tx1.sign()
>>> tx2.sign()

If no secret defined:
>>> bad_tx = core.Transaction()
>>> bad_tx.sign()
Traceback (most recent call last):
...
arky.core.NoSecretDefinedError: No secret defined for <0.00000000 ARK unsigned transaction type 0 from "No one" to "No one">
'''
	# here are attribute that can be set through object interface
	attr = ["type", "amount", "timestamp", "asset", "vendorField", "secret", "recipientId", "requesterPublicKey"]
	senderPublicKey = property(lambda obj:obj.key_one.public, None, None, "alias for public key, read-only attribute")

	def __init__(self, **kwargs):
		"""
>>> Transaction(amount=100000000, secret="secret")
<1.00000000 ARK unsigned transaction type 0 from a3T1iRdHFt35bKY8RX1bZBGbenmmKZ12yR to "No one">
"""
		# the four minimum attributes that defines a transaction
		self.type = kwargs.pop("type", 0)
		self.amount = kwargs.pop("amount", 0)
		self.timestamp = slots.getTime() - 100 # get backward 100s to avoid error:Invalid transaction timestamp
		self.asset = kwargs.pop("asset", ArkyDict())
		for attr,value in kwargs.items():
			setattr(self, attr, value)

	def __setattr__(self, attr, value):
		if attr not in Transaction.attr:
			raise NotGrantedAttribute("%s attribute can not be set using object interface" % attr)
		# if one of granted attribute is modified, it change signature in-fine
		# so unsign transaction to delete id, signature and signSignature
		self._unsign()
		if attr == "secret":
			# secret is not stored
			# associated ecdsa object and ARK address are instead
			keys = getKeys(value)
			object.__setattr__(self, "key_one", keys)
			object.__setattr__(self, "address", getAddress(keys))
		elif attr == "secondSecret":
			# second secret is not stored
			# associated ecdsa object is instead
			object.__setattr__(self, "key_two", getKeys(value))
		elif attr == "type":
			# when doing `<object>.type = value` automaticaly set the associated fees
			if value == 0:   object.__setattr__(self, "fee", cfg.__FEES__.send)
			elif value == 1: object.__setattr__(self, "fee", cfg.__FEES__.secondsignature)
			elif value == 2: object.__setattr__(self, "fee", cfg.__FEES__.delegate)
			elif value == 3: object.__setattr__(self, "fee", cfg.__FEES__.vote)
			elif value == 4: object.__setattr__(self, "fee", cfg.__FEES__.multisignature)
			elif value == 5: object.__setattr__(self, "fee", cfg.__FEES__.dapp)
			object.__setattr__(self, attr, value)
		else:
			object.__setattr__(self, attr, value)

	def __del__(self):
		if hasattr(self, "key_one"): delattr(self, "key_one")
		if hasattr(self, "key_two"): delattr(self, "key_two")

	def __repr__(self):
		return "<%(amount).8f ARK %(signed)s transaction type %(type)d from %(from)s to %(to)s>" % {
			"signed": "signed" if hasattr(self, "signature") else \
			          "double-signed" if hasattr(self, "signSignature") else \
			          "unsigned",
			"type": self.type,
			"amount": self.amount//100000000,
			"from": getattr(self, "address", '"No one"'),
			"to": getattr(self, "recipientId", '"No one"')
		}

	def _unsign(self):
		if hasattr(self, "signature"): delattr(self, "signature")
		if hasattr(self, "signSignature"): delattr(self, "signSignature")
		if hasattr(self, "id"): delattr(self, "id")

	def sign(self, secret=None):
		if secret != None:
			self.secret = secret
		elif not hasattr(self, "key_one"):
			raise NoSecretDefinedError("No secret defined for %r" % self)
		self._unsign()
		stamp = getattr(self, "key_one").signingKey.sign_deterministic(getBytes(self), hashlib.sha256, sigencode_der)
		object.__setattr__(self, "signature", checkStrictDER(stamp))
		object.__setattr__(self, "id", hashlib.sha256(getBytes(self)).digest())

	def seconSign(self, secondSecret=None):
		if not hasattr(self, "signature"):
			raise NotSignedTransactionError("%r must be signed first" % self)
		if secondSecret != None:
			self.secondSecret = secondSecret
		elif not hasattr(self, "key_two"):
			raise NoSecretDefinedError("No second secret defined for %r" % self)
		if hasattr(self, "signSignature"): delattr(self, "signSignature")
		stamp = getattr(self, "key_two").signingKey.sign_deterministic(getBytes(self), hashlib.sha256, sigencode=sigencode_der)
		object.__setattr__(self, "signSignature", checkStrictDER(stamp))
		object.__setattr__(self, "id", hashlib.sha256(getBytes(self)).digest())

	def serialize(self):
		"""
>>> sorted(Transaction(amount=100000000, secret="secret", timestamp=22030978).serialize()\
.items(), key=lambda e:e[0])
[('amount', 100000000), ('asset', {}), ('fee', 10000000), ('senderPublicKey', '03a02b9d5f\
dd1307c2ee4652ba54d492d1fd11a7d1bb3f3a44c4a05e79f19de933'), ('timestamp', 22030978), ('ty\
pe', 0)]
"""
		data = ArkyDict()
		for attr in [a for a in [
			"id", "timestamp", "type", "fee", "amount", 
			"recipientId", "senderPublicKey", "requesterPublicKey", "vendorField",
			"asset", "signature", "signSignature"
		] if hasattr(self, a)]:
			value = getattr(self, attr)
			if isinstance(value, bytes) and attr not in ["recipientId", "vendorField"]:
				value = binascii.hexlify(value)
				if isinstance(value, bytes):
					value = value.decode()
			elif attr in ["amount", "timestamp", "fee"]:
				value = int(value)
			setattr(data, attr, value)
		return data


def sendTransaction(secret, transaction, n=10, secondSignature=None):
	attempt = 0
	while n: # yes i know, it is brutal :)
		n -= 1
		attempt += 1
		# 1s shift timestamp for hash change
		transaction.timestamp += 1
		transaction.sign(secret)
		if secondSignature:
			transaction.seconSign(secondSignature)
		result = ArkyDict(json.loads(requests.post(
			cfg.__URL_BASE__+"/peer/transactions",
			data=json.dumps({"transactions": [transaction.serialize()]}),
			headers=cfg.__HEADERS__
		).text))
		if result["success"]:
			break

	result.attempt = attempt
	result.transaction = "%r" % transaction
	cfg.__TXLOG__.put(result)
	return result


def sendMultiple(secret, *transactions, **kw):
	result = ArkyDict()
	for transaction in transactions:
		sendTransaction(secret, transaction, n=kw.get("n", 10), secondSignature=kw.get('secondSinature', None))
	return result
