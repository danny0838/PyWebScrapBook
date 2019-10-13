#!/bin/bash
set -e

CMD=${@:1:1}

case "$CMD" in  
	"" )
		echo "CMD IS NULL!!!"
		;;
	"start" )
		exec /run_wsb.sh
		;;
	* ) 
		 # Run custom command. Thanks to this line we can still use 
		 # "docker run our_image /bin/bash" and it will work  
		 exec $CMD ${@:2}
		 ;;
esac