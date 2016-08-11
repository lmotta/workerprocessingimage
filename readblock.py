#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
/***************************************************************************
Name                 : Test Read and Write block
Description          : Create new image, add 100 for each pixel
Arguments            : Georeferencing Inage

                       -------------------
begin                : 2016-08-11
copyright            : (C) 2016 by Luiz Motta
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

import os, struct

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

def run(filenameIn):
  def sum100(value):
    return value + 100
  
  def setBlockOutValue(dataRead, xOff, yOff, func):
    def getBlocksSizeValid(off, blockSize, bandSize):
      valid = blockSize
      if ( off + 1 ) * blockSize > bandSize:
        valid = bandSize - off * blockSize
      return valid
  
    values = list( struct.unpack( fsRead, dataRead) )
    yBlocksSizeValid = getBlocksSizeValid( yOff, yBlockSize, yBandSize )
    xBlocksSizeValid = getBlocksSizeValid( xOff, xBlockSize, xBandSize )
    for yOffValid in xrange( yBlocksSizeValid ):
      for xOffValid in xrange( xBlocksSizeValid ):
        i = xOffValid + yOffValid * xBlockSize
        outValues[ i ] = func( values[ i ] )
  
  def getMetadataImages():
    def GetMetadataBandBlock(band):
      f = lambda b: ( [ b.XSize, b.YSize ], band.GetBlockSize() )
      ( xBandSize, yBandSize ), ( xBlockSize, yBlockSize ) = f( band )
      xNumBlocks = ( xBandSize + xBlockSize - 1 ) / xBlockSize
      yNumBlocks = ( yBandSize + yBlockSize - 1 ) / yBlockSize
      
      return {
        'xBandSize':  xBandSize,  'yBandSize':  yBandSize,
        'xBlockSize': xBlockSize, 'yBlockSize': yBlockSize,
        'xNumBlocks': ( xBandSize + xBlockSize - 1 ) / xBlockSize,
        'yNumBlocks': ( yBandSize + yBlockSize - 1 ) / yBlockSize
      }
    
    dsIn = gdal.Open( filenameIn, GA_ReadOnly )
    transform = dsIn.GetGeoTransform()
    srs = dsIn.GetProjection()
    bandIn = dsIn.GetRasterBand( 1 )
    datatype = bandIn.DataType

    name = os.path.splitext( os.path.basename( filenameIn ) )[0]
    filenameOut = "%s_out.tif" % name
    driverTif = gdal.GetDriverByName('GTiff')
    d = ( filenameOut, xsize, xsize, 1, datatype )
    dsOut = driverTif.Create( *d )
    dsOut.SetProjection( srs )
    dsOut.SetGeoTransform( transform )
    bandOut = dsOut.GetRasterBand( 1 )

    metadataIn =  { 'dsIn':  dsIn,  'bandIn':  bandIn  }
    metadataIn.update( GetMetadataBandBlock( bandIn ) )
    metadataOut = { 'dsOut': dsOut, 'bandOut': bandOut }
    metadataOut.update( GetMetadataBandBlock( bandOut ) )
    
    return { 'in': metadataIn, 'out': metadataOut }
    
  sizeImageBlock = lambda b: ( [ b.XSize, b.YSize ], b.GetBlockSize() )
  ( xBandSize, yBandSize ), ( xBlockSize, yBlockSize ) = sizeImageBlock( band )
  xNumBlocks = ( xBandSize + xBlockSize - 1 ) / xBlockSize
  yNumBlocks = ( yBandSize + yBlockSize - 1 ) / yBlockSize
  
  fsRead = gdal_sctruct_types[ datatype ] * xBlockSize * yBlockSize
  xx = xrange( xNumBlocks )
  
  filenameOut = "/home/lmotta/data/plscenes/data/20141007_192530_0812_sub_out.tif"
  outDS = createDSOut()
  outBand = outDS.GetRasterBand( 1 )
  ( xsize, ysize ) = outBand.GetBlockSize()
  fsWrite   = gdal_sctruct_types[ datatype ] * xsize * ysize
  outValues = xsize * ysize * [ 0 ]
  for yOff in xrange( yNumBlocks  ):
    for xOff in xx:
      data = band.ReadBlock( xOff, yOff )
      setBlockOutValue( data, xOff, yOff, sum100)
      del data
      data = struct.pack( fsWrite, *outValues )
      outBand.WriteBlock( xOff, yOff, data )
      del data
  
  del outValues[:]
  band.FlushCache()
  band = None
  ds = None
  outBand.FlushCache()
  outBand = None
  outDS = None

def main():
  def removeFile(filename):
    if os.path.exists( filename ):
      os.remove( filename )
    name = os.path.splitext( os.path.basename( filename ) )[0]    
    aux = "%s.aux.xml" % name
    if os.path.exists( aux ):
      os.remove( aux )

  d = "Image processing (create imagem sum 100 ) - Test with ReadBlock and Write Block."
  parser = argparse.ArgumentParser(description=d )
  d = "Input file name of image"
  parser.add_argument('filenameIn', metavar='filenameIn', type=str, help=d )

  args = parser.parse_args()
  if not os.path.exists( args.filenameIn ):
    print "Missing file '%s'." % args.filenameIn
    return 1
  removeFile( args.filenameIn )
  run( args.filenameIn )

if __name__ == "__main__":
    sys.exit( main() )
