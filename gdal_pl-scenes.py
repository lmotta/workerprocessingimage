#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os, struct, datetime

from osgeo import ( gdal, osr, ogr )
from gdalconst import GA_ReadOnly
gdal.UseExceptions()
gdal.PushErrorHandler('CPLQuietErrorHandler')

class WorkerPLScene(object):
  isKilled = False
  api_key = None
  driverMem = gdal.GetDriverByName('MEM')
  driverTif = gdal.GetDriverByName('GTiff')
  gdal_sctruct_types = {
    gdal.GDT_Byte: 'B',
    gdal.GDT_UInt16: 'H',
    gdal.GDT_Int16: 'h',
    gdal.GDT_UInt32: 'I',
    gdal.GDT_Int32: 'i',
    gdal.GDT_Float32: 'f',
    gdal.GDT_Float64: 'd'
  }

  def __init__(self, idWorker):
    super(WorkerPLScene, self).__init__()
    self.idWorker = idWorker
    self.scene, self.ds, self.metadata = None, None, None
    self.algorithms = {
      'mask': { 'datatype': gdal.GDT_Byte,    'numBands': 1, 'func': self._mask },
      'normalize_difference': { 'datatype': gdal.GDT_Float64, 'numBands': 1, 'func': self._norm_dif },
    }
  
  def __del__(self):
    self._clear()

  def _clear(self):
    self.ds = None
    if not self.metadata is None:
      self.metadata.clear()

  def _processBandOut(self, ds, bands, func):
    def setValuesImage(row):
      for i in xrange( len(bands) ):
        d = ( xoff, row, xsize, ysize, xsize, ysize, bands_img[ i ].DataType )
        line = bands_img[ i ].ReadRaster( *d )
        fs = self.gdal_sctruct_types[ bands_img[ i ].DataType ] * xsize * ysize
        values_img[ i ] = list( struct.unpack( fs, line) )
        del line

    bands_img  = [ self.ds.GetRasterBand( bands[ i ] ) for i in xrange( len(bands) ) ]
    values_img = [ None for i in xrange( len(bands) ) ]
    value_out  = [ None for i in xrange( self.metadata['x'] ) ]
    band_out = ds.GetRasterBand(1)
    xoff, xsize, ysize = 0, self.metadata['x'], 1
    format_struct = self.gdal_sctruct_types[ band_out.DataType ] * xsize * ysize
    for row in xrange( self.metadata['y'] ):
      setValuesImage( row )
      for i in xrange( self.metadata['x'] ):
        value_out[ i ] = func( values_img, i )
      line = struct.pack( format_struct, *value_out )
      band_out.WriteRaster( xoff, row, xsize, ysize, line )
      del line
      if self.isKilled:
        break
    #Clear
    del values_img[:]
    del value_out
    for i in xrange( len(bands) ):
      bands_img[ i ].FlushCache()
      bands_img[ i ] = None
    band_out.FlushCache()
    band_out = None
    ds = None
    
  def _mask(self, ds, bands):
    def func(values, i):
      return 255 if values[0][i] > 0 else 0
    self. _processBandOut( ds, [ self.metadata['numBands'] ], func )
  
  def _norm_dif(self, ds, bands):
    def func(values, i):
      vdiff = float( values[0][i] - values[1][i] )
      vsum  = float( values[0][i] + values[1][i] )
      return 0.0 if vsum == 0.0 else vdiff / vsum
    self. _processBandOut( ds, bands, func )

  def setImage(self, image):
    if self.api_key is None:
      return { 'isOk': False, 'msg': "Not found API KEY" }

    self._clear()
    self.scene = image['SCENE']
    opts = [
      ( 'VERSION', 'V0' ),
      ( 'API_KEY', self.api_key ),
      ( 'SCENE', self.scene ),
      ( 'PRODUCT_TYPE', image['PRODUCT_TYPE'] )
    ]
    open_opts = map( lambda x: "%s=%s" % ( x[0], x[1] ), opts )
    msg = None
    try:
      self.ds = gdal.OpenEx( 'PLScenes:', gdal.OF_RASTER, open_options=open_opts )
    except RuntimeError:
      msg = gdal.GetLastErrorMsg()
    if not msg is None:
      return { 'isOk': False, 'msg': msg }
    
    self.metadata = {
        'transform':self.ds.GetGeoTransform(), # resX = coefs[1] resY = -1 * coefs[5] 
        'x': self.ds.RasterXSize, 'y': self.ds.RasterYSize,
        'numBands': self.ds.RasterCount,
        'srs': self.ds.GetProjection()
    }
    return { 'isOk': True }

  def run(self, algorithm):
    def createDSOut():
      numBands = self.algorithms[ nameAlgorithm ]['numBands']
      datatype = self.algorithms[ nameAlgorithm ]['datatype']
      d = ( filenameOut, self.metadata['x'], self.metadata['y'], numBands, datatype )
      ds = None
      try:
        ds = self.driverTif.Create( *d )
      except RuntimeError:
        return None
      ds.SetProjection( self.metadata['srs'] )
      ds.SetGeoTransform( self.metadata['transform'] )
      return ds

    def removeOut():
      if os.path.exists( filenameOut ):
        os.remove( filenameOut )
      aux = "%s.aux.xml" % filenameOut
      if os.path.exists( aux ):
        os.remove( aux )
      
    nameAlgorithm = algorithm['name']
    if not nameAlgorithm in self.algorithms.keys():
      return { 'isOk': False, 'msg': "Not found algorithm '%s'" % algorithm }
    if self.scene is None:
      return { 'isOk': False, 'msg': "Need set image for running" }
    
    filenameOut = "%s_%s_%d.tif" % ( self.scene, nameAlgorithm, self.idWorker )
    removeOut()
    ds = createDSOut()
    if ds is None:
      msg = "Error creating output image from '%s'" % self.scene
      return { 'isOk': False, 'msg': msg }
    
    self.algorithms[ nameAlgorithm ]['func']( ds, algorithm['bands'] )

    return { 'isOk': True, 'filename': filenameOut }

def main():
  def setWorkerPLScene():
    WorkerPLScene.isKilled = False
    WorkerPLScene.api_key = "d42ef5b420514ffd8f5c63655ec63739"
    image = { 'SCENE': '20160421_110213_0c53', 'PRODUCT_TYPE': "analytic" }
    idWorker = 1
    return ( WorkerPLScene( idWorker ), image )
  
  def printTime(title):
    t = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print "%-70s - %s" % ( title, t)

  def runAlgorithm(algorithm):
    printTime( "Running algorithm '%s'" % algorithm['name'] ) 
    vreturn = worker.run( algorithm )
    if not vreturn['isOk']:
      print "Error: %s" % vreturn['msg']
    else:
      printTime( "Create image '%s'" % vreturn['filename'] )

  ( worker, image ) = setWorkerPLScene()
  printTime( "Setting Dataset '%s'" % image['SCENE'] )
  vreturn = worker.setImage( image )
  if not vreturn['isOk']:
    print "Error: %s" % vreturn['msg']
    return
  algorithm = { 'name': 'mask', 'bands': None }  # Use last band
  runAlgorithm( algorithm )
  algorithm = { 'name': 'normalize_difference', 'bands': [ 1, 2 ] }
  runAlgorithm( algorithm )

main()