#!/bin/zsh

# watch-ersatz mit cooler Statusleiste und hotkeys.
# needs expect-package (for unbuffer)

usage() {
    echo "Usage:
 $0 [options] command

Options:
  -b           beep if command has a non-zero exit
  -e           exit if command has a non-zero exit
  -n <secs>    seconds to wait between updates
  -h           display this help and exit
"
}

INT=2
XIT=?

zparseopts -D -E -- b=xbeep e=xexit n:=xint h=xhelp

CMD="$@"

if [ -n "$xhelp" ] ; then
   usage
   exit
fi

if [ -n "$xint" ]; then 
    if [[ ! "${xint[2]}" =~ "^[0-9]+$" ]] ; then
        echo "secs must be a number"
        exit 2
    fi
    INT="${xint[2]}"
fi

if [ "$CMD" = "" ] ; then
   usage
   echo -e "no command given"
   exit 1
fi


echo -ne "\e[?25l" # hide cursor
clear # also sets LINES and COLUMNS

# simple fallback: We cannot pipe output to keep colors for autodetecting 
# programs like ls or grep. So instead we clear the screen and execute.
DOIT() {
    echo -en "\e[2H\e[0J" # jump to second line & clear rest of screen
    zsh -c $CMD
}

# if expect is installed, we can run CMD in unbuffer (allocates pty) and pipe
# its output, so we can append "clear line" on each line and do not have to
# clear the screen before executing CMD to avoid flickering.
# but we must use a tempfile in order to keep the exitcode of CMD.
if which unbuffer >/dev/null ; then
    TMP="$(mktemp /tmp/watch_XXXX)"
    DOIT() {
        echo -en "\e[2H" # jump to second line
        unbuffer zsh -c $CMD &> "$TMP"
        ret=$?
        sed 's/$/[0K/' "$TMP"
        echo -en "\e[0J"
        return $ret
    }
fi


status() {
    # strings
    front1=" $CMD "
    front2=" [Ret $XIT] "
    middle1=" $(date "+%Y-%m-%d %H:%M:%S") "
    middle2=" (${INT} sec) "
    help=" [+]/[-] change interval  [Q]uit "
    # reduce status width, if necessary
    tfull="$front1$front2$middle1$middle2$help"
    if [ $COLUMNS -lt ${#tfull} ] ; then
        help="[+/-] [Q]"
        tfull="$front1$front2$middle1$middle2$help"
    fi
    if [ $COLUMNS -lt ${#tfull} ] ; then
        middle1=""
        tfull="$front1$front2$middle1$middle2$help"
    fi
    if [ $COLUMNS -lt ${#tfull} ] ; then
        help=""
        tfull="$front1$front2$middle1$middle2$help"
    fi
    
    # go to statusline and start printing it
    echo -en "\e[H\e[48;5;20m\e[37;1m $CMD \e[48;5;19m"
    if [ "$XIT" = "?" ] ; then
        echo -en "\e[38;5;19;22m"
    elif [ "$XIT" -ne 0 ] ; then
        echo -en "\e[91;22m"
    else
        echo -en "\e[92;22m"
    fi
    echo -en "$front2"
    echo -en "\e[48;5;17m\e[K"
    
    # try to center clock
    spleft=$(( ( COLUMNS - ${#tfull} ) / 2 + ${#front1} + ${#front2} ))
    echo -en "\e[1;${spleft}H\e[48;5;18m\e[37m$middle1$middle2"
    
    # help to the right
    echo -en "\e[1;$((COLUMNS - ${#help} + 1))H" # clear rest of line, jump to right
    echo -en "\e[48;5;53m\e[96m$help\e[0m"
}

finally() {
    echo -ne "\e[r\e[?25h\e[u" # reset scrolling, move and show cursor
    [ -n "$TMP" ] && rm "$TMP"
    exit 0
}
trap 'finally' SIGINT

# MAIN LOOP
while true; do
    echo -en "\e[2;${LINES}r" # do not scroll first row
    DOIT
    XIT=$?
    echo -ne "\e[s" # save cursor
    status
    echo -ne "\e[u" # restore cursor
    
    if [ $XIT -ne 0 -a -n "$xbeep" ] ; then
        echo -en "\a"
    fi
    if [ $XIT -ne 0 -a -n "$xexit" ] ; then
        status
        break
    fi
    
    #read -srn15 -t0.05 KEY # clear input buffer
    unset KEY
    read -srk1 -t$INT KEY
    case "$KEY" in
        +)  if [[ INT -ge 10 ]] ; then
                INT=$(printf "%d" $(( INT + 10 )))
            elif [[ INT -ge 1 ]] ; then
                INT=$(printf "%d" $(( INT + 1 )))
            else
                INT=$(LANG=C printf "%.1f" $(( INT + 0.1 ))) 
            fi
            if [[ INT -gt 120 ]] ; then
                INT=120
            fi
            ;;
        -)  if [[ INT -gt 10 ]] ; then
                INT=$(printf "%d" $(( INT - 10 )))
            elif [[ INT -gt 1 ]] ; then
                INT=$(printf "%d" $(( INT - 1 )))
            else
                INT=$(LANG=C printf "%.1f" $(( INT - 0.1 ))) 
            fi
            if [[ INT -lt 0.1 ]] ; then
                INT=0.1
            fi
            ;;
        q)  break ;;
        *)  ;;
    esac
done

finally
