#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
/***************************************************************************
Name                 : Cut GeoJsons
Description          : Cut Geojsons with mold(other Geojson)
Arguments            : List of geoJsons an mold

                       -------------------
begin                : 2016-08-28
copyright            : (C) 2016 by Luiz Motta
email                : motta dot luiz at gmail.com

 ***************************************************************************/
"""

import sys, argparse, json

from osgeo import gdal, ogr
gdal.UseExceptions()
gdal.PushErrorHandler('CPLQuietErrorHandler')

def run(geojsons, geojson_mold):
  def getGeom(geojson):
    geom = ogr.CreateGeometryFromJson( geojson )
    if geom is None:
      msg = gdal.GetLastErrorMsg()
      return { 'isOk': False, 'msg': msg }
    return { 'isOk': True, 'geom': geom }
  
  def cutGeometry(geojson):
    vreturn = getGeom( geojson )
    if not vreturn['isOk']:
      return vreturn
    geom = vreturn['geom']
    geomInter = geom_mold.Intersection( geom )
    geom.Destroy()
    geojsonInter = json.loads( geomInter.ExportToJson() )
    geomInter.Destroy()
    return { 'isOk': True, 'geojson': geojsonInter }

  vreturn = getGeom( geojson_mold )
  if not vreturn['isOk']:
    msg = "Geojson Mold: %s" % vreturn['msg']
    print '{ "isOk": 0, "msg": "%s" }' % msg
    return 1
  geom_mold = vreturn['geom']
  
  geoms_json = json.loads( geojsons )
  for id in xrange( len( geoms_json ) ):
    vreturn = cutGeometry( json.dumps( geoms_json[id]["geometry"] ) )
    if not vreturn['isOk']:
      msg = "Geojson item '%d': %s" % ( id+1, vreturn['msg'] )
      print '{ "isOk": 0, "msg": "%s" }' % msg
      return 1
    geoms_json[id]["geometry"] = vreturn['geojson']
  
  geom_mold.Destroy()
  print '{ "isOk": 1, "geojsons": %s }' % json.dumps( geoms_json )
  return 0

def main():
  d = 'Print List Geojsons with cut from mold({ "isOk": 1, "geojsons": "geojsons"}).'
  parser = argparse.ArgumentParser(description=d )
  d = "List of Geojsons"
  parser.add_argument('geojsons', metavar='geojsons', type=str, help=d )
  d = "Geojson(mold)"
  parser.add_argument('geojson_mold', metavar='geojson_mold', type=str, help=d )

  args = parser.parse_args()
  return run( args.geojsons, args.geojson_mold )

if __name__ == "__main__":
    sys.exit( main() )
