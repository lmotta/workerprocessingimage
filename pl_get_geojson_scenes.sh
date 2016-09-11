#!/bin/bash
#
# ***************************************************************************
# Name                 : Planet Labs Get Geojson Scenes
# Description          : Get Geojson from query for Planet Labs API V.1.
#
# Arguments:           $1: Initial  date (yyyy-mm-dd)
#                      $2: Finished date (yyyy-mm-dd)
#                      $3: Geojson (Geometry)
#                      $4: ID of Geometry
#
# Dependencies         : $PL_API_KEY, jq(https://stedolan.github.io/jq/), curl
#                        cut_geojsons.py
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
#   pl_get_geojson_scenes.sh "2016-07-01" "2016-08-27" Geometry 1
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
create_search_json(){
  # External: date1, date2, geojson, search_json
  local filterGeom='{"type": "GeometryFilter","field_name": "geometry","config":'$geojson'}'
  local dates='{"gte": "'$date1'T00:00:00Z","lte": "'$date2'T00:00:00Z" }'
  local filterDate='{"type": "DateRangeFilter","field_name":"catalog::acquired","config":'$dates'}'
  local headers="--header 'Content-Type: application/json' --header 'Accept: application/json'"
  local http="https://api.planet.com/v1/catalogs/grid-utm-25km/quick-search?_page_size=100"
  local filter='{"type": "AndFilter","config": ['$filterDate','$filterGeom']}'
  local filterName='date_geom'
  local data='{"filter":'$filter',"name": "'$filterName'"}'
  echo "curl --silent --show-error -X POST $headers -u $PL_API_KEY: -d '$data' '$http'" | bash - > $search_json
}
add_features(){
  # External: search_json,features 
  local total=$(jq '.["features"] | length' $search_json)
  if [ $total -ne 0 ] ; then
    local properties='id: .id'
    properties+=',satellite_id: .properties["catalog::satellite_id"],grid_cell: .properties["catalog::grid_cell"],provider: .properties["catalog::provider"]'
    properties+=',resolution: .properties["catalog::resolution"],acquired: .properties["catalog::acquired"]'
    properties+=',cloud_cover: .properties["catalog::cloud_cover"],usable_data: .properties["catalog::usable_data"]'
    properties+=',view_angle: .properties["catalog::view_angle"],sun_elevation: .properties["catalog::sun_elevation"],sun_azimuth: .properties["catalog::sun_azimuth"]'
    local filter='{ "type": "Feature", "properties": {'$properties'}, geometry: .geometry }'  
    local features_tmp=$(echo "jq '[.[\"features\"][] | $filter ]' $search_json" | bash -)
    if [ -z "$features" ] ; then
      features=${features_tmp:1:-1}
    else
      features+=","${features_tmp:1:-1}
    fi
    local link=$(jq '.["_links"]["_next"]' $search_json | sed 's/"//g')
    curl --silent --show-error -G $link -u $PL_API_KEY: > $search_json
    add_features
  else
    features="["$features"]"
  fi
}
create_scenes_geojson(){
  # External: geom_id, date1, date2, features
  scenes_geojson="scenes_geom"$geom_id"_"$date1"_"$date2".geojson"
  local header='"type": "FeatureCollection", "crs": { "type": "name", "properties": { "name": "urn:ogc:def:crs:OGC:1.3:CRS84" } }'
  echo '{ '$header',"features": '$features' }' > $scenes_geojson
}
msg_error(){
  local name_script=$(basename $0)
  echo "Total of arguments '"$entryargs"' wrong!"
  echo "Usage: $name_script <date1> <date2> <geojson> <geom_id>" >&2
  echo '<date1>   is the initial  date(Ex.: "2016-07-01")' >&2
  echo '<date2>   is the finished date(Ex.: "2016-08-27")' >&2
  echo '<geojson> is the geometry' >&2
  echo "Ex. geojson = '"'{"type": "Polygon", "coordinates": [[ [-57.8006, -14.6254], ..., [-57.8006, -14.6254]]] }'"'" >&2
  echo '<geom_id> is the ID of geometry' >&2
  exit 1
}
#
totalargs=4
entryargs=$#
#
if [ $entryargs -ne $totalargs ] ; then
  msg_error
  exit 1
fi
#
date1=$1
date2=$2
geojson=$3
geom_id=$4
#
printf "\nProcessing..."
#
search_json=$(mktemp)
create_search_json
features=""
add_features
rm $search_json
vresult=$(echo "cut_geojsons.py '$features' '$geojson'" | bash -)
isok=$(echo $vresult | jq '.["isOk"]')
if [ $isok -eq 0 ] ; then
  msg=$(echo $vresult | jq '.["msg"]')
  printf "\rError: "
  echo $msg
  exit 1
fi
features=$(echo $vresult | jq '.["geojsons"]')
create_scenes_geojson
#
total=$(jq '.["features"] | length' $scenes_geojson)
printf "\rCreated '%s'(total %d features)\n" $scenes_geojson $total
#
exit 0
