#!/bin/bash
msg_error(){
  local name_script=$(basename $0)
  echo "Usage: $name_script <image>" >&2
  echo "<image> scene (ex.: 20160421_110213_0c53)" >&2
  exit 1
}
#
totalargs=1
#
if [ $# -ne $totalargs ] ; then
  msg_error
  exit 1
fi
scene=$1
url="https://api.planet.com/v0/scenes/ortho/"$scene"/full?product=analytic"
wget --user=$PL_API_KEY --password='' --output-document $scene".tif" $url
