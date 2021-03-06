# -*- coding: utf-8 -*-
"""
Created on Tue Nov  4 12:46:34 2014

@author: ke291

Extracts NMR shifts from Gaussian output files
"""

import math

gasConstant = 8.3145
temperature = 298.15
hartreeEnergy = 2625.499629554010

def main(settings, *args):

    labels = []
    allshieldings = []
    energies = []
    FCmatrices = []
    Jmatrices = []
    Jlabels = []

    #For every file run ReadShieldings and store the extracted shielding
    #constants
    #Also run ReadCouplingConstants - will return empty matrices if none found
    for f in args:
        (labels, shieldings) = ReadShieldings(f)
        allshieldings.append(shieldings)
        energy = ReadEnergy(settings.EnergyDir + f)
        energies.append(energy)
        if settings.jKarplus:
            import Karplus
            Jmat, Jlabels = Karplus.Karplus(f + ".out", "g09")
            Jmatrices.append(Jmat)
            FCmatrices.append(Jmat) #Jmat used as a placeholder value for FCmat
        else:
            FCmat, Jmat, Jlabels = ReadCouplingConstants(settings.JDir + f,\
                labels)
            FCmatrices.append(FCmat)
            Jmatrices.append(Jmat)

    minE = min(energies)

    relEs = []

    #Calculate rel. energies in kJ/mol
    for e in energies:
        relEs.append(((e-minE)*hartreeEnergy))

    populations = []

    #Calculate Boltzmann populations
    for e in relEs:
        populations.append(math.exp(-e*1000/(gasConstant*temperature)))

    q = sum(populations)

    for i in range(0, len(populations)):
        populations[i] = populations[i]/q
    
    #Make a list of populations and corresponding files for reporting
    #significant conformations
    from operator import itemgetter
    ConfsPops = [list(x) for x in zip(args, populations)]
    ConfsPops.sort(key=itemgetter(1), reverse=True)
    totpop = 0
    i = 0
    while totpop<0.8:
        totpop += ConfsPops[i][1]
        i += 1
    SigConfs = ConfsPops[:i]
        
    #Calculate Boltzmann weighed shielding constants
    #by summing the shifts multiplied by the isomers population
    Natoms = len(labels)
    BoltzmannShieldings = []

    for atom in range(Natoms):
        shielding = 0
        for conformer in range(len(allshieldings)):
            shielding = shielding + allshieldings[conformer][atom] * \
                populations[conformer]
        BoltzmannShieldings.append(shielding)

    if len(Jlabels) < 2:# or not any([settings.jJ, settings.jFC, settings.jKarplus]):
        return (relEs, populations, labels, BoltzmannShieldings, [""],
                [0], [0], SigConfs)
    else:
        #Calculate Boltzmann weighed coupling constants (FC and J)
        Natoms = len(Jlabels)
        BoltzmannFC = [[0.0 for i in range(Natoms)] for i in range(Natoms)]
        BoltzmannJ = [[0.0 for i in range(Natoms)] for i in range(Natoms)]
        
        if settings.jJ or settings.jFC:
            for a1 in range(Natoms):
                for a2 in range(Natoms):
                    coupling = 0.0
                    for conf in range(len(FCmatrices)):
                        coupling = coupling + FCmatrices[conf][a1][a2] * \
                            populations[conf]
                        BoltzmannFC[a1][a2] = coupling

        for a1 in range(Natoms):
            for a2 in range(Natoms):
                coupling = 0.0
                for conf in range(len(Jmatrices)):
                    coupling = coupling + Jmatrices[conf][a1][a2] * \
                        populations[conf]
                    BoltzmannJ[a1][a2] = coupling

        return relEs, populations, labels, BoltzmannShieldings,\
            Jlabels, BoltzmannFC, BoltzmannJ, SigConfs


def ReadEnergy(GOutpFile):
    gausfile = open(GOutpFile + '.out', 'r')
    GOutp = gausfile.readlines()
    gausfile.close()
    
    for line in GOutp:
        if 'SCF Done:' in line:
            start = line.index(') =')
            end = line.index('A.U.')
            energy = float(line[start+4:end])
    
    return energy


def ReadShieldings(GOutpFile):
    
    print GOutpFile
    gausfile = open(GOutpFile + '.out', 'r')
    GOutp = gausfile.readlines()

    index = 0
    shieldings = []
    labels = []

    #Find the NMR shielding calculation section
    while not 'Magnetic shielding' in GOutp[index]:
        index = index + 1

    #Read shielding constants and labels
    for line in GOutp[index:]:
        if 'Isotropic' in line:
            data = filter(None, line.split(' '))
            shieldings.append(float(data[4]))
            labels.append(data[1]+data[0])

    gausfile.close()

    return labels, shieldings


def ReadCouplingConstants(GOutpFile, atomlabels):
    FCmat, FCmatlabels = ReadCMatrix(GOutpFile,
        'Fermi Contact (FC) contribution to J (Hz)')
    FCmat, FCmatlabels = RemoveAtomsMatrix(FCmat, FCmatlabels, atomlabels)
    Jmat, Jmatlabels = ReadCMatrix(GOutpFile,
                                   'Total nuclear spin-spin coupling J (Hz)')
    Jmat, Jmatlabels = RemoveAtomsMatrix(Jmat, Jmatlabels, atomlabels)
    return FCmat, Jmat, Jmatlabels


def RemoveAtomsMatrix(mat, matlabels, atomlabels):

    if len(mat) < 2:
        return mat, matlabels

    ToKeep = [x[1:] for x in atomlabels if x[0] == 'H']
    PrunedMatrix = []
    PrunedLabels = []
    for y in range(len(mat)):
        if matlabels[y] in ToKeep:
            row = []
            PrunedLabels.append(matlabels[y])
            for x in range(len(mat)):
                if matlabels[x] in ToKeep:
                    row.append(mat[y][x])
            PrunedMatrix.append(row)
    return PrunedMatrix, PrunedLabels


def ReadCMatrix(GOutpFile, title):
    gausfile = open(GOutpFile + '.out', 'r')
    GOutp = gausfile.readlines()

    index = 0

    #Find the start of matrix
    while not title in GOutp[index]:
        index = index + 1
        if index == len(GOutp):
            return [0], ['']

    start = index
    end = 0
    started = False
    #Count total included atoms
    for i, line in enumerate(GOutp[index:], index):
        data = filter(None, line.split(' '))
        if 'D' in data[-1]:
            if not started:
                started = True
                start = i
        else:
            if started:
                end = i
                break

    natoms = end - start
    matlabels = []
    Matrix = [[0.0 for i in range(natoms)] for i in range(natoms)]
    index = start-1
    coln = 0
    rown = 0

    while unicode(filter(None, GOutp[index].split(' '))[-2]).isnumeric():
        index += 1
        data = filter(None, GOutp[index].split(' '))
        while 'D' in data[-1]:
            if len(matlabels) < natoms:
                matlabels.append(data[0])
            jvals = [float(x.replace('D', 'E')) for x in data[1:]]
            Matrix[rown][coln:coln+len(jvals)] = jvals
            rown += 1
            index += 1
            data = filter(None, GOutp[index].split(' '))
        coln += 5
        rown = coln
    for x in range(len(Matrix)): Matrix[x][x] = 0.0
    for x in range(len(Matrix)):
        for y in range(x, len(Matrix)):
            Matrix[x][y] = Matrix[y][x]
    return Matrix, matlabels
