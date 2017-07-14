#!/usr/bin/env python

#
# Utility to update SPN field of a SIM card
#
# Copyright (C) 2013  Alexander Chemeris <alexander.chemeris@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

from optparse import OptionParser
import os
import sys
import csv

from pySim.commands import SimCardCommands
from pySim.utils import h2b, swap_nibbles, rpad, dec_imsi, dec_iccid
from pySim.cards import card_autodetect


def load_sim_db(filename):
	sim_db = {}
	with open(filename, 'r') as f:
		reader = csv.reader(f, delimiter=' ')
		# Skip the header
		reader.next()
		for l in reader:
			sim_db[l[0]] = l
	return sim_db

def program_sim_card(card, sim_db):
	# Program the card
	print("Reading SIM card ...")

	# EF.ICCID
	(iccid, sw) = card.read_iccid()
	if sw != '9000':
		print("ICCID: Can't read, response code = %s" % (sw,))
		sys.exit(1)
	print("ICCID: %s" % (iccid))

	# Find SIM card keys in the DB
	sim_keys = sim_db.get(iccid+'F')
	if sim_keys == None:
		print("Can't find SIM card in the SIM DB.")
		sys.exit(1)

	# EF.SPN
	((name, hplmn_disp, oplmn_disp), sw) = card.read_spn()
	if sw == '9000':
		print("Service Provider Name:    %s" % name)
		print("  display for HPLMN       %s" % hplmn_disp)
		print("  display for other PLMN  %s" % oplmn_disp)
	else:
		print("Old SPN: Can't read, response code = %s" % (sw,))

	print("Programming...")

	# Enter ADM code to get access to writing SPN file
	sw = card.verify_adm1(h2b(sim_keys[6]))
	if sw != '9000':
		print("Fail to verify ADM code with result = %s" % (sw,))
		sys.exit(1)

	sw = card.update_spn(name, True, False)
	if sw != '9000':
		print("SPN: Fail to update with result = %s" % (sw,))
		sys.exit(1)

	# Verify EF.SPN
	((name, hplmn_disp, oplmn_disp), sw) = card.read_spn()
	if sw == '9000':
		print("Service Provider Name:    %s" % name)
		print("  display for HPLMN       %s" % hplmn_disp)
		print("  display for other PLMN  %s" % oplmn_disp)
	else:
		print("New SPN: Can't read, response code = %s" % (sw,))

	# Done for this card and maybe for everything ?
	print "Done !\n"


def parse_options():

	parser = OptionParser(usage="usage: %prog [options]")

	parser.add_option("-d", "--device", dest="device", metavar="DEV",
			help="Serial Device for SIM access [default: %default]",
			default="/dev/ttyUSB0",
		)
	parser.add_option("-b", "--baud", dest="baudrate", type="int", metavar="BAUD",
			help="Baudrate used for SIM access [default: %default]",
			default=9600,
		)
	parser.add_option("-p", "--pcsc-device", dest="pcsc_dev", type='int', metavar="PCSC",
			help="Which PC/SC reader number for SIM access",
			default=None,
		)
	parser.add_option("-s", "--sim-db", dest="sim_db_filename", type='string', metavar="FILE",
			help="filename of a SIM DB to load keys from (space searated)",
			default="sim_db.dat",
		)
	parser.add_option("--batch", dest="batch",
			help="Process SIM cards in batch mode - don't exit after programming and wait for the next SIM card to be inserted.",
			default=False, action="store_true",
		)

	(options, args) = parser.parse_args()

	if args:
		parser.error("Extraneous arguments")

	return options


if __name__ == '__main__':

	# Parse options
	opts = parse_options()

	# Connect to the card
	if opts.pcsc_dev is None:
		from pySim.transport.serial import SerialSimLink
		sl = SerialSimLink(device=opts.device, baudrate=opts.baudrate)
	else:
		from pySim.transport.pcsc import PcscSimLink
		sl = PcscSimLink(opts.pcsc_dev)

	# Create command layer
	scc = SimCardCommands(transport=sl)

	print("Loading SIM DB ...")
	sim_db = load_sim_db(opts.sim_db_filename)

	if opts.batch:
		print("Batch mode enabled! Press Ctrl-C to exit")

	# Loop once in non-batch mode and loop forever in batch mode
	first_run = True
	while first_run or opts.batch:
		print("Insert a SIM card to program...")
		sl.wait_for_card(newcardonly=not first_run)
		first_run = False

		card = card_autodetect(scc)
		if card is None:
			print("Card autodetect failed")
			continue
		print "Autodetected card type %s" % card.name

		program_sim_card(card, sim_db)
