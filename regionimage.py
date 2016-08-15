#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
/***************************************************************************
Name                 : Region image
Description          : Get region image  from WKT
Arguments            : Georeferencing Image and WKT for geometry

                       -------------------
begin                : 2016-08-11
copyright            : (C) 2016 by Luiz Motta
email                : motta dot luiz at gmail.com

 ***************************************************************************/
"""

import os, sys, argparse, math

from osgeo import gdal, ogr, osr
from gdalconst import GA_ReadOnly
gdal.UseExceptions()
gdal.PushErrorHandler('CPLQuietErrorHandler')
gdal_sctruct_types = {
  gdal.GDT_Byte: 'B',
  gdal.GDT_UInt16: 'H',
  gdal.GDT_Int16: 'h',
  gdal.GDT_UInt32: 'I',
  gdal.GDT_Int32: 'i',
  gdal.GDT_Float32: 'f',
  gdal.GDT_Float64: 'd'
}

class RegionImage():
  def __init__(self, ds):
    self.ds = ds
    self.ulImage, self.resImage = None, None
  
  def _getGeom(self):
    def getWktBBox( UL, BR):
      coords = [ ( UL['x'], UL['y'] ), ( BR['x'], UL['y'] ), ( BR['x'], BR['y'] ), ( UL['x'], BR['y'] ), ( UL['x'], UL['y'] ) ]
      coords = map( lambda c: "%f %f" % ( c[0], c[1] ), coords)
      return "POLYGON (( %s ))" % ','.join( coords )

    transform = self.ds.GetGeoTransform()
    self.ulImage  = { 'x': transform[0], 'y': transform[3] }
    self.resImage = { 'x': transform[1], 'y': transform[5] }
    xsize, ysize = self.ds.RasterXSize, self.ds.RasterYSize
    BR = { 'x': self.ulImage['x'] + transform[1] * xsize, 'y': self.ulImage['y'] + transform[5] * ysize }
    wktGeom = getWktBBox( self.ulImage, BR )
    
    wktSRS = self.ds.GetProjectionRef()
    if wktSRS == '':
      return { 'isOk': False, 'msg': "Image not have Spatial Reference" }

    sr = osr.SpatialReference()
    sr.ImportFromWkt( wktSRS )
    geom = ogr.CreateGeometryFromWkt( wktGeom )
    geom.AssignSpatialReference( sr )
    
    return { 'isOk': True, 'geom': geom }

  def getRegion(self, wkt4326):
    def getGeomWkt4326():
      geom = ogr.CreateGeometryFromWkt( wkt4326 )
      sr = osr.SpatialReference()
      sr.ImportFromEPSG( 4326 )
      geom.AssignSpatialReference( sr )
      geom.TransformTo( geomImg.GetSpatialReference() )
      
      return geom

    def getPixelCoordinate(x, y):
      self.ulImage, self.resImage
      xCell = ( x - self.ulImage['x'] ) / self.resImage['x'] 
      yCell = ( y - self.ulImage['y'] ) / self.resImage['y']
      
      return { 'x': int( math.ceil( xCell ) ), 'y': int( math.ceil( yCell ) ) }

    vreturn = self._getGeom()
    if not vreturn['isOk']:
      print msg
      return
    geomImg = vreturn['geom']
    geom = getGeomWkt4326()
    msg = "Wkt Geom not intersect with image:\nWkt '%s'\nImage = '%s'" % ( wkt4326, self.ds.GetDescription() )
    if not geomImg.Intersect( geom ):
      geomImg.Destroy()
      geom.Destroy()
      return { 'isOk': False, 'msg': msg }
    geomRegion = geomImg.Intersection( geom )
    geomImg.Destroy()
    geom.Destroy()
    if not geomRegion.GetDimension() == 2:
      geomRegion.Destroy()
      return { 'isOk': False, 'msg': msg }

    ( minX, maxX, minY, maxY )= geomRegion.GetEnvelope()
    geomRegion.Destroy()
    
    ul = getPixelCoordinate( minX, maxY )
    br = getPixelCoordinate( maxX, minY )
    
    return { 'isOk': True, 'ul': ul, 'br': br }

  @staticmethod
  def isValidGeom(wkt4326):
    try:
      geom = ogr.CreateGeometryFromWkt( wkt4326 )
    except RuntimeError:
      pass # The exception not enter here, but, not show GDAL message!
    if geom is None:
      return False
    geom.Destroy()
    return True

def run(filename, wkt4326):
  ds = gdal.Open( filename, GA_ReadOnly )
  ri = RegionImage( ds )
  vreturn = ri.getRegion( wkt4326 )
  if not vreturn['isOk']:
    print vreturn['msg']
    return
  
  x_UL, y_UL = vreturn['ul']['x'], vreturn['ul']['y']
  x_BR, y_BR = vreturn['br']['x'], vreturn['br']['y'] 
  
  print "%d,%d,%d,%d" % ( x_UL, y_UL, x_BR, y_BR )

  ds = None

def main():
  parser = argparse.ArgumentParser(description='Get UL and RB of region image.')
  parser.add_argument('filename', metavar='filename', type=str, help='Name of image')
  parser.add_argument('wkt4326', metavar='wkt4326', type=str, help='WKT, between double quotes, for region(EPSG 4326)')

  args = parser.parse_args()
  if not os.path.exists( args.filename ):
    print "Not found '%s'" % args.filename
    return 1
  
  if not RegionImage.isValidGeom( args.wkt4326 ): 
    print "The WKT '%s' not valid." % args.wkt4326
    return 1
  
  return run( args.filename, args.wkt4326 )


if __name__ == "__main__":
    sys.exit( main() )