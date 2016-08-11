# -*- coding: utf-8 -*-

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

def getBlocksSizeValid(off, blockSize, bandSize):
  valid = blockSize
  if ( off + 1 ) * blockSize > bandSize:
    valid = bandSize - off * blockSize

name = "/home/lmotta/data/plscene_gdal/test/20160421_110213_0c53.tif"
ds = gdal.Open( name, GA_ReadOnly )
band = ds.GetRasterBand( 1 )

sizeImageBlock = lambda b: ( [ b.XSize, b.YSize ], b.GetBlockSize() )
( xBandSize, yBandSize ), ( xBlockSize, yBlockSize ) = sizeImageBlock( band )
xNumBlocks = ( xBandSize + xBlockSize - 1 ) / xBlockSize
yNumBlocks = ( yBandSize + yBlockSize - 1 ) / yBlockSize

fs = gdal_sctruct_types[ band.DataType ] * xNumBlocks * yNumBlocks
xx = xrange( xNumBlocks )

for yOff in xrange( yNumBlocks  ):
  for xOff in xx:
    dataRead = band.ReadBlock( xOff, yOff )
    values = list( struct.unpack( fs, dataRead) )
    del dataRead

    yBlocksSizeValid = getBlocksSizeValid( yOff, yBlockSize, yBandSize )
    xBlocksSizeValid = getBlocksSizeValid( xOff, xBlockSize, xBandSize )
    for yOffValid in xrange( yBlocksSizeValid ):
      for xOffValid in xrange( xBlocksSizeValid ):
        newValue = values[ xOffValid + yOffValid * xBlockSize ]
    del newValue

band = None
ds = None