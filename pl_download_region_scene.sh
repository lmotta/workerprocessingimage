#!/bin/bash
#
# ***************************************************************************
# Name                 : Planet Labs Download Scene
# Description          : Download scene from query for Planet Labs API V.1.
#
# Arguments:           $1: scene_id
#                      $2: Geojson (Geometry)
#                      $4: ID of Geometry
#
# Dependencies         : $PL_API_KEY, jq(https://stedolan.github.io/jq/), curl,
#                        bbox-geojson.py
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
#   pl_download_region_scene.sh 218280_2132411_2016-08-09_0c60 Geometry 1
#   * Geometry: '{"type": "Polygon", "coordinates": [[ [-57.8006, -14.6254], ..., [-57.8006, -14.6254]]] }'
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
set_projwin(){
  # External: geojson
  local vresult=$(echo "bbox-geojson.py '$geojson'" | bash -)
  local isok=$(echo $vresult | jq '.["isOk"]')
  if [ $isok -eq 0 ] ; then
    local msg=$(echo $vresult | jq '.["msg"]')
    printf "\rError: "
    echo $msg
    exit 1
  fi
  projwin=$(echo $vresult | jq '.["bbox"]')
  projwin=${projwin:1:-1}
}
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
  # External: assets_json, projwin, geom_id
  local asset=$1
  local location=$(jq '.["'$asset'"]["files"]["http"]["location"]' $assets_json | sed 's/"//g')
  gdal_translate -q -projwin_srs "EPSG:4326" -projwin $projwin "/vsicurl/"$location $scene_id"_geom"$geom_id"_"$asset".tif"
}
msg_error(){
  local name_script=$(basename $0)
  echo "Total of arguments '"$entryargs"' wrong!"
  echo "Usage: $name_script <scene_id> <geojson> <geom_id>" >&2
  echo '<scene_id>   is the ID of scene (Ex.: 218280_2132411_2016-08-09_0c60)' >&2
  echo '<geojson> is the geometry' >&2
  echo "Ex. geojson = '"'{"type": "Polygon", "coordinates": [[ [-57.8006, -14.6254], ..., [-57.8006, -14.6254]]] }'"'" >&2
  echo '<geom_id> is the ID of geometry' >&2
  exit 1
}
#
totalargs=3
entryargs=$#
#
if [ $entryargs -ne $totalargs ] ; then
  msg_error
  exit 1
fi
#
scene_id=$1
geojson=$2
geom_id=$3
#
set_projwin
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
echo "Created "$scene_id"_geo"$geom_id"(udm and "$analytic").tif"
exit 0
