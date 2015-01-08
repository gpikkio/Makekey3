import sys, signal, re, os
import mods
import time
from datetime import date
from subprocess import call

def MakeCoordFunction(spacecraft, PI,out_file, scantime, donwload_kernels,
                      mid_scan, do_vex, start_date, end_date, initial_gap, gap_start,
                      stations):

    # slices a date string of form dd/mm/yyyy hh:mm:ss
    def date_str(s):
        return s[0:2], s[3:5], s[6:10], s[11:13], s[14:16], s[17:19]

    #############################
    # PATH definition and checks.
    #
    kernel_path, meta_path, keyfile_path =  mods.paths()
    #kernel_path = SPICE KERNELS DIRECTORY
    #meta_path = SPICE METAFILES DIRECTORY
    #keyfile_path = MAIN DIRECTORY FOR SCHED TEMPLATES
    #
    def path_check(paths):
        check_note = 'Please define the env variable $MAKEKEY.'
        if not os.path.isdir(paths):
            print('\n\tPath {} not found.\n\t{}\n'.format(paths, check_note))
            sys.exit(0)

    for paths in kernel_path, meta_path, keyfile_path: path_check(paths)

    pis={'sergei':{'piname':'Sergei Pogrebenko',
                   'phone':'+31-521-596523',
                   'email':'pogrebenko@jive.nl'},
         'giuseppe':{'piname':'Giuseppe Cimo',
                   'phone':'+31-521-596545',
                   'email':'cimo@jive.nl'},
         'tatiana':{'piname':'Tatiana Bocanegra',
                   'phone':'+31-521-596523',
                   'email':'bocanegra@jive.nl'},
         'guifre':{'piname':'Guifre Molera',
                   'phone':'+31-521-596506',
                   'email':'molera@jive.nl'}}

    # command line options and initialization
    #

    gaps='y'

    def steps(step):
        if step[-1]=='s':
            timestep=float(step[:-1])
            duration = 'dur=00:'+str(int(timestep))
        elif step[-1]=='m':
            timestep=float(step[:-1])*60.
            duration = 'dur='+str(int(timestep/60.)-1)+':00 gap=1:00'
        else:
    #       This catches a wrong input (only m or s are valid!)
            str(int(step))+1
        return timestep, duration

    timestep=''
    duration=''
    sat=''
    timestep, duration = steps(scantime)

    if spacecraft == 'VEX':
        sat = 'Vex'
        gaps='n'

    if spacecraft == 'MEX':
        sat = 'Mex'
        gaps='n'

    coordname=''
    outfile = out_file

    same_day='y'

    kernels='n'
    if donwload_kernels == 'Y':
        kernels='y'
        mods.getKernels(kernel_path,sat)

    early_start='n'

    correlation='n'

    # Coordinates are calculated for the 
    # middle of the scan
    if mid_scan == 'Y': 
        scan_center='y'
    else:
        scan_center='n'

    #Should I create a setup?
    setup='n'

    pi=str(PI).lower()

    # list of names for the satellites
    #
    list_vex = ['v', 'vex']
    list_mex = ['m', 'mex']

    #
    # end initialization!
    #####################

    ###################
    #                 #
    # Here we start...#
    #                 #
    ###################

    print ''
    print '\n   This program creates the key file for Sched.\n'
    print ''

    full_date = start_date
    full_date2 = end_date
        
    day, month, year, h1,m1,s1 = date_str(str(start_date))
    day2,month2,year2,h2,m2,s2 = date_str(str(end_date))
    start = h1+':'+m1+':'+s1
    ends = h2+':'+m2+':'+s2    

    date = month+day

    filename = keyfile_path+'keyfiles/default.key'

    if sat.lower() in (list_vex):
        target='VEX'
        if setup == 'n': setup_file =  keyfile_path+'Setups/vex.x'
        gaps='n'
    elif sat.lower() in (list_mex):
        target='MEX'
        if setup == 'n': setup_file =  keyfile_path+'Setups/mex.x'
        gaps='n'

    outname=out_file

    if scan_center == 'y':
        m1=str(int(float(m1)+timestep/60./2.))
        m2=str(int(float(m2)+timestep/60./2.))

    utctime_ini=year+'-'+month+'-'+day+'T'+h1+':'+m1+':'+s1#+'.002'
    utctime_end=year2+'-'+month2+'-'+day2+'T'+h2+':'+m2+':'+s2#+'.002'

    if timestep=='':
        while True:
            step = raw_input('\nInsert time step (i.e. 20m or 15s)--> ')
            try:
                timestep, duration = steps(step)
                break
            except TypeError:
                print('Invalid time unit! Please use m for minutes and s for seconds.')

    # start for the participant stations
    #

    output = open(outname, 'a')

    # ask for the file with the coordinates
    #
    if coordname!='':
        filecoords=coordname
    else:
        filecoords=target.lower()+'_'+utctime_ini
        filecoords=mods.pointing(meta_path,target,stations,
                                 utctime_ini,utctime_end,timestep,filecoords)

    # run the sat module to create
    # the scan list with or without gaps
    #
    open(filecoords)
    if sat.lower() in (list_vex+list_mex):
        source_file = mods.sched_ra(filecoords,duration)


    # let's define some match and catch
    #
    exp_re = re.compile('(.*expcode.*\')(\*{5})(\'.*)')
    stafile_re = re.compile('(^stafile.*)')
    sources_re = re.compile('(.*srcfile2.*)(sources\.\*{4})(.*)')
    y_re = re.compile('(.*year.*)')
    m_re = re.compile('(.*month.*)')
    d_re = re.compile('(.*day.*)')
    s_re = re.compile('(^start.*)')
    sta_re = re.compile('(.*stations.*)')
    setup_re = re.compile('(.*setup.*)')
    pi_re = re.compile('(.*piname.*\')(.*)(\'.*)')
    phone_re = re.compile('(.*phone.*\')(.*)(\'.*)')
    email_re = re.compile('(.*email.*\')(.*)(\'.*)')

    # if match then change the string
    #
    for lines in open(filename):
        match_exp = exp_re.match(lines)
        match_stafile = stafile_re.match(lines)
        match_source = sources_re.match(lines)
        match_year = y_re.match(lines)
        match_month = m_re.match(lines)
        match_day = d_re.match(lines)
        match_start = s_re.match(lines)
        match_sta = sta_re.match(lines)
        match_setup = setup_re.match(lines)
        match_pi = pi_re.match(lines)
        match_phone = phone_re.match(lines)
        match_email = email_re.match(lines)
        split_line = lines
        if match_exp:
            if sat.lower() in (list_vex):
                split_line = exp_re.split(lines)
                split_line[2] = 'v'+date
                lines = ''.join(split_line)
            elif sat.lower() in (list_mex):
                split_line = exp_re.split(lines)
                split_line[2] = 'm'+date
                lines = ''.join(split_line)
            elif sat.lower() in (list_ra):
                split_line = exp_re.split(lines)
                split_line[2] = 'r'+date
                lines = ''.join(split_line)
            elif sat.lower() in (list_gaia):
                split_line = exp_re.split(lines)
                split_line[2] = 'g'+date
                lines = ''.join(split_line)
            else:
                split_line = exp_re.split(lines)
                split_line[2] = 'x'+date
                lines = ''.join(split_line)
        if match_pi:
            split_line = pi_re.split(lines)
            split_line[2] = pis.get(pi).get('piname')
        if match_phone:
            split_line = phone_re.split(lines)
            split_line[2] = pis.get(pi).get('phone')
        if match_email:
            split_line = email_re.split(lines)
            split_line[2] = pis.get(pi).get('email')
        if match_stafile:
            split_line = stafile_re.split(lines)
            split_line = 'stafile = '+keyfile_path+'catalogs/stations.local\n'
        if match_source:
            split_line = sources_re.split(lines)
            if correlation == 'n':
                split_line[2] = source_file
            else:
                split_line[2] = corr_file
            lines = ''.join(split_line)
        if match_year:
            split_line = y_re.split(lines)
            split_line = 'year     = '+year+'\n'
            lines = ''.join(split_line)
        if match_month:
            split_line = m_re.split(lines)
            split_line = 'month    = '+month+'\n'
            lines = ''.join(split_line)
        if match_day:
            split_line = d_re.split(lines)
            split_line = 'day      = '+day+'\n'
            lines = ''.join(split_line)
        if match_start:
            split_line = s_re.split(lines)
            if early_start=='n':
                split_line = 'start    = '+start+'\n'
            elif early_start=='y':
                split_line = 'start    = '+start_early+'\n'
            lines = ''.join(split_line)
        if match_sta:
            test = match_sta.groups()[0]
            if test[0:8] == 'stations':
                split_line = sta_re.split(lines)
                split_line = 'stations = '+stations+'\n'
                lines = ''.join(split_line)
            else:
                pass
        if match_setup:
            if setup=='y':
                split_line = setup_re.split(lines)
                split_line = 'setup =', setup_file,'\n'
                lines = ''.join(split_line)
            else:
                if sat.lower() in (list_vex):
                    split_line = setup_re.split(lines)
                    split_line = 'setup = '+ keyfile_path+'Setups/vex.x\n'
                    lines = ''.join(split_line)
                elif sat.lower() in (list_mex):
                    split_line = exp_re.split(lines)
                    split_line = 'setup = '+ keyfile_path+'Setups/mex.x\n'
                    lines = ''.join(split_line)
                elif sat.lower() in (list_ra):
                    split_line = exp_re.split(lines)
                    split_line = 'setup = '+ keyfile_path+'Setups/ra.x\n'
                    lines = ''.join(split_line)
                elif sat.lower() in (list_gaia):
                    split_line = exp_re.split(lines)
                    split_line = 'setup = '+ keyfile_path+'Setups/gaia.x\n'
                    lines = ''.join(split_line)
                else:
                    split_line = exp_re.split(lines)
                    lines = ''.join(split_line)
    
        lines = ''.join(split_line)

    #   write the strings into the new key file
    #
        output.write(lines)

    # read the file with the scan list created by the module
    # and append the scan list at the bottom of the key file.
    #
    # append a dummy list in case of a file for correlation.
    #
    if correlation=='n':
        if gaps == 'y':
            for listscan in open('list.scans'):
                output.write(listscan)
        elif gaps == 'n':
            for listscan in open('list.sources'):
                output.write(listscan)
    else:
         for listscan in open('list.corr'):
             output.write(listscan)

    print '\nPlease check the output file:', outname, '\n'
    output.close()

    if do_vex == 'Y':
        call("/aps3/sched11.3u1/bin/LINUX64/sched < %s" % outname, shell=True)
