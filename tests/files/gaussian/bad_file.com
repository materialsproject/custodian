%chk=Checkpoint.chk
%mem=48GB
%NProcShared=28
#P PBE1PBE/6-31+G* opt scf=(maxcycle=100) guess=read geom=check

H10 C4 O2

0 1

