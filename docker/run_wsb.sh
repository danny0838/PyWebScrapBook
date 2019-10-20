#!/bin/bash

#
# Boot script for WSB daemon.
#
# @verions 1.0
# @fecha 14/09/2019
# @author Javier Pastor
# @license GPL 3.0
#

FILE_CFG=config.ini
PATH_DATA=/data
PATH_WSB=$PATH_DATA/.wsb
PATH_STORE=$PATH_DATA/store
PATH_CFG=$PATH_WSB/$FILE_CFG
PATH_CFG_DEFAULT=/$FILE_CFG
EXEC_WSB=/usr/local/bin/wsb
EXEC_EXTERNAL=$PATH_DATA/run_wsb.sh
WSB_VERSION=$(${EXEC_WSB} --version | awk '{print $2;}')

fun_check_path_data() {
	if [[ ! -d $PATH_DATA ]]; then
		mkdir -p $PATH_DATA
		[[ $? -gt 0 ]] && return 1 || return 0
	fi
}

fun_check_path_wsb() {
	if [[ ! -d $PATH_WSB ]]; then
		mkdir -p $PATH_WSB
		[[ $? -gt 0 ]] && return 1 || return 0
	fi
}

fun_check_path_store() {
	if [[ ! -d $PATH_STORE ]]; then
		mkdir -p $PATH_STORE
		[[ $? -gt 0 ]] && return 1 || return 0
	fi
}

fun_remove_config() {
	if [[ -f $PATH_CFG ]]; then
		rm -f $PATH_CFG
		[[ $? -gt 0 ]] && return 1 || return 0
	fi
}

fun_copy_default_config() {
	fun_check_path_wsb
	fun_remove_config
	cp -f $PATH_CFG_DEFAULT $PATH_CFG
}

fun_gen_config() {
	fun_check_path_wsb
	$EXEC_WSB --root $PATH_DATA config -ba
}

fun_check_chown() {
	if [[ ! -d $PATH_DATA ]]; then
		chown root:root $PATH_DATA -R
	fi
	if [[ ! -d $PATH_WSB ]]; then
		chown root:root $PATH_WSB -R
	fi
	if [[ ! -d $PATH_STORE ]]; then
		chown root:root $PATH_STORE -R
	fi
}


if [[ -f $EXEC_EXTERNAL ]]; then
	echo "*** RUN EXTERNAL ***"
	sh $EXEC_EXTERNAL
else
	echo "Starting webscrapbook $WSB_VERSION..."
	fun_check_path_data
	fun_check_path_store
	if [ -f $PATH_CFG ]; then
		fun_check_chown
	else
		fun_gen_config
		fun_copy_default_config
		fun_check_chown
	fi
	$EXEC_WSB --root $PATH_DATA serve
fi

