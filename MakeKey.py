#!/usr/bin/env python3
# This script reads a template key file and creates the final
# key file for an experiment.
#
# Giuseppe Cimo' 16/02/2012
#

import sys, signal, re, os
from classmakekey import MakeKey
import mods
import complete
import time
from datetime import date
from subprocess import call
import numpy as np

# signal handler for catching CTRL-C
#
def signal_handler(signal, frame):
    print("\n\n\tYou presssed Ctrl+C! Bye!\n")
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

# slices a date string of form dd/mm/yyyy
def date_str(s):
    return s[0:2], s[3:5], s[6:10]

#############################
# PATH definition and checks.
#
kernel_path, meta_path, keyfile_path = mods.paths()

def path_check(paths):
    check_note = "Please define the env variable $MAKEKEY."
    if not os.path.isdir(paths):
        print(f"\n\tPath {paths} not found.\n\t{check_note}\n")
        sys.exit(0)

for paths in kernel_path, meta_path, keyfile_path:
    path_check(paths)

pis = {
    "pi1": {"piname": "Name1", "phone": "Phone1", "email": "Email1"},
    "pi2": {"piname": "Name2", "phone": "Phone2", "email": "Email2"},
}

# command line options and initialization
#
args = mods.parsing()

gaps = "y"
if args.nogap:
    gaps = "n"


def steps(step):
    if step[-1] == "s":
        timestep = float(step[:-1])
        duration = f"dur=00:{timestep}"
    elif step[-1] == "m":
        timestep = float(step[:-1]) * 60.0
        duration = f"dur={int(timestep/60)-1}:00 gap=1:00"
        if args.g:
            duration = f"dur={int(timestep/60)}:00 gap=0:30"
        elif args.a:
            duration = f"dur={int(timestep/60):02}:00 gap=0:00"
    else:
        # This catches a wrong input (only m or s are valid!)
        str(int(step)) + 1
    return timestep, duration


timestep = ""
duration = ""
satellite = ""
if args.s:
    timestep, duration = steps(args.s)
if args.r:
    satellite = "RadioAstron"
    if args.S:
        timestep, duration = steps("15s")
    if args.s:
        timestep, duration = steps(args.s)

if args.v:
    satellite = "Vex"
    gaps = "n"
    if args.S:
        timestep, duration = steps("20m")
    if args.s:
        timestep, duration = steps(args.s)

if args.m:
    satellite = "Mex"
    gaps = "n"
    if args.S:
        timestep, duration = steps("20m")
    if args.s:
        timestep, duration = steps(args.s)

if args.g:
    satellite = "Gaia"
    gaps = "n"
    if args.S:
        timestep, duration = steps("2m")
    if args.s:
        timestep, duration = steps(args.s)

if args.b:
    satellite = "BC_MPO"
    gaps = "n"
    if args.S:
        timestep, duration = steps("20m")
    if args.s:
        timestep, duration = steps(args.s)

if args.j:
    satellite = "Juno"
    gaps = "n"
    if args.S:
        timestep, duration = steps("20m")
    if args.s:
        timestep, duration = steps(args.s)

if args.o:
    satellite = "Perseverance"
    gaps = "n"
    if args.S:
        timestep, duration = steps("20m")
    if args.s:
        timestep, duration = steps(args.s)

if args.a:
    # if argument is a then it means an asteroid
    satellite = "asteroid"
    target = args.a
    #target = "2231937"
    #target = "-140947"
    gaps = "n"
    if args.S:
        timestep, duration = steps("1m")
    if args.s:
        timestep, duration = steps(args.s)

coordname = ""
if args.in_file:
    coordname = args.in_file

outfile = ""
if args.out_file:
    outfile = args.out_file

same_day = "y"
if args.long:
    same_day = "n"

kernels = "n"
if args.kernels:
    kernels = "y"
    mods.getKernels(kernel_path, satellite)

early_start = "n"
if args.time:
    early_start = "y"

correlation = "n"
if args.corr:
    correlation = "y"

# Scan length for correlating RA observations
# default 1 minute gap every 19 minutes.
scan_length = "19"
if args.scan:
    scan_length = args.scan

# Coordinates are calculated for the
# middle of the scan
scan_center = "y"
if args.nomid:
    scan_center = "n"

# Should I create a setup?
setup = "n"
if args.setup:
    setup_file = mods.setup()
    setup = "y"

pi = "pi1"
if args.pi:
    pi = args.pi.lower()

do_vex = "N"
if args.sched:
    do_vex = "Y"

# list of names for the satellites
#
list_vex = ["v", "vex"]
list_mex = ["m", "mex"]
list_ra = ["r", "ra", "radioastron"]
list_gaia = ["g", "gaia"]
list_mpo = ["b", "bc", "mpo", "bc_mpo"]
list_juno = ["j", "juno"]
list_m20 = ["o", "perseverance"]
list_ast = ["a", "asteroid"]

#
# end initialization!
#####################

###################
#                 #
# Here we start...#
#                 #
###################

print(f"")
print(f"\n   This program creates the key file for Sched.\n")
print(f"")

# ask for the observations date
#

while True:
    full_date = input("Insert observation date (dd/mm/yyyy) --> ")
    try:
        valid_date = time.strptime(full_date, "%d/%m/%Y")
        break
    except ValueError:
        print("Invalid date!")

day, month, year = date_str(full_date)
date = month + day
if same_day != "y":
    same_day = input("\nExperiment ends on the same day? (Y/n): ")
    if same_day == "" or same_day[0].lower() == "y":
        day2, month2, year2 = day, month, year
    else:
        while True:
            full_date2 = input("Insert ending date (dd/mm/yyyy) --> ")
            try:
                valid_date2 = time.strptime(full_date2, "%d/%m/%Y")
                break
            except ValueError:
                print("Invalid date!")

        day2, month2, year2 = date_str(full_date2)
else:
    day2, month2, year2 = day, month, year
    full_date2 = full_date

# ask for the satellite to observe
#
if satellite != "":
    sat = satellite
else:
    sat = input(
        "VenusExpress, MarsExpress, RadioAstron, Gaia, Juno or BepiColombo? (Mex/Vex/Ra/Gaia/Mpo/M20) --> "
    )

filename = f'{keyfile_path}keyfiles/default.key'

if sat.lower() in (list_vex):
    target = "VEX"
    if setup == "n":
        setup_file = f'{keyfile_path}Setups/vex.x'
    gaps = "n"
elif sat.lower() in (list_ast):
    #target = "2231937"
    #target = "-140947"
    #target = "54106739"
    target = "54134663"
    if setup == "n":
        setup_file = f'{keyfile_path}Setups/asteroid.x'
    gaps = "n"
elif sat.lower() in (list_mpo):
    target = "MPO"
    if setup == "n":
        setup_file = f'{keyfile_path}Setups/bc_mpo.x'
    gaps = "n"
elif sat.lower() in (list_m20):
    target = "Perseverance"
    if setup == "n":
        setup_file = f'{keyfile_path}Setups/mex.x'
    gaps = "n"
elif sat.lower() in (list_juno):
    target = "Juno"
    if setup == "n":
        setup_file = f'{keyfile_path}Setups/juno.x'
    gaps = "n"
elif sat.lower() in (list_mex):
    target = "MEX"
    if setup == "n":
        setup_file = f'{keyfile_path}Setups/mex.x'
    gaps = "n"
elif sat.lower() in (list_ra):
    target = "RADIOASTRON"
    if setup == "n":
        setup_file = f'{keyfile_path}Setups/ra.x'
    if gaps != "y":
        while True:
            gaps = input("Should I add gaps in scan list? (y/N): ")
            if gaps == "" or gaps[0].lower() == "n":
                gaps = "n"
                break
            elif gaps[0].lower() == "y":
                gaps = "y"
                break
            else:
                print("***Please answer with yes or no.***")
elif sat.lower() in (list_gaia):
    target = "GAIA"
    if setup == "n":
        setup_file = f'{keyfile_path}Setups/gaia.x'
    gaps = "n"
if outfile != "":
    outname = outfile
else:
    outname = input("Insert output key file --> ")

# ask for the time when the observations start
#
while True:
    start = input("Insert Spacecraft observations start time (hh:mm:ss) --> ")
    try:
        valid_date = time.strptime(start, "%H:%M:%S")
        break
    except ValueError:
        print("Invalid time!")
h1, m1, s1 = date_str(start)
if early_start == "y":
    while True:
        print("\nYou have to select a start time for the observation")
        start_early = input("Insert start time (hh:mm:ss) --> ")
        try:
            valid_date = time.strptime(start_early, "%H:%M:%S")
            break
        except ValueError:
            print("Invalid time!")
    he, me, se = date_str(start_early)

while True:
    ends = input("\nInsert Spacecraft observations end time (hh:mm:ss) --> ")
    try:
        valid_date = time.strptime(ends, "%H:%M:%S")
        break
    except ValueError:
        print("Invalid time!")

h2, m2, s2 = date_str(ends)

if scan_center == "y":
    m1 = int(float(m1) + float(timestep) / 120)
    m2 = int(float(m2) + float(timestep) / 120)

utctime_ini = f'{year}-{month}-{day}T{h1}:{m1:02}:{s1}'
utctime_end = f'{year2}-{month2}-{day2}T{h2}:{m2:02}:{s2}'

if timestep == "":
    while True:
        step = input("\nInsert time step (i.e. 20m or 15s)--> ")
        try:
            timestep, duration = steps(step)
            break
        except TypeError:
            print("Invalid time unit! Please use m for minutes and s for seconds.")

# start for the participant stations
#
stations = input("Insert participant stations (separated by commas) --> ")

while True:
    if pi.lower() in list(pis.keys()):
        break
    else:
        pi = input("Provide a valid PI (pi1 or pi2) --> ")
    pi = pi.lower()

output = open(outname, "a")

# ask for the file with the coordinates
#
if coordname != "":
    filecoords = coordname
else:
    filecoords = f'{target.lower()}_{utctime_ini}'
    filecoords = mods.pointing(meta_path, target, stations, utctime_ini, utctime_end, timestep, filecoords)

# In Summary:
#
print(f"\nSummary (please check if correct):")
print(f"-------------------------------\n")
print(f"PI is              : {pis.get(pi).get('piname')}")
print(f"Satellite          : {satellite.upper()}")
print(f"Using Coord file:  : {filecoords}")
print(f"Output file        : {outname}")
print(f"Observations start : {full_date}{start}")
print(f"Observations end   : {full_date2}{ends}")
print(f"Stations scheduled : {stations}")
if setup == "y":
    print(f"Ad-hoc setup used  : {setup_file} \n")
else:
    print(f"Setup file         : {setup_file} \n")

ok = input("Proceed? (Y/n): ")
if ok == "" or ok[0].lower() == "y":
    pass
else:
    print("OK... Bye!")
    sys.exit(1)

# run the sat module (Mex/Vex or ra/Gaia) to create
# the scan list with or without gaps
#
open(filecoords)
if sat.lower() in (list_vex + list_mex + list_gaia + list_mpo + list_juno + list_m20 + list_ast):
    source_file = mods.sched_ra(filecoords, duration)
    if correlation == "y":
        source_file = mods.sched_corr(filecoords, duration, sat)
        mods.scans_corr(sat, int(scan_length))
elif sat.lower() in (list_ra):
    source_file = mods.sched_ra(filecoords, duration)
    if correlation == "y":
        source_file = mods.sched_corr(filecoords, duration, sat)
        mods.scans_corr(sat, int(scan_length))
    if correlation == "n":
        mods.scans_ra(int(scan_length), int(timestep))
else:
    print(f"\n(Unknown satellite) Please check the output file: {outname}\n")
    sys.exit(1)

# Generate a table as a summary pre-observation (BlockObservationsStatus)
if (args.sumtb) and (sat.lower() in list_mex):
    from pysctrack import handler

    f = open("summary.table", "w")
    stat = re.split(r"\s*[,;]\s*", stations.strip())

    target = "Mars"
    observer = "147.439167,-42.805,0.043"
    startTime = f"{year}-{month}-{day} {start[0:5]}"
    stopTime = f"{year}-{month}-{day} {ends[0:5]}"

    (yy,mm,dd,HH,MM,rah,ram,ras,dech,decm,decs,delta,sot,sto) = handler.retrieve_jpleph(target, observer, startTime, stopTime)
    for ip in stat:
        f.write(
            "|   0   | {}.{}.{} | {}-{} |  {}  | {}      |   NNO   | {} | {} | {}  | S      | Scint                 |\n".format(year,month,day,start[0:5],ends[0:5],outname[0:5],ip,sot,sto,delta))
    
    f.close()

Schedule_File = MakeKey(
    pis.get(pi),
    year,
    month,
    day,
    sat,
    early_start,
    start,
    source_file,
    setup,
    setup_file,
    stations,
    keyfile_path,
)
for line in open(filename):
    lines = line
    for r in Schedule_File.list_checks:
        Schedule_File.re_lines(r)
        if Schedule_File.re.match(line):
            lines = Schedule_File.match_text(r, line)

    # write the strings into the new key file
    output.write(lines)

# read the file with the scan list created by the module
# and append the scan list at the bottom of the key file.
#
# append a dummy list in case of a file for correlation.
#
if correlation == "n":
    if gaps == "y":
        for listscan in open("list.scans"):
            output.write(listscan)
    elif gaps == "n":
        for listscan in open("list.sources"):
            output.write(listscan)
else:
    for listscan in open("list.corr"):
        output.write(listscan)

print(f"\nPlease check the output file: {outname} \n")
output.close()

if do_vex == "Y":
    call("$sched/bin/sched < %s" % outname, shell=True)
