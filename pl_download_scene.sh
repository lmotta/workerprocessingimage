#!/bin/bash
#
# ***************************************************************************
# Name                 : Planet Labs Download Scene
# Description          : Download scene from query for Planet Labs API V.1.
#
# Arguments:           $1: scene_id
#
# Dependencies         : $PL_API_KEY, jq(https://stedolan.github.io/jq/), curl
#
# ***************************************************************************
# begin                : 2016-08-27 (yyyy-mm-dd)
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
#   pl_download_scene.sh 218280_2132411_2016-08-09_0c60
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
set_analytic(){
  # External: assets_json 
  local assets_type=$(jq 'keys' $assets_json)
  analytic="analytic_dn"
  if [ $(echo $assets_type | grep -c $analytic) -eq 0 ]
  then
    analytic="analytic"
  fi
}
activate_asset(){
  # External: assets_json
  local asset=$1
  local activate=$(jq '.["'$asset'"]["files"]["http"]["_links"]["activate"]' $assets_json | sed 's/"//g')
  curl --silent --show-error -X POST $activate -u $PL_API_KEY:
}
download_asset(){
  # External: assets_json
  local asset=$1
  local location=$(jq '.["'$asset'"]["files"]["http"]["location"]' $assets_json | sed 's/"//g')
  curl --silent --show-error -o $scene_id"_"$asset".tif" -L $location
}
msg_error(){
  local name_script=$(basename $0)
  echo "Total of arguments '"$entryargs"' wrong!"
  echo "Usage: $name_script <scene_id>" >&2
  echo '<scene_id>   is the ID of scene (Ex.: 218280_2132411_2016-08-09_0c60)' >&2
  exit 1
}
#
totalargs=1
entryargs=$#
#
if [ $entryargs -ne $totalargs ] ; then
  msg_error
  exit 1
fi
#
scene_id=$1
#
printf "\nProcessing..."
#
pl1_catalog="https://api.planet.com/v1/catalogs/grid-utm-25km/items/"
assets_json=$(mktemp)
curl --silent --show-error -G $pl1_catalog$scene_id"/assets/" -u $PL_API_KEY: > $assets_json
set_analytic
activate_asset "udm"
activate_asset $analytic
curl --silent --show-error -G $pl1_catalog$scene_id"/assets/" -u $PL_API_KEY: > $assets_json
download_asset "udm"
download_asset $analytic
rm $assets_json
#
printf "\rDownload scene '%s' ('udm' and '%s')\n" $scene_id $analytic
#
exit 0
