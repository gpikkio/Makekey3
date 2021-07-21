import os, re, sys
import datetime
import argparse


def parsing():
    parser = argparse.ArgumentParser(description='Script to create a .key file for spacecraft observations.', epilog='For bug and feature requests, please contact Giuseppe Cimo\': cimo@jive.nl\n')
    parser.add_argument('in_file', help='input coordinates file.', nargs='?')
    parser.add_argument('out_file', help='output key file.')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('-r', help='Satellite is RadioAstron', action="store_true")
    group.add_argument('-v', help='Satellite is Vex', action="store_true")
    group.add_argument('-m', help='Satellite is Mex', action="store_true")
    group.add_argument('-g', help='Satellite is Gaia', action="store_true")
    group.add_argument('-b', help='Satellite is BEPICOLOMBO', action="store_true")
    group.add_argument('-j', help='Satellite is Juno', action="store_true")
    group.add_argument('-o', help='Satellite is M20', action="store_true")
    group.add_argument('-a', help='Satellite is an asteroid', action="store_true")
#    group2.add_argument('-M', help='\'mix\' setup single pol', action="store_true")
#    group2.add_argument('-d', help='\'mix\' setup dual pol', action="store_true")
    parser.add_argument('--long', help='Experiment finishing another day', action="store_true")
    parser.add_argument('--nogap', help='No gap for RA observations', action="store_true")
    parser.add_argument('-k', '--kernels', help='Download SPICE kernels for VEX or MEX, Leap Second and EOP.', action="store_true")
    parser.add_argument('--sched', help='Run Sched to create the .vex file', action="store_true")
    parser.add_argument('-t', '--time', help='Start time of the Observations, if different than the first scan time on the spacecraft.', action="store_true")
    parser.add_argument('-s', help='Insert the scan duration (eg. 30m or 20s)')
    parser.add_argument('-S', help='Dur=20m for VEX/MEX and Dur=15s for RadioAstron', action="store_true")
    parser.add_argument('--corr', help='Create a dummy file for correlation purposes', action="store_true")
    parser.add_argument('--scan', help='Total/cumulated scan length (in minutes) for RA observations (eg. 19)')
    parser.add_argument('--nomid', help='Coordinates are NOT calculated at the middle of the scan', action="store_true")
    parser.add_argument('--setup', help='Create an ad-hoc frequency setup', action="store_true")
    parser.add_argument('--pi', help='Provide PI name (Sergei, Giuseppe, Tatiana or Guifre) --> ')
    parser.add_argument('--sumtb', help='Print out a block summary of the observations', action="store_true")
    args = parser.parse_args()
    return args


def paths():
    """
    <kernel_path> is the directory where the SPICE kernels are stored.
                It is assumed that it has the structure:

                spk directory = <kernel_path>spk/<SATELLITE>/ (eg. VEX)
                lsk directory = <kernel_path>lsk/
                pck directory = <kernel_path>pck/

    <meta_path> is the directory where the meta files are stored.

    <keyfile_path> is the main directory where sched-related files
                 are stored.
    """
    import os

    global wd
    wd = os.environ.get('MAKEKEY')

    kernel_path: str = f'{wd}SPICE/kernels/'
    meta_path: str = f'{wd}SPICE/meta/'
    keyfile_path: str = f'{wd}sched_files/'

    return kernel_path, meta_path, keyfile_path


def pointing(prog_dir, target, stations, ut_start, ut_end, steps, filecoords):
    import signal
    import spiceypy as spice
    import ephem
    import complete
    import time
    from datetime import date

    stations_list = [
        x.lower()
        for x in ['METSAHOV', 'WETTZELL', 'ONSALA60', 'ONSALA85', 'MEDICINA', 'YEBES40M', 'MATERA', 'NOTO', 'SHANGHAI', 'URUMUQI', 'KUNMING', 'WARKWORTH', 'KASHIMA', 'YAMAGUCHI', 'HARTEESB', 'YEVPATORIA', 'BADARY', 'PUSHCHINO', 'KATHERIN', 'YARRAGAD', 'HOBART12', 'HOBART26', 'CEDUNA', 'BISDEE']
    ]

    stations_codes = [x.lower() for x in ['Mh', 'Wz', 'On', 'Od', 'Mc', 'Ys', 'Ma', 'Nt', 'Sh', 'Ur', 'Km', 'Ww', 'Ks', 'Ym', 'Hh', 'Ye', 'Bd', 'Pu', 'Ke', 'Yg', 'Hb', 'Ho', 'Cd', 'Bs']]

    stations_dict = dict(list(zip(stations_codes, stations_list)))

    metakernel = f'{prog_dir}meta_{target.lower()}.tm'

    separate_stations = re.split(r"\s*[,;]\s*", stations.strip())

    for STATION in separate_stations:
        if STATION.lower() in list(stations_dict.keys()):
            STATION: str = stations_dict.get(STATION.lower())
            TOPO_FRAME: str = f'{STATION}_TOPO'
            file2: str = f'{filecoords}_{STATION.lower()}.txt'
        elif STATION.lower() in list(stations_dict.values()):
            TOPO_FRAME: str = f'{STATION}_TOPO'
            file2: str = f'{filecoords}_{STATION.lower()}.txt'
        else:
            print('Unknown station(s)!')
            sys.exit(0)

        # --------------------------------------------------------------------------
        # S/C state vector calculation
        # --------------------------------------------------------------------------

        # Unload all kernels.
        spice.kclear()

        # Load metakernel
        spice.furnsh(metakernel)

        # Convert initial UTC time to TDT.
        et1TDB = spice.utc2et(ut_start + '0.01')  # start time
        et1 = spice.unitim(et1TDB, 'TDB', 'TDT')

        # Convert final UTC time to TDT.
        et2TDB = spice.utc2et(ut_end)  # end time
        et2 = spice.unitim(et2TDB, 'TDB', 'TDT')

        et = et1

        f = open(file2, 'w')
        header = f'/ OBJECT_NAME = {target} \n\
/ CENTER_NAME = {STATION} \n\
/ REF_FRAME = {STATION}_TOPO_EQ \n'
        f.write(header)

        while et <= et2:
            times = et
            timesUTC = spice.et2utc(et, 'ISOC', 3)

            # Compute the apparent state of target w.r.t. STATION in their respective topographic reference frames.
            # States in units of km and km/s.
            if target == 'GAIA':
                target = '-123'
            if target == 'Perseverance':
                target = '-168'
            spice.spkpos(target, et, 'J2000', 'LT+S', STATION)

            try:
                vecs_STATION, ltimeSTATION = spice.spkpos(target, et, 'J2000', 'LT+S', STATION)
            except:
                print('\nInsufficient ephemeris data has been loaded to compute the position of {target}!\n   Please download the appropriate kernels.\n')
                sys.exit()

            # Compute the apparent state of target w.r.t. EARTH CENTER in J2000.
            # States in units of km and km/s.

            vecs_EARTH, ltimeEARTH = spice.spkezr(target, et, 'IAU_EARTH', 'LT+S', 'EARTH')
            vecs_to_st, ltimetost = spice.spkezr(STATION, et, 'IAU_EARTH', 'LT+S', 'EARTH')

            # --------------------------------------------------------------------------
            # Conversions
            # --------------------------------------------------------------------------

            # From rectangular coordinates to RA and DEC

            range_ST, ra_ST, dec_ST = spice.recrad(vecs_STATION[0:3])
            range_EARTH, ra_E, dec_E = spice.recrad(vecs_EARTH[0:3])

            # From radians to degrees
            # not needed...

            # RA and DEC in strings
            ra_E_STRING = ephem.hours(ra_E)
            dec_E_STRING = ephem.degrees(dec_E)
            ra_ST_STRING = ephem.hours(ra_ST)
            dec_ST_STRING = ephem.degrees(dec_ST)

            # --------------------------------------------------------------------------
            # Print output file
            # --------------------------------------------------------------------------

            source: str = f'{timesUTC[11:13]}{timesUTC[14:16]}{timesUTC[17:19]}'
            f.write(f"source=\'{source}\' ra={ra_ST_STRING} dec={dec_ST_STRING} equinox=\'j2000\' /\n")

            et = et + steps

        # --------------------------------------------------------------------------
        # Unload all kernels.
        # --------------------------------------------------------------------------

        spice.kclear()

        print(f'\n Created pointing file: {file2}\n')
        f.close()
    if target[0].lower() == 'v' and len(separate_stations) > 1:
        print('Using the last one for the Vex Coordinates')
    return file2


# Program that reads a coordinate files (produced by Tatiana)
# and produces a source catalog for Sched.
# A list of scans to append to the key file is also created.


def sched_ra(filename, dur):
    if os.path.exists('list.sources'):
        os.remove('list.sources')

    outfile = 'sources.coord'

    f = open(outfile, 'w')
    scan = open('list.sources', 'w')

    coords_re = re.compile('(.*source=[\'\"]?(\d+).*(ra=\w+\:\w+\:\w+\.\w+).*(dec=[-+]?\w+\:\w+\:\w+\.\w+).*)')
    for lines in open(filename):
        match = coords_re.match(lines)
        if match:
            source = match.groups()[1]
            coord_ra = match.groups()[2]
            coord_dec = match.groups()[3]
            source_lines = f'source=\'{source}\' {coord_ra} {coord_dec} equinox=\'j2000\' /\n'
            f.write(source_lines)
            scans = f"source=\'{source}\' {dur} /\n"
            scan.write(scans)

    return outfile


def sched_corr(filename, dur, sat):
    if os.path.exists('list.sources'):
        os.remove('list.sources')

    coord_count = 0
    outfile = 'sources.corr'

    f = open(outfile, 'w')
    scan = open('list.sources', 'w')

    coords_re = re.compile('(.*source=[\'\"]?(\d+).*(ra=\w+\:\w+\:\w+\.\w+).*(dec=[-+]?\w+\:\w+\:\w+\.\w+).*)')
    for lines in open(filename):
        match = coords_re.match(lines)
        if match:
            source = match.groups()[1]
            coord_ra = match.groups()[2]
            coord_dec = match.groups()[3]
            if coord_count == 0:
                source_lines = f'source=\'{sat.upper()}\' {coord_ra} {coord_dec} equinox=\'j2000\' /\n'
                f.write(source_lines)
                coord_count = 1
            scans = f'source={source} {dur} /\n'
            scan.write(scans)

    return outfile


def scans_ra(scan_length, step):
    if os.path.exists('list.scans'):
        os.remove('list.scans')

    outfile = 'list.sources'
    scans = open('list.scans', 'w')

    times = re.compile('source=(\d+)')
    gap_time = 1

    first_scan = file(outfile).readlines()[0]
    start_time = times.match(first_scan).groups()[0]
    last_scan = file(outfile).readlines()[-1]
    last_time = times.match(last_scan).groups()[0]

    if len(start_time) == 5:
        hours, minutes, seconds = start_time[0:1], start_time[1:3], start_time[3:5]
    if len(start_time) == 6:
        hours, minutes, seconds = start_time[0:2], start_time[2:4], start_time[4:6]

    t0 = datetime.datetime(1, 1, 1, int(hours), int(minutes), int(seconds))
    tgap = t0 + datetime.timedelta(minutes=scan_length)
    tgap2 = t0 + datetime.timedelta(minutes=scan_length + gap_time)
    tgap0 = tgap2 + datetime.timedelta(seconds=step)

    def time_gap(x):
        if x == '6':
            gap = str(tgap.time())[0:2] + str(tgap.time())[3:5] + str(tgap.time())[6:8]
            gap2 = str(tgap2.time())[0:2] + str(tgap2.time())[3:5] + str(tgap2.time())[6:8]
            gap0 = str(tgap0.time())[0:2] + str(tgap0.time())[3:5] + str(tgap0.time())[6:8]
        if x == '5':
            gap = str(tgap.time())[1:2] + str(tgap.time())[3:5] + str(tgap.time())[6:8]
            gap2 = str(tgap2.time())[1:2] + str(tgap2.time())[3:5] + str(tgap2.time())[6:8]
            gap0 = str(tgap0.time())[1:2] + str(tgap0.time())[3:5] + str(tgap0.time())[6:8]
        return gap, gap2, gap0

    gap, gap2, gap0 = time_gap(str(len(start_time)))

    for lines in open(outfile):
        match = times.match(lines)
        split_line = lines
        if match:
            t = match.groups()[0]
            lines = ''.join(split_line)
            if t == last_time:
                lines = '!' + ''.join(split_line)
            elif t == gap0:
                lines = 'gap=0:00 ' + ''.join(split_line)
                tgap0 = tgap2 + datetime.timedelta(seconds=step)
                gap, gap2, gap0 = time_gap(str(len(start_time)))
            elif t >= gap and t < gap2:
                lines = '!' + ''.join(split_line)
            elif t == gap2 and t != last_time:
                lines = 'gap=1:00 ' + ''.join(split_line)
                tgap = tgap2 + datetime.timedelta(minutes=scan_length)
                tgap2 = tgap2 + datetime.timedelta(minutes=scan_length + gap_time)
                gap, gap2, gap0 = time_gap(str(len(start_time)))

            scans.write(lines)


def scans_corr(sat, scan_length):
    if os.path.exists('list.corr'):
        os.remove('list.corr')

    outfile = 'list.sources'
    scans = open('list.corr', 'w')

    times = re.compile('source=(\d+)')
    step = 60
    gap_time = 1

    first_scan = file(outfile).readlines()[0]
    start_time = times.match(first_scan).groups()[0]
    last_scan = file(outfile).readlines()[-1]
    last_time = times.match(last_scan).groups()[0]

    if len(start_time) == 5:
        hours, minutes, seconds = start_time[0:1], start_time[1:3], start_time[3:5]
    if len(start_time) == 6:
        hours, minutes, seconds = start_time[0:2], start_time[2:4], start_time[4:6]

    t0 = datetime.datetime(1, 1, 1, int(hours), int(minutes), int(seconds))
    tgap = t0 + datetime.timedelta(minutes=scan_length)
    tgap2 = t0 + datetime.timedelta(minutes=scan_length + gap_time)
    tgap0 = tgap2 + datetime.timedelta(seconds=step)

    def time_gap(x):
        if x == '6':
            gap = str(tgap.time())[0:2] + str(tgap.time())[3:5] + str(tgap.time())[6:8]
            gap2 = str(tgap2.time())[0:2] + str(tgap2.time())[3:5] + str(tgap2.time())[6:8]
            gap0 = str(tgap0.time())[0:2] + str(tgap0.time())[3:5] + str(tgap0.time())[6:8]
        if x == '5':
            gap = str(tgap.time())[1:2] + str(tgap.time())[3:5] + str(tgap.time())[6:8]
            gap2 = str(tgap2.time())[1:2] + str(tgap2.time())[3:5] + str(tgap2.time())[6:8]
            gap0 = str(tgap0.time())[1:2] + str(tgap0.time())[3:5] + str(tgap0.time())[6:8]
        return gap, gap2, gap0

    gap, gap2, gap0 = time_gap(str(len(start_time)))

    for lines in open(outfile):
        match = times.match(lines)
        split_line = lines[:14] + '\n'
        if match:
            t = match.groups()[0]
            if t == start_time:
                lines = f'gap=1:00 source={sat.upper()} dur={scan_length}:00 /\n'
                scans.write(lines)
            if t == gap2 and t != last_time:
                lines = f'gap=1:00 source={sat.upper()} dur={scan_length}:00 /\n'
                tgap = tgap2 + datetime.timedelta(minutes=scan_length)
                tgap2 = tgap2 + datetime.timedelta(minutes=scan_length + gap_time)
                gap, gap2, gap0 = time_gap(str(len(start_time)))
                scans.write(lines)


def setup():
    while True:
        nchan = input('How many channels? (4 or 8) --> ')
        if nchan == '4' or nchan == '8':
            break
        else:
            print('Please choose 4 or 8!')

    while True:
        bbfilter = input('Insert bandwidth in GHz (4, 8 or 16) --> ')
        if bbfilter == '4' or bbfilter == '8' or bbfilter == '16':
            break
        else:
            print('Please choose 4 or 8 or 16!')

    while True:
        pcal = input("PCAL 'on' or 'off' (default is OFF) --> ")
        if pcal.lower() == 'on' or pcal.lower() == 'off' or pcal == '':
            if pcal == '':
                pcal = 'off'
            else:
                pcal = pcal.lower()
            break
        else:
            print('Please write on or off')

    while True:
        freqref = input('Insert reference frequency MHz (eg. 8417.99) --> ')
        try:
            float(freqref)
            print(f'Your reference frequency is: {freqref}')
            right_freq = input('Correct? (Y,n) ')
            if right_freq == '' or right_freq[0].lower() == 'y':
                break
        except ValueError:
            print('Input error!')

    while True:
        offset = input('Insert frequency offset (eg. -10kHz or 4MHz) --> ')
        try:
            if offset[-3].lower() == 'k':
                unit: float = 1000
                break
            elif offset[-3].lower() == 'm':
                unit: float = 1
                break
        except IndexError:
            print('Unclear input! Please try again.')
        except ValueError:
            print('Unclear input! Please try again.')

    j: int = 1
    offsets = []
    offsets.append(0)
    while j < int(nchan):
        off = int(offset[:-3]) * j
        offsets.append(off / unit)
        j = j + 1

    freqoffsets = ["{0:0.2f}".format(i) for i in offsets]
    freqoff = ','.join(str(f) for f in freqoffsets)
    print(freqoff)

    header = {'nchan': nchan, 'bits': '2', 'bbfilter': bbfilter, 'freqref': freqref, 'freqoff': freqoff, 'netside': 'U', 'pcal': pcal, 'pol': 'RCP', 'format': 'vdif', 'barrel': 'roll_off'}

    setup_file = f'{nchan}ChanX{bbfilter}MHz.{freqref}'
    scans = open(setup_file, 'w')

    if nchan == '4':
        chan_file = f'{wd}sched_files/Setups/stations_setups/4.chan'
    elif nchan == '8':
        chan_file = f'{wd}sched_files/Setups/stations_setups/8.chan'

    print('\nYour frequency setup will be:\n')
    for keys in list(header.keys()):
        lines = keys + ' = ' + header.get(keys) + '\n'
        print(lines)
        scans.write(lines)

    separator = '/\n'
    scans.write(separator)

    ok = input('\nProceed? (Y/n): ')
    if ok == '' or ok[0].lower() == 'y':
        pass
    else:
        print('\nOK... Bye!')
        if os.path.exists(setup_file):
            os.remove(setup_file)
        sys.exit(1)

    for line in open(chan_file):
        scans.write(line)

    return setup_file


def getKernels(kernel_dir, satellite):
    import urllib.request, urllib.error, urllib.parse

    now = datetime.datetime.now()
    year: str = str(now)[2:4]
    month: str = str(now)[5:7]
    date: str = f'{year}{month}'

    satellite: str = satellite.upper()

    spk_dir: str = f'{kernel_dir}spk/{satellite}/'
    lsk_dir: str = f'{kernel_dir}lsk/'
    pck_dir: str = f'{kernel_dir}pck/'

    url: str = f'http://naif.jpl.nasa.gov/'
    url1: str = f'ftp://spiftp.esac.esa.int/data/SPICE/'
    path: str = f'pub/naif/{satellite}/kernels/spk/'
    filename: str = f'OR{satellite[0]*2}__{date}'

    if satellite == "BC_MPO":
        u = urllib.request.urlopen(f'{url1}BEPICOLOMBO/')
        response = urllib.request.urlopen(url1).read().decode('utf-8')
    else:
        u = urllib.request.urlopen(f'{url}{path}')
        response = urllib.request.urlopen(url).read().decode('utf-8')

    response_re = re.compile('.*\>(%s.*BSP)\<.*' % filename)
    for files in response_re.findall(response):
        dest_file = f'{spk_dir}{files}'
        print(f'{dest_file}')
        if os.path.exists(dest_file):
            print(f'{satellite} SPICE Kernel Already Exists!')
        else:
            os.system('wget %s --directory-prefix=%s' % (url + path + files, spk_dir))
            os.system("rm -rf {0}OR".format(spk_dir) + satellite[0] * 2 + "_LAST_{0}.BSP".format(satellite))
            os.system("ln -s {0} {1}OR".format(dest_file, spk_dir) + satellite[0] * 2 + "_LAST_{0}.BSP".format(satellite))
            print(f"Created symlink: {spk_dir}OR" + satellite[0] * 2 + "_LAST_{satellite}.BSP\n")

    path1 = f'pub/naif/{satellite}/kernels/lsk/'
    filename = 'NAIF'
    if satellite == "BC_MPO":
        response = urllib.request.urlopen(f'{url1}BEPICOLOMBO/kernels/lsk/').read().decode('utf-8')
    else:
        response = urllib.request.urlopen(f'{url}{path1}').read().decode('utf-8')

    response_re = re.compile('.*\>(%s.*TLS)\<.*' % filename)
    for files in response_re.findall(response):
        dest_file = lsk_dir + str(files)
        if os.path.exists(dest_file):
            print('Leap Second Kernel Already Exists!')
        else:
            os.system('wget %s --directory-prefix=%s' % (url + path1 + files, lsk_dir))
            os.system('rm -rf %snaifLAST.tls' % lsk_dir)
            os.system('ln -s %s %snaifLAST.tls' % (dest_file, lsk_dir))
            print('Created symlink: %snaifLAST.tls\n' % lsk_dir)

    path2 = "pub/naif/generic_kernels/pck/"
    filename = 'earth_000101'
    response = urllib.request.urlopen(url + path2).read().decode('utf-8')
    response_re = re.compile('.*\>(%s.*bpc)\<.*' % filename)
    for files in response_re.findall(response):
        dest_file = pck_dir + str(files)
        if os.path.exists(dest_file):
            print('EOP Kernel Already Exists!')
        else:
            os.system('wget %s --directory-prefix=%s' % (url + path2 + files, pck_dir))
            os.system('rm -rf %searth_LAST.bpc' % pck_dir)
            os.system('ln -s %s %searth_LAST.bpc' % (dest_file, pck_dir))
            print(f'Created symlink: {pck_dir}earth_LAST.bpc\n')
