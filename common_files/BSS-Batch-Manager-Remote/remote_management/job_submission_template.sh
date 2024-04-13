#! /bin/bash

#Set runtime limit (HHH:MM:SS)
#$ -l s_rt=150:00:00 

#Set name of job and prefix of its output file
#$ -N q0

job_dir="/u/mw/"
export WORK="/$TMPDIR/$USER/$JOB_ID"
mkdir -p $WORK
cd $job_dir
cp -r * $WORK
cd $WORK
./bond_switch_simulator.exe
cp -r  * $job_dir
rm -Rf $WORK

