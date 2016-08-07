# -*- coding: utf-8 -*-

import os, struct

from osgeo import gdal
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

class WorkerAlgorithmValues():
  def __init__(self, p):
    def getBands_Total():
      f_grb = self.ds.GetRasterBand 
      bands = p['numBands']
      total = len( p['numBands'] )
      return ( [ f_grb( bands[ i ] ) for i in xrange( total ) ], total )
      
    self.ds, self.alg = p['ds'], p['algorithm']
    self.bands, self.totalBands = getBands_Total()
    datatype = self.bands[-1].DataType
    # dRead = nXOff, nYOff, nXSize, nYSize, nBufXSize, nBufYSize, eBufType
    self.dRead = [
      0, None, # Replace with row in in 'getValue'
      p['xsize'], 1, p['xsize'], 1, datatype
    ]
    # fs = gdal_sctruct_type * xsize * ysize
    self.fs = gdal_sctruct_types[ datatype ] * p['xsize']
    self.idr, self.idx, self.idy = 1, 2, 3
    self._getValues = None
    self.args = [ None for i in xrange( self.totalBands ) ]
    self.valuesAlg = [ None for i in xrange( self.dRead[ self.idx ]  ) ]

  def __del__(self):
    for i in xrange( self.totalBands ):
      self.bands[ i ].FlushCache()
      self.bands[ i ] = None
    del self.args[:]
    del self.valuesAlg[:]

  def setValuesAlg(self, row):
    self.dRead[ self.idr ] = row
    valuesBands = [ None for c in xrange( self.totalBands  ) ]
    for b in xrange( self.totalBands ):
      data = self.bands[ b ].ReadRaster( *self.dRead )
      valuesBands[ b ] = list( struct.unpack( self.fs, data) )
      del data
    for x in xrange( self.dRead[ self.idx ] ):
      for b in xrange( self.totalBands ):
        self.args[ b ] = valuesBands[ b ][ x ]
      self.valuesAlg[ x ] = self.alg( *self.args )
    for b in xrange( self.totalBands ):
      del valuesBands[ b ][:]

class WorkerProcessingImage(object):
  isKilled = False
  driverMem = gdal.GetDriverByName('MEM')
  driverTif = gdal.GetDriverByName('GTiff')

  def __init__(self, idWorker):
    super(WorkerProcessingImage, self).__init__()
    self.idWorker = idWorker
    self.nameImage, self.ds, self.metadata = None, None, None
    self.algorithms = {
      'mask': {
        'datatype': gdal.GDT_Byte,
        'numBands': 1,
        'func': self._algMask
      },
      'normalize_difference': {
        'datatype': gdal.GDT_Float32,
        'numBands': 1,
        'func': self._algNormDiff
      },
    }
  
  def __del__(self):
    self._clear()

  def _clear(self):
    self.ds = None
    if not self.metadata is None:
      self.metadata.clear()

  def _processBandOut(self, ds, numBands, algorithm):
    params = {
      'ds': self.ds, 'numBands': numBands, 'algorithm': algorithm,
      'xsize': self.metadata['x']
    }
    wav = WorkerAlgorithmValues( params )
    band_out = ds.GetRasterBand(1)
    # format_struct = gdal_sctruct_type * xsize * ysize
    format_struct = gdal_sctruct_types[ band_out.DataType ] * params['xsize']
    for row in xrange( self.metadata['y'] ):
      wav.setValuesAlg( row )
      data = struct.pack( format_struct, *wav.valuesAlg )
      band_out.WriteRaster( 0, row, params['xsize'], 1, data )
      del data
      if self.isKilled:
        break
    band_out.FlushCache()
    band_out = None
    ds = None
    
  def _algMask(self, ds, bands):
    def alg(value):
      return 255 if value > 0 else 0
    self. _processBandOut( ds, [ self.metadata['numBands'] ], alg )
  
  def _algNormDiff(self, ds, bands):
    def alg(b1, b2):
      vdiff = float( b1 - b2 )
      vsum  = float( b1 + b2 )
      return 0.0 if vsum == 0.0 else vdiff / vsum
    self. _processBandOut( ds, bands, alg )

  def _setMetadata(self):
    self.metadata = {
        'transform':self.ds.GetGeoTransform(), # resX = coefs[1] resY = -1 * coefs[5] 
        'x': self.ds.RasterXSize, 'y': self.ds.RasterYSize,
        'numBands': self.ds.RasterCount,
        'srs': self.ds.GetProjection()
    }
    
  #def setImage(self, image):
    # self._clear()
    # todo
    # self._setMetadata()
    # return { 'isOk': True }

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
    if self.nameImage is None:
      return { 'isOk': False, 'msg': "Need set image for running" }
    
    filenameOut = "%s_%s_%d.tif" % ( self.nameImage, nameAlgorithm, self.idWorker )
    removeOut()
    ds = createDSOut()
    if ds is None:
      msg = "Error creating output image from '%s'" % self.nameImage
      return { 'isOk': False, 'msg': msg }
    
    self.algorithms[ nameAlgorithm ]['func']( ds, algorithm['bands'] )

    return { 'isOk': True, 'filename': filenameOut }
