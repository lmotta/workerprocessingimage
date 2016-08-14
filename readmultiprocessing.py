#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
/***************************************************************************
Name                 : difference geom
Description          : Calculate the difference of shapes
Arguments            : Shapefiles

                       -------------------
begin                : 2015-04-08
copyright            : (C) 2015 by Luiz Motta
email                : motta dot luiz at gmail.com

 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""

import os, sys, multiprocessing, argparse, struct 

from osgeo import gdal
from gdalconst import GA_ReadOnly
gdal_sctruct_types = {
  gdal.GDT_Byte: 'B',
  gdal.GDT_UInt16: 'H',
  gdal.GDT_Int16: 'h',
  gdal.GDT_UInt32: 'I',
  gdal.GDT_Int32: 'i',
  gdal.GDT_Float32: 'f',
  gdal.GDT_Float64: 'd'
}

# WORKER
# Use by pool.apply_async
def getValuesReadRowsBand(data):
  ( idBand, row ) = data
  band = WorkerReadRowBand.bands[ idBand ]
  size = []
  size.extend( WorkerReadRowBand.size )
  size[1] = WorkerReadRowBand.yoff + row
  data = band.ReadRaster( *size )
  return [ idBand, list( struct.unpack( WorkerReadRowBand.fs, data ) ) ]

class WorkerReadRowBand():
  bands = None
  yoff = None
  size = None
  fs = None
  maxRowRead = None

  def __init__(self, ds, bandNumbers):
    WorkerReadRowBand.bands = map( lambda nb: ds.GetRasterBand( nb ), bandNumbers )
  
  def __del__(self):
    for b in xrange( len( self.bands ) ):
      self.bands[ b ] = None
  
  def setData(self, d):
    if len ( set( map( lambda b: b.DataType, self.bands ) ) ) > 1:
      msg = "Dataset have different type of bands"
      return { 'isOk': False, 'msg': msg }
    if len ( set( map( lambda b: ( b.XSize, b.YSize ), self.bands ) ) ) > 1:
      msg = "Dataset have different sizes of bands"
      return { 'isOk': False, 'msg': msg }
    sumSize = d['xsize'] + d['xoff']
    if sumSize > self.bands[0].XSize:
      data = ( d['xsize'], d['xoff'], sumSize, self.bands[0].XSize )
      msg = "XSize '%d' + Xoffset '%d' (%d) is greater than X size of Bands" % data 
      return { 'isOk': False, 'msg': msg }
    
    WorkerReadRowBand.yoff = d['yoff']
    datatype = self.bands[0].DataType
    WorkerReadRowBand.size = [ d['xoff'],  None, d['xsize'], 1, d['xsize'], 1, datatype ]
    WorkerReadRowBand.fs = gdal_sctruct_types[ datatype ] * d['xsize']
    WorkerReadRowBand.maxRowRead = self.bands[0].YSize - d['yoff']

    return { 'isOk': True }
    
  @staticmethod
  def getBandRows(values):
    return map( lambda v: v[1], sorted( values, key=lambda v: v[0] ) )  

def run(filename):
  def algNormDiff( values, x ):
    band1 = values[ 0 ]
    band2 = values[ 1 ]
    vdiff = float( band1[ x ] - band2[ x ] )
    vsum  = float( band1[ x ] + band2[ x ] )
    return 0.0 if vsum == 0.0 else vdiff / vsum

  ds = gdal.Open( filename, GA_ReadOnly )
  bandNumbers = [1,2]
  worker = WorkerReadRowBand( ds, bandNumbers )
  xsize = 50
  vreturn = worker.setData( { 'xoff': 0, 'yoff': 0, 'xsize': xsize } )
  if not vreturn['isOk']:
    print vreturn['msg']
    return
  
  totalRow = 5
  if totalRow > worker.maxRowRead:
    print "Total read rows '%d' is greather than maximum for reading '%d'" % ( totalRow, worker.maxRowRead )
    return

  xb = xrange( len( bandNumbers ) )
  xx = xrange( xsize)
  outValues = xsize * [ None ]
  values = []
  for r in xrange( totalRow ):
    pool = multiprocessing.Pool()
    for b in xb:
      pool.apply_async( getValuesReadRowsBand, args=( ( b, r),), callback=values.append )
    pool.close()
    pool.join()
    pool = None
    for x in xx:
      outValues[ x ] = algNormDiff( WorkerReadRowBand.getBandRows( values ) , x )
    del values[:]

  del outValues[:]
  ds = None
  del worker

def main():
  parser = argparse.ArgumentParser(description='Read image.')
  parser.add_argument('filename', metavar='filename', type=str, help='Name of image')

  args = parser.parse_args()
  if not os.path.exists( args.filename ):
    print "Not found '%s'" % args.filename
    return 1
  
  return run( args.filename )


if __name__ == "__main__":
    sys.exit( main() )