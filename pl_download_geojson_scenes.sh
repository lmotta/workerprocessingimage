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
  # External: geom_id, date1, date2, 
  scenes_geojson="scenes_geom"$geom_id"_"$date1"_"$date2".geojson"
  local header='"type": "FeatureCollection", "crs": { "type": "name", "properties": { "name": "urn:ogc:def:crs:OGC:1.3:CRS84" } }'
  echo '{ '$header',"features": '$features' }' > $scenes_geojson
}
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
echo "Created regions of scenes (total %d )" $total
exit 0
