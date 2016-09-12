#!/bin/bash
#
# ***************************************************************************
# Name                 : Planet Labs Downloads Geojson Scenes
# Description          : Download region images from Geojson layer(scene ID).
#                        Geojson layer from: pl_get_geojson_scenes.sh
#
# Arguments:           $1: Geojson layer
#                      $2: ID of Geometry(used by pl_get_geojson_scenes.sh)
#
# Dependencies         : $PL_API_KEY, jq(https://stedolan.github.io/jq/), 
#                        pl_download_region_scene.sh
#
# ***************************************************************************
# begin                : 2016-08-28 (yyyy-mm-dd)
# copyright            : (C) 2016 by Luiz Motta
# email                : motta dot luiz at gmail.com
# ***************************************************************************
#
# Revisions
#
# 0000-00-00:
# - None
# 
# ***************************************************************************
#
# Example:
#   pl_download_geojson_scenes.sh geojson_layer 1
#
# ***************************************************************************
# *                                                                         *
# *   This program is free software; you can redistribute it and/or modify  *
# *   it under the terms of the GNU General Public License as published by  *
# *   the Free Software Foundation; either version 2 of the License, or     *
# *   (at your option) any later version.                                   *
# *                                                                         *
# ***************************************************************************
#
msg_error(){
  local name_script=$(basename $0)
  echo "Total of arguments '"$entryargs"' wrong!"
  echo "Usage: $name_script <geojson_layer> <geom_id>" >&2
  echo '<geojson_layer> is the name of file from "pl_get_geojson_scenes.sh"' >&2
  echo '<geom_id> is the ID of geometry' >&2
  exit 1
}
#
totalargs=2
entryargs=$#
#
if [ $entryargs -ne $totalargs ] ; then
  msg_error
  exit 1
fi
#
geojson_layer=$1
geom_id=$2
#
if [ ! -f "$geojson_layer" ] ; then
  echo "The file '$geojson_layer' not exist" >&2
  exit 1
fi
#
# Create list of scnene_id and Geojson
l_scene_geom=$(mktemp)
jq -c '.["features"][] | .properties["id"],"@@",.geometry,"!!"' $geojson_layer \
| tr -d '\n' | sed -e $'s/"!!"/\'\\\n/g' \
| sed -e $'s/"@@"/@\'/g' > $l_scene_geom
#
printf "\nProcessing..."
# Run download
pids=""
for item in $(cat $l_scene_geom)
do
  args="$(echo $item | sed 's/@/ /g' ) $geom_id"
  echo "pl_download_region_scene.sh $args" | bash &
  pids="$pids $!"
done
wait $pids
total=$(cat $l_scene_geom | wc -l)
rm $l_scene_geom
#
printf "\rCreated regions of scenes (total %d)%-50s\n" $total ' '
exit 0
