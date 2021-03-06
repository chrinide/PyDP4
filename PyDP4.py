#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
PyDP4 integrated workflow for the running of MM, DFT GIAO calculations and
DP4 analysis
v0.8

Copyright (c) 2015-2017 Kristaps Ermanis, Jonathan M. Goodman

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.

Created on Wed Nov 19 15:26:32 2014
Updated on Mon Sep 28 2017

@author: ke291

The main file, that should be called to start the PyDP4 workflow.
Interprets the arguments and takes care of the general workflow logic.
"""

from __future__ import division

import Gaussian
import NMRAnalysis
import Tinker
import MacroModel
import NWChem
import Jaguar

import glob
import sys
import os
import datetime
import argparse
import math


#Assigning the config default values
class Settings:
    MMTinker = False
    MMMacromodel = True
    DFT = 'z'
    Rot5Cycle = False
    Title = 'DP4molecule'
    DarwinNodeSize = 32
    RingAtoms = []
    ConfPrune = True
    GenDS = True
    GenTaut = False
    GenProt = False
    Solvent = ''
    DFTOpt = False
    PM6Opt = False
    PM7Opt = False
    HFOpt = False
    M06Opt = False
    MaxDFTOptCycles = 50
    jKarplus = False
    jFC = False
    jJ = False
    Bias = False
    CP3 = False
    JDir = ''
    TimeLimit = 24
    queue = 's1'
    TinkerPath = '~/tinker7/bin/scan '
    OBPath = '/home/ke291/Tools/openbabel-install/lib/python2.7/site-packages/'
    SCHRODINGER = '/usr/local/shared/schrodinger/current'
    MOPAC = '/home/ke291/MOPAC/MOPAC2016.exe'
    DarwinScrDir = '/home/ke291/rds/hpc-work/'
    StartTime = ''
    nProc = 1
    OtherNuclei = ''
    RenumberFile = ''
    ScriptDir = ''
    user = 'ke291'
    OnlyConfS = False # Stop the process after conformational search
    MMstepcount = 10000
    MMfactor = 2500  # nsteps = MMfactor*degrees of freedom
    HardConfLimit = 10000
    MaxConcurrentJobs = 75
    MaxConcurrentJobsDarwin = 320
    PerStructConfLimit = 100
    StrictConfLimit = True
    Cluster = False
    InitialRMSDcutoff = 0.75
    MaxCutoffEnergy = 10.0
    TMS_SC_C13 = 191.69255
    TMS_SC_H1 = 31.7518583
    CFCl3_SC_F19 = 180.9961
    NTaut = 1
    LogFile = 'PyDP4.log'
    AssumeDone = False
    UseExistingInputs = False
    GenOnly = False
    StatsModel = 'g'
    StatsParamFile = ''
    JStatsModel = 'g'
    JStatsParamFile = ''
    EnergyDir = ''
    SelectedStereocentres = []
    charge = None
    BasicAtoms = []
    ForceField = 'mmff'
    BasisSet = "6-31g(d,p)"
    Functional = "b3lyp"

settings = Settings()


def main(filename, ExpNMR, nfiles):

    print "=========================="
    print "PyDP4 script,\nintegrating Tinker/MacroModel,"
    print "Gaussian/NWChem/Jaguar and DP4\nv0.7"
    print "\nCopyright (c) 2015-2018 Kristaps Ermanis, Jonathan M. Goodman"
    print "Distributed under MIT license"
    print "==========================\n\n"

    if nfiles < settings.NTaut or nfiles % settings.NTaut != 0:
        print "Invalid number of tautomers/input files - number of input files\
        must be a multiple of number of tautomers"
        quit()
    
    SetTMSConstants()
    
    #Check the number of input files, generate some if necessary
    if nfiles == 1:
        import InchiGen
        if len(settings.SelectedStereocentres) > 0:
            numDS, inpfiles = InchiGen.GenSelectDiastereomers(filename,
                                                settings.SelectedStereocentres)
        else:
            numDS, inpfiles = InchiGen.GenDiastereomers(filename)
        if settings.GenTaut:
            newinpfiles = []
            for ds in inpfiles:
                print "Generating tautomers for " + ds
                settings.NTaut, files = InchiGen.GenTautomers(ds)
                newinpfiles.extend(files)
            inpfiles = list(newinpfiles)
        if settings.GenProt:
            newinpfiles = []
            for ds in inpfiles:
                print "Generating protomers for " + ds
                settings.NTaut, files = InchiGen.GenProtomers(ds,
                                                        settings.BasicAtoms)
                newinpfiles.extend(files)
            inpfiles = list(newinpfiles)
    else:
        inpfiles = filename
        if settings.GenTaut:
            numDS = nfiles
            import InchiGen
            newinpfiles = []
            for ds in inpfiles:
                print "Generating tautomers for " + ds
                settings.NTaut, files = InchiGen.GenTautomers(ds)
                newinpfiles.extend(files)
            inpfiles = list(newinpfiles)
        else:
            numDS = int(nfiles/settings.NTaut)
            if numDS == 1:
                import InchiGen
                for f in filename:
                    tdiastereomers = []
                    numDS, tinpfiles = InchiGen.GenDiastereomers(f)
                    tdiastereomers.append(tinpfiles)
                tinpfiles = zip(*tdiastereomers)
                inpfiles = []
                for ds in tinpfiles:
                    inpfiles.extend(list(ds))

    print inpfiles

    #Check the existence of mm output files
    MMRun = False

    if settings.MMTinker:
        #Check if there already are Tinker output files with the right names
        tinkfiles = glob.glob('*.tout')
        mminpfiles = []
        for f in inpfiles:
            if f + '.tout' in tinkfiles and (f + 'rot.tout' in
                                    tinkfiles or settings.Rot5Cycle is False):
                if len(mminpfiles) == 0:
                    MMRun = True
            else:
                MMRun = False
                mminpfiles.append(f)
    else:
        #Check if there already are MacroModel output files with the right names
        mmfiles = glob.glob('*.log')
        mminpfiles = []
        for f in inpfiles:
            if f + '.log' in mmfiles and (f + 'rot.log' in
                                        mmfiles or settings.Rot5Cycle is False):
                if len(mminpfiles) == 0:
                    MMRun = True
            else:
                MMRun = False
                mminpfiles.append(f)

    if MMRun or settings.AssumeDone or settings.UseExistingInputs:
        print 'Conformation search has already been run for these inputs.\
                \nSkipping...'
        if settings.GenOnly:
            print "Input files generated, quitting..."
            quit()
    else:
        if settings.MMTinker:
            print 'Some Tinker files missing.'
            print '\nSeting up Tinker files...'
            Tinker.SetupTinker(len(inpfiles), settings, *mminpfiles)
            if settings.GenOnly:
                print "Input files generated, quitting..."
                quit()
            print '\nRunning Tinker...'
            Tinker.RunTinker(len(inpfiles), settings, *mminpfiles)
        else:
            print 'Some Macromodel files missing.'
            print '\nSetting up Macromodel files...'
            MacroModel.SetupMacromodel(len(inpfiles), settings, *mminpfiles)
            if settings.GenOnly:
                print "Input files generated, quitting..."
                quit()
            print '\nRunning Macromodel...'
            MacroModel.RunMacromodel(len(inpfiles), settings, *mminpfiles)

    if settings.OnlyConfS:
        print "Conformational search completed, quitting as instructed."
        quit()

    if (not settings.AssumeDone) and (not settings.UseExistingInputs):
        if settings.ConfPrune and not settings.Cluster:
            if settings.DFT == 'z' or settings.DFT == 'g' or settings.DFT == 'd':
                adjRMSDcutoff = Gaussian.AdaptiveRMSD(inpfiles[0], settings)
            elif settings.DFT == 'n' or settings.DFT == 'w' or settings.DFT == 'm':
                adjRMSDcutoff = NWChem.AdaptiveRMSD(inpfiles[0], settings)
            elif settings.DFT == 'j':
                adjRMSDcutoff = Jaguar.AdaptiveRMSD(inpfiles[0], settings)

            print 'RMSD cutoff adjusted to ' + str(adjRMSDcutoff)
        else:
            adjRMSDcutoff = settings.InitialRMSDcutoff
        
        #Run DFT setup script for every diastereomer
        print '\nRunning DFT setup...'
        i = 1
        for ds in inpfiles:
            if settings.DFT == 'z' or settings.DFT == 'g' or settings.DFT == 'd':
                print "\nGaussian setup for file " + ds + " (" + str(i) +\
                    " of " +  str(len(inpfiles)) + ")"
                if settings.Cluster == False:
                    Gaussian.SetupGaussian(ds, ds + 'ginp', 3, settings,
                                           adjRMSDcutoff)
                else:
                    Gaussian.SetupGaussianCluster(ds, ds + 'ginp', 3, settings)
            elif settings.DFT == 'n' or settings.DFT == 'w' or settings.DFT == 'm':
                print "\nNWChem setup for file " + ds +\
                    " (" + str(i) + " of " + str(len(inpfiles)) + ")"
                NWChem.SetupNWChem(ds, ds + 'nwinp', 3, settings,
                                   adjRMSDcutoff)
            elif settings.DFT == 'j':
                print "\nJaguar setup for file " + ds +\
                    " (" + str(i) + " of " + str(len(inpfiles)) + ")"
                Jaguar.SetupJaguar(ds, ds + 'jinp', 3, settings,
                                   adjRMSDcutoff)

            i += 1
        QRun = False
    elif settings.AssumeDone:
        QRun = True
    else:
        QRun = False

    if settings.DFT == 'z' or settings.DFT == 'g' or settings.DFT == 'd':
        Files2Run = Gaussian.GetFiles2Run(inpfiles, settings)
    elif settings.DFT == 'n' or settings.DFT == 'w' or settings.DFT == 'm':
        Files2Run = NWChem.GetFiles2Run(inpfiles, settings)
    elif settings.DFT == 'j':
        Files2Run = Jaguar.GetFiles2Run(inpfiles, settings)
    
    print Files2Run
    
    if len(Files2Run) == 0:
        
        if (settings.DFT == 'z' or settings.DFT == 'g' or settings.DFT == 'd') and\
            (settings.DFTOpt or settings.PM6Opt or settings.HFOpt or settings.M06Opt)\
	    and not settings.AssumeDone:
            print "Checking if all geometries have converged"
            Ngeoms, Nunconverged, unconverged = Gaussian.CheckConvergence(inpfiles)
            if Nunconverged > 0:
                print "WARNING: Not all geometries have achieved convergence!"
                print ','.join([x[:-8] for x in unconverged])
                print "Number of geometries: " + str(Ngeoms)
                print "Unconverged: " + str(Nunconverged)
                Gaussian.ResubGeOpt(unconverged, settings)
                Files2Run = Gaussian.GetFiles2Run(inpfiles, settings)
                QRun = False
            else:
                QRun = True
        else:
            QRun = True
        
        #QRun = True
        
    if len(Files2Run) > settings.HardConfLimit:
        print "Hard conformation count limit exceeded, DFT calculations aborted."
        quit()
    
    if QRun:
        print 'DFT has already been run for these inputs. Skipping...'
    else:
        if settings.DFT == 'g':
            print '\nRunning Gaussian locally...'
            Gaussian.RunLocally(Files2Run, settings)

        elif settings.DFT == 'z':
            print '\nRunning Gaussian on Ziggy...'

            #Run Gaussian jobs on Ziggy cluster in folder named after date
            #and time in the short 1processor job queue
            #and wait until the last file is completed
            MaxCon = settings.MaxConcurrentJobs
            if settings.DFTOpt or settings.PM6Opt or settings.HFOpt or settings.M06Opt:
                for i in range(len(Files2Run)):
                    Files2Run[i] = Files2Run[i][:-5] + '.com'
            if len(Files2Run) < MaxCon:
                Gaussian.RunOnZiggy(0, settings.queue, Files2Run, settings)
            else:
                print "The DFT calculations will be done in " +\
                    str(math.ceil(len(Files2Run)/MaxCon)) + " batches"
                i = 0
                while (i+1)*MaxCon < len(Files2Run):
                    print "Starting batch nr " + str(i+1)
                    Gaussian.RunOnZiggy(str(i+1), settings.queue, Files2Run[(i*MaxCon):((i+1)*MaxCon)], settings)
                    i += 1
                print "Starting batch nr " + str(i+1)
                Gaussian.RunOnZiggy(str(i+1), settings.queue, Files2Run[(i*MaxCon):], settings)
        elif settings.DFT == 'd':
            print '\nRunning Gaussian on Darwin...'

            #Run Gaussian jobs on Darwin cluster in folder named after date
            #and title and wait until the last file is completed
            MaxCon = settings.MaxConcurrentJobsDarwin
            
            if settings.DFTOpt or settings.PM6Opt or settings.HFOpt or settings.M06Opt:
                for i in range(len(Files2Run)):
                    Files2Run[i] = Files2Run[i][:-5] + '.com'
                    
            if len(Files2Run) < MaxCon:
                Gaussian.RunOnDarwin(0, Files2Run, settings)
            else:
                print "The DFT calculations will be done in " +\
                    str(math.ceil(len(Files2Run)/MaxCon)) + " batches"
                i = 0
                while (i+1)*MaxCon < len(Files2Run):
                    print "Starting batch nr " + str(i+1)
                    Gaussian.RunOnDarwin(str(i+1), Files2Run[(i*MaxCon):((i+1)*MaxCon)],
                        settings)
                    i += 1
                print "Starting batch nr " + str(i+1)
                Gaussian.RunOnDarwin(str(i+1), Files2Run[(i*MaxCon):], settings)

        elif settings.DFT == 'n':
            print '\nRunning NWChem locally...'
            NWChem.RunNWChem(Files2Run, settings)

        elif settings.DFT == 'w':
            print '\nRunning NWChem on Ziggy...'

            #Run NWChem jobs on Ziggy cluster in folder named after date
            #and time in the short 1 processor job queue
            #and wait until the last file is completed
            now = datetime.datetime.now()
            MaxCon = settings.MaxConcurrentJobs
            if len(Files2Run) < MaxCon:
                NWChem.RunOnZiggy(now.strftime('%d%b%H%M'), settings.queue,
                                  Files2Run, settings)
            else:
                print "The DFT calculations will be done in " +\
                    str(math.ceil(len(Files2Run)/MaxCon)) + " batches"
                i = 0
                while (i+1)*MaxCon < len(Files2Run):
                    print "Starting batch nr " + str(i+1)
                    NWChem.RunOnZiggy(now.strftime('%d%b%H%M')+str(i+1),
                        settings.queue, Files2Run[(i*MaxCon):((i+1)*MaxCon)], settings)
                    i += 1
                print "Starting batch nr " + str(i+1)
                NWChem.RunOnZiggy(now.strftime('%d%b%H%M')+str(i+1),
                    settings.queue, Files2Run[(i*MaxCon):], settings)
        
        elif settings.DFT == 'm':
            print '\nRunning NWChem on Medivir cluster...'

            #Run NWChem jobs on Medivir cluster
            MaxCon = settings.MaxConcurrentJobs
            if len(Files2Run) < MaxCon:
                NWChem.RunOnMedivir(Files2Run, settings)
            else:
                print "The DFT calculations will be done in " +\
                    str(math.ceil(len(Files2Run)/MaxCon)) + " batches"
                i = 0
                while (i+1)*MaxCon < len(Files2Run):
                    print "Starting batch nr " + str(i+1)
                    NWChem.RunOnMedivir(Files2Run[(i*MaxCon):((i+1)*MaxCon)], settings)
                    i += 1
                print "Starting batch nr " + str(i+1)
                NWChem.RunOnMedivir(Files2Run[(i*MaxCon):], settings)
        
        elif settings.DFT == 'j':
            print '\nRunning Jaguar locally...'
            Jaguar.RunJaguar(Files2Run, settings)

    if numDS < 2:
        print "DP4 requires at least 2 candidate structures!"
    else:
        allargs = []
        for i in range(numDS):
            allargs.append(settings.NTaut)
            allargs.extend(inpfiles[i*settings.NTaut:(i+1)*settings.NTaut])
        allargs.append(ExpNMR)
        DP4outp = NMRAnalysis.main(numDS, settings, *allargs)
        print '\nWriting the DP4 output to DP4outp'
        DP4_ofile = open(allargs[-1] + '.dp4', 'w')
        DP4_ofile.write(DP4outp)
        DP4_ofile.close()
        print 'DP4 process completed successfully.'


def getScriptPath():
    return os.path.dirname(os.path.realpath(sys.argv[0]))


def SetTMSConstants():
    
    TMSfile = open(settings.ScriptDir + '/TMSdata', 'r')
    TMSdata = TMSfile.readlines()
    TMSfile.close()
    
    for i, line in enumerate(TMSdata):
        buf = line.split(' ')
        if len(buf)>1:
            if settings.Solvent != '':
                if buf[0].lower() == settings.Functional.lower() and \
                   buf[1].lower() == settings.BasisSet.lower() and \
                   buf[2].lower() == settings.Solvent.lower():
                    
                    print "Setting TMS references to " + buf[3] + " and " + \
                        buf[4] + "\n"
                    settings.TMS_SC_C13 = float(buf[3])
                    settings.TMS_SC_H1 = float(buf[4])
                    return
            else:
                if buf[0].lower() == settings.Functional.lower() and \
                   buf[1].lower() == settings.BasisSet.lower() and \
                   buf[2].lower() == 'none':
                    
                    print "Setting TMS references to " + buf[3] + " and " + \
                        buf[4] + "\n"
                    settings.TMS_SC_C13 = float(buf[3])
                    settings.TMS_SC_H1 = float(buf[4])
                    return
    
    print "No TMS reference data found for these conditions, using defaults\n"
    print "Unscaled shifts might be inaccurate, use of unscaled models is" + \
        " not recommended."


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='PyDP4 script to setup\
    and run Tinker, Gaussian (on ziggy) and DP4')
    parser.add_argument('-m', '--mm', help="Select molecular mechanics program,\
    t for tinker or m for macromodel, default is m", choices=['t', 'm'],
    default='m')
    parser.add_argument('-d', '--dft', help="Select DFT program, j for Jaguar,\
    g for Gaussian, n for NWChem, z for Gaussian on ziggy, d for Gaussian on \
    Darwin, w for NWChem on ziggy, m for NWChem on Medivir cluster, default is z",
        choices=['j', 'g', 'n', 'z', 'w', 'm', 'd'], default='z')
    parser.add_argument('--StepCount', help="Specify\
    stereocentres for diastereomer generation")
    parser.add_argument('StructureFiles', nargs='+', default=['-'], help=
    "One or more SDF file for the structures to be verified by DP4. At least one\
    is required, if automatic diastereomer and tautomer generation is used.\
    One for each candidate structure, if automatic generation is not used")
    parser.add_argument("ExpNMR", help="Experimental NMR description, assigned\
    with the atom numbers from the structure file")
    parser.add_argument("-s", "--solvent", help="Specify solvent to use\
    for dft calculations")
    parser.add_argument("-q", "--queue", help="Specify queue for job submission\
    on ziggy", default='s1')
    parser.add_argument("--TimeLimit", help="Specify job time limit for jobs\
    on ziggy or darwin", type=int)
    parser.add_argument("-t", "--ntaut", help="Specify number of explicit\
    tautomers per diastereomer given in structure files, must be a multiple\
    of structure files", type=int, default=1)
    parser.add_argument("--nProc", help="Specify number of processor cores\
    to use for Gaussian calculations", type=int, default=1)
    parser.add_argument("--batch", help="Specify max number of jobs per batch",
    type=int, default=75)
    parser.add_argument("-l", "--ConfLimit", help="Specify maximum number of \
    conformers per structure. If above this, adaptive RMSD pruning will be \
    performed", type=int, default=100)
    parser.add_argument("--MaxConfE", help="Specify maximum MMFF energy \
    allowed before conformer is discarded before DFT stage", type=float,\
    default=settings.MaxCutoffEnergy)
    parser.add_argument("--StrictConfLimit", help="Strictly enforce per struct \
    conf limit at the cost of abandoning consistent RMSD cutoff value", action="store_true")
    parser.add_argument("--Cluster", help="Use HDBSCAN clustering algorithm to decide which" \
                        + " conformers to calculate", action="store_true")
    parser.add_argument("-r", "--rot5", help="Manually generate conformers for\
    5-memebered rings", action="store_true")
    parser.add_argument("--jJ", help="Calculate coupling constants at DFT\
    level and use in analysis", action="store_true")
    parser.add_argument("--jFC", help="Calculate Fermi contact term of\
    coupling constants at DFT level level and use in analysis", action="store_true")
    parser.add_argument("--jK", help="Use Karplus-type equation to calculate\
    coupling constants and use in analysis", action="store_true")
    parser.add_argument('-J', '--JDir', help="Specify the location for\
    the corresponding output files containing coupling constants for the conformers.\
    Useful when NMR and coupling constants need to be calculated at different levels.")
    parser.add_argument('--ra', help="Specify ring atoms, for the ring to be\
    rotated, useful for molecules with several 5-membered rings")
    parser.add_argument('-S', '--Stats', help="Specify the stats model and\
    parameters")
    parser.add_argument('--CP3', help="Calculate CP3 instead of DP4. Recommended\
    when 2 experimental sets of data need to be matched to 2 calculated sets.\
    Experimental NMR argument needs to be provided in the form 'ExpNMR1,ExpNMR2'",
    action="store_true")
    parser.add_argument('--JStats', help="Specify the stats model and\
    parameters for coupling constants")
    parser.add_argument('-E', '--EnergyDir', help="Specify the location for\
    the corresponding output files containing the energies of the conformers.\
    Useful when NMR and energies need to be calculated at different levels.")
    parser.add_argument("--AssumeDFTDone", help="Assume RMSD pruning, DFT setup\
    and DFT calculations have been run already", action="store_true")
    parser.add_argument("--UseExistingInputs", help="Use previously generated\
    DFT inputs, avoids long conf pruning and regeneration", action="store_true")
    parser.add_argument("--NoConfPrune", help="Skip RMSD pruning, use all\
    conformers in the energy window", action="store_true")
    parser.add_argument("--OnlyConfS", help="Quit after conformational search",
                        action="store_true")
    parser.add_argument("--Renumber", help="Renumber the atoms in\
    diastereomers according to renumbering map in the specified file. Useful\
    when analysing manually drawn input structures")
    parser.add_argument("-g", "--GenOnly", help="Only generate diastereomers\
    and tinker input files, but don't run any calculations", action="store_true")
    parser.add_argument('-c', '--StereoCentres', help="Specify\
    stereocentres for diastereomer generation")
    parser.add_argument('-T', '--GenTautomers', help="Automatically generate\
    tautomers", action="store_true")
    parser.add_argument('-o', '--DFTOpt', help="Optimize geometries at DFT\
    level before NMR prediction", action="store_true")
    parser.add_argument('--PM6Opt', help="Optimize geometries at PM6\
    level before NMR prediction", action="store_true")
    parser.add_argument('--PM7Opt', help="Optimize geometries at PM7\
    level before NMR prediction", action="store_true")
    parser.add_argument('--HFOpt', help="Optimize geometries at HF\
    level before NMR prediction", action="store_true")
    parser.add_argument('--M06Opt', help="Optimize geometries at M062X\
    level before NMR prediction", action="store_true")
    parser.add_argument("--OptCycles", help="Specify max number of DFT geometry\
    optimization cycles", type=int, default=settings.MaxDFTOptCycles)
    parser.add_argument('-n', '--Charge', help="Specify\
    charge of the molecule. Do not use when input files have different charges")
    parser.add_argument('-b', '--BasicAtoms', help="Generate protonated states\
    on the specified atoms and consider as tautomers")
    parser.add_argument('-B', '--BasisSet', help="Selects the basis set for\
    DFT calculations", default='6-31g(d,p)')
    parser.add_argument('-F', '--Functional', help="Selects the functional for\
    DFT calculations", default='b3lyp')
    parser.add_argument('-x', '--OtherNuclei', help="Print predictions for\
     other nuclei")
    parser.add_argument('-f', '--ff', help="Selects force field for the \
    conformational search, implemented options 'mmff' and 'opls' (2005\
    version)", choices=['mmff', 'opls'], default='mmff')
    args = parser.parse_args()
    print args.StructureFiles
    print args.ExpNMR
    settings.Title = args.ExpNMR[:-3]
    settings.NTaut = args.ntaut
    settings.DFT = args.dft
    settings.queue = args.queue
    settings.ScriptDir = getScriptPath()
    settings.ForceField = args.ff
    settings.PerStructConfLimit = args.ConfLimit
    settings.MaxCutoffEnergy = args.MaxConfE
    settings.BasisSet = args.BasisSet
    settings.Functional = args.Functional
    settings.nProc = args.nProc
    settings.MaxConcurrentJobs = args.batch
    settings.MaxDFTOptCycles = args.OptCycles
    
    if settings.DFT == 'd' and not args.TimeLimit:
        print "For calculations on Darwin explicit time limit in hours " + \
            "must be specified, exiting..."
        quit()
    if args.Renumber is not None:
        settings.RenumberFile = args.Renumber
    if args.OtherNuclei:
        settings.OtherNuclei = args.OtherNuclei
    if args.TimeLimit:
        settings.TimeLimit = args.TimeLimit
    if args.jJ:
        settings.jJ = True
        settings.jFC = False
        settings.jKarplus = False
    if args.jFC:
        settings.jFC = True
        settings.jJ = False
        settings.jKarplus = False
    if args.jK:
        settings.jKarplus = True
        settings.jJ = False
        settings.jFC = False
    if args.JDir is not None:
        settings.JDir = args.JDir
    if args.EnergyDir is not None:
        settings.EnergyDir = args.EnergyDir
    else:
        settings.EnergyFolder = os.getcwd()
    if args.Stats is not None:
        settings.StatsModel = (args.Stats)[0]
        settings.StatsParamFile = (args.Stats)[1:]
    if args.CP3:
        settings.CP3 = True
    if args.JStats is not None:
        settings.JStatsModel = (args.JStats)[0]
        settings.JStatsParamFile = (args.JStats)[1:]
    if args.mm == 't':
        settings.MMTinker = True
        settings.MMMacromodel = False
    else:
        settings.MMMacromodel = True
        settings.MMTinker = False
    if args.OnlyConfS:
        settings.OnlyConfS = True
    if args.DFTOpt:
        settings.DFTOpt = True
    if args.M06Opt:
        settings.M06Opt = True
    if args.HFOpt:
        settings.HFOpt = True
    if args.PM6Opt:
        settings.PM6Opt = True
    if args.PM7Opt:
        settings.PM7Opt = True
    if args.BasicAtoms is not None:
        settings.BasicAtoms =\
            [int(x) for x in (args.BasicAtoms).split(',')]
        settings.GenProt = True
    if args.StepCount is not None:
        settings.MMstepcount = int(args.StepCount)
    if args.Charge is not None:
        settings.charge = int(args.Charge)
    if args.GenTautomers:
        settings.GenTaut = True
    if args.StereoCentres is not None:
        settings.SelectedStereocentres =\
            [int(x) for x in (args.StereoCentres).split(',')]
    if args.GenOnly:
        settings.GenOnly = True
    if args.StrictConfLimit:
        settings.StrictConfLimit = True
    if args.Cluster:
        settings.Cluster = True
    if args.NoConfPrune:
        settings.ConfPrune = False
    if args.AssumeDFTDone:
        settings.AssumeDone = True
    if args.UseExistingInputs:
        settings.UseExistingInputs = True
    if args.solvent:
        settings.Solvent = args.solvent
    if args.rot5:
        settings.Rot5Cycle = True
    if args.ra is not None:
        settings.RingAtoms =\
            [int(x) for x in (args.ra).split(',')]
    
    if settings.StatsParamFile != '':
        if os.path.isfile(settings.StatsParamFile):
            print "Statistical parameter file found at " + settings.StatsParamFile
        elif (not os.path.isfile(settings.StatsParamFile)) and\
            os.path.isfile(settings.ScriptDir+settings.StatsParamFile):
                settings.StatsParamFile = settings.ScriptDir+settings.StatsParamFile
                print "Statistical parameter file found at " + settings.StatsParamFile
        elif (not os.path.isfile(settings.StatsParamFile)) and\
            (not os.path.isfile(settings.ScriptDir+settings.StatsParamFile)):
            print "Stats file not found, quitting."
            quit()
    
    SchrodEnv = os.getenv('SCHRODINGER')
    if SchrodEnv != None:
        settings.SCHRODINGER = SchrodEnv
    #settings.SCHRODINGER = '/usr/local/shared/schrodinger/current'

    now = datetime.datetime.now()
    settings.StartTime = now.strftime('%d%b%H%M')

    with open('cmd.log', 'a') as f:
        f.write(' '.join(sys.argv) + '\n')

    inpfiles = [x.split('.')[0] for x in args.StructureFiles]
    
    if len(inpfiles) == 1:
        main(inpfiles[0], args.ExpNMR, 1)
    else:
        main(inpfiles, args.ExpNMR, len(inpfiles))

    #main()
