#! /bin/bash
PATH=$1
if [[ -f $PATH ]]
then
    echo "True"
else
    echo "False"
fi
