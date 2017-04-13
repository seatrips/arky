# -*- encoding: utf-8 -*-
from arky.util import getArkPrice
from arky import cfg, api, wallet, HOME
import os, json, math, datetime

import sys
print(sys.version)

api.use("ark")

__daily_fees__ = 5./30 # daily server cost
__pythoners__ =   "AGvTiwbXykX6zpDMYUEBd9E5J818YmPZ4H"
__investments__ = "AUahWfkfr5J4tYakugRbfow7RWVTK35GPW"
__exchange__ =    "APREAB1cyRLGRrTBs97BEXNv1AwAPpSQkJ"
__tx_fee__ = cfg.__FEES__["send"]/100000000.

# screen command line
from optparse import OptionParser
parser = OptionParser()
parser.set_usage("usage: %prog arg1 ....argN [options]")
parser.add_option("-s", "--secret", dest="secret", help="wallet secret you want to use")
parser.add_option("-k", "--keyring", dest="keyring", help="wallet file you want to use")
(options, args) = parser.parse_args()

def ARK2USD(value): return value * getArkPrice("usd")
def USD2ARK(value): return value / getArkPrice("usd")

if len(args) == 1 and os.path.exists(args[0]):
	in_ = open(args[0])
	content = in_.read()
	in_.close()
	conf = json.loads(content.decode() if isinstance(content, bytes) else content)
	wlt = wallet.Wallet(conf["forging"]["secret"][0])
elif options.secret:
	wlt = wallet.Wallet(options.secret)
elif options.keyring:
	wlt = wallet.open(options.keyring)
else:
	raise Exception("Can not do something for now !")

print(wlt.address)

logfile = os.path.join(HOME, "Payment", "%s.pay" % datetime.datetime.now().strftime("%y-%m-%d"))
try: os.makedirs(os.path.dirname(logfile))
except: pass
log = open(logfile, "w")

wlt.update()
if wlt.delegate["rate"] > 51:
	log.write("%s is not an active delegate right now !" % wlt.delegate["username"])
	log.close()
	raise Exception("%s is not an active delegate right now !" % wlt.delegate["username"])
	
elif wlt.balance < 200:
	log.write("%s does not have more than 200 Arks !" % wlt.delegate["username"])
	log.close()
	raise Exception("%s does not have more than 200 Arks !" % wlt.delegate["username"])

# 
def _blacklistContributors(contributors, lst):
	share = 0.
	for addr,ratio in [(a,r) for a,r in contributors.items() if a in lst]:
		share += contributors.pop(addr)
	share /= len(contributors)
	for addr,ratio in [(a,r) for a,r in contributors.items()]:
		contributors[addr] += share
	return contributors

def _floorContributors(contributors, min_ratio):
	return _blacklistContributors(contributors, [a for a,r in contributors.items() if r < min_ratio])

def _ceilContributors(contributors, max_ratio):
	nb_cont = len(contributors)
	test = 1./nb_cont
	if test >= max_ratio:
		return dict([(a,test) for a in contributors])
	else:
		share = 0
		nb_cuts = 0
		for addr,ratio in contributors.items():
			diff = ratio - max_ratio
			if diff > 0:
				share += diff
				nb_cuts += 1
				contributors[addr] = max_ratio
		share /= (nb_cont - nb_cuts)
		for addr in [a for a in contributors if contributors[a] <= (max_ratio-share)]:
			contributors[addr] += share
		return contributors

# get contributors and make a selection
contributors = wallet.getVoterContribution(wlt)
# contributors = _floorContributors(contributors, 5./100)
contributors = _ceilContributors(contributors, 70./100)

amount = wlt.balance
log.write("delegate amount : A%.8f\n" % amount)
header = ["Date", datetime.datetime.now(), ""]
content = ["ARK amount", amount, ""]

# ARK to be exchanged for node fees payment
node_invest = 2*math.ceil(USD2ARK(__daily_fees__*7)) - __tx_fee__
log.write("node fees       : A%.8f\n" % node_invest)
header.append("Node fees")
content.append(node_invest)
wlt.sendArk(node_invest, __exchange__)

# part to be distributed
share = amount - node_invest
log.write("Share           : A%.8f\n" % share)

pythoners = 0.10*share - __tx_fee__
log.write("For pythoners   : A%.8f\n" % pythoners)
header.append("Pythoners")
content.append(pythoners)
wlt.sendArk(pythoners, __pythoners__)

investments = 0.65*share - __tx_fee__
log.write("For investments : A%.8f\n" % investments)
header.append("Investments")
content.append(investments)
wlt.sendArk(investments, __investments__)

# relays = 0.05*share
# log.write("For relay nodes : A%.8f\n" % relays)
# relays = api.Delegate.getCandidates()[52:]
# vote_sum = max(1, sum([float(d.get("vote", 0.)) for d in relays]))
# dist, count = dict([(r["address"], float(r.get("vote", 0.))/vote_sum) for r in relays]), 0
# for d,ratio in dist.items():
# 	amount = (relays * ratio) - __tx_fee__
# 	if amount > 0.:
# 		wlt.sendArk(amount, d, vendorField="Arky contribution for relay nodes")
# 		count += 1
# 	log.write("%s : A%.8f\n" % (addr, amount))
# header.append("Relay nodes (%d)" % count)
# content.append(relays)

voters = 0.25*share
log.write("For voters      : A%.8f\n" % voters)

log.write("\nArky contributors :\n")
header.append("")
content.append("")
for addr,ratio in contributors.items():
	amount = voters*ratio - __tx_fee__
	if amount > 0.:
		wlt.sendArk(amount, addr, vendorField="Arky weekly refund. Thanks for you contributors !")
	log.write("%s : A%.8f\n" % (addr, amount))
	header.append(addr)
	content.append(amount)

out = open("accounting.csv", "a")
out.write(";".join(["%s"%e for e in header])  + "\n")
out.write(";".join(["%s"%e for e in content]) + "\n")
out.close()

wallet.mgmt.join()
log.close()
