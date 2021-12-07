#!/bin/sh

# X3  --   Starte X-Server ohne startx und xinit und so.

# basiert auf https://github.com/Earnestly/sx/blob/master/sx

# requires xauth Xorg

# Geänderte Änderungen:
#   - DISPLAY vom X auf tty1 ist :0 und nicht :1 
#   - default startskript ist ~/.xinitrc
#   - 1. Parameter kann eine andere xinitrc sein
#   - datadir nach ~/.local/share/xorg/

cleanup() {
    if [ "$pid" ] && kill -0 "$pid" 2> /dev/null; then
        kill -s TERM "$pid"
        wait "$pid"
        r=$?
    fi
    stty "$stty" || stty sane
    xauth remove :"$tty"
    exit "${r:-$?}"
}

stty=$(stty -g)
tty=$(tty)
tty=${tty#/dev/tty}
dsp=$tty
[ "$tty" == "1" ] && dsp=0

datadir=${XDG_DATA_HOME:-$HOME/.local/share/xorg}
mkdir -p "$datadir"

export XAUTHORITY=${XAUTHORITY:-$datadir/xauthority}
touch "$XAUTHORITY"

export XINITRC="$HOME/.xinitrc"
[ -n "$1" ] && export XINITRC="$1"

if [ ! -x "$XINITRC" ] ; then
    echo "$XINITRC is not executable"
    exit 1
fi

echo -e "\e[92mStart\e[0m Xorg on \e[1mtty$tty\e[0m (DISPLAY=\e[1m:$dsp\e[0m) using \e[1m$XINITRC\e[0m"
echo -e "========== $(date) Start Xorg on tty$tty (DISPLAY=:$dsp) using $XINITRC" >>/tmp/X.$dsp.log

trap 'cleanup' EXIT
xauth add :"$dsp" MIT-MAGIC-COOKIE-1 "$(od -An -N16 -tx /dev/urandom | tr -d ' ')"

# Xorg will check if its SIGUSR1 disposition is SIG_IGN and use this state to
# reply back to the parent process with its own SIGUSR1 as an indication it is
# ready to accept connections.
# Taking advantage of this feature allows us to launch our client directly
# from a SIGUSR1 handler and avoid the need to poll for server readiness.

trap 'DISPLAY=:$dsp "${@:-$XINITRC}" >>/tmp/X.$dsp.log 2>&1' USR1
(trap '' USR1 && exec Xorg :"$dsp" -dpi 96 -keeptty vt"$tty" -noreset -auth "$XAUTHORITY" 2>>/tmp/X.$dsp.log ) & pid=$!
wait "$pid"

echo -e "\e[91mStopped\e[0m Xorg on \e[1mtty$tty\e[0m (DISPLAY=\e[1m:$dsp\e[0m) using \e[1m$XINITRC\e[0m\r"
echo -e "========== $(date) Stopped Xorg on tty$tty (DISPLAY=:$dsp) using $XINITRC" >>/tmp/X.$dsp.log
