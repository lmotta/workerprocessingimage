# -*- coding: utf-8 -*-

import os, struct

from osgeo import gdal
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

class WorkerValuesImage():
  def __init__(self, bands, xsize):
    self.bands = bands
    datatype = self.bands[0].DataType
    # bandRead: nXOff, nYOff, nXSize, nYSize, nBufXSize, nBufYSize, eBufType
    self.bandRead = [ 0, None, xsize, 1, xsize, 1, datatype ] # None replace with 'row'
    self.fs = gdal_sctruct_types[ datatype ] * xsize

  def setRow(self, row):
    self.bandRead[1] = row

  def getValues(self, id):
    band = self.bands[ id ]
    line = band.ReadRaster( *self.bandRead )
    values = list( struct.unpack( self.fs, line) )
    del line
    return values

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

  def _processBandOut(self, ds, bands, func):
    def getValuesImage(row):
      wvi.setRow( row )
      idBands = range( len( bands_img ) )
      values_img = map( wvi.getValues, idBands )
      del idBands[:]
      return values_img

    bands_img  = [ self.ds.GetRasterBand( bands[ i ] ) for i in xrange( len( bands ) ) ]
    value_out  = [ None for i in xrange( self.metadata['x'] ) ]
    band_out = ds.GetRasterBand(1)
    fs = gdal_sctruct_types[ band_out.DataType ] * self.metadata['x']
    wvi = WorkerValuesImage( bands_img, self.metadata['x'] )
    for row in xrange( self.metadata['y'] ):
      values_img = getValuesImage( row )
      for i in xrange( self.metadata['x'] ):
        value_out[ i ] = func( values_img, i )
      del values_img[:]
      line = struct.pack( fs, *value_out )
      band_out.WriteRaster( 0, row, self.metadata['x'], 1, line )
      del line
      if self.isKilled:
        break
    del value_out
    for i in xrange( len(bands) ):
      bands_img[ i ].FlushCache()
      bands_img[ i ] = None
    band_out.FlushCache()
    band_out = None
    ds = None
    
  def _algMask(self, ds, bands):
    def func(values, i):
      return 255 if values[0][i] > 0 else 0
    self. _processBandOut( ds, [ self.metadata['numBands'] ], func )
  
  def _algNormDiff(self, ds, bands):
    def func(values, i):
      vdiff = float( values[0][i] - values[1][i] )
      vsum  = float( values[0][i] + values[1][i] )
      return 0.0 if vsum == 0.0 else vdiff / vsum
    self. _processBandOut( ds, bands, func )

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

class WorkerLocalImage(WorkerProcessingImage):
  def __init__(self, idWorker):
    super(WorkerLocalImage, self).__init__( idWorker )
    
  def setImage(self, image):
    self._clear()
    self.nameImage = os.path.splitext(os.path.basename( image['name'] ) )[0]
    msg = None
    try:
      self.ds = gdal.Open( image['name'], GA_ReadOnly )
    except RuntimeError:
      msg = gdal.GetLastErrorMsg()
    if not msg is None:
      return { 'isOk': False, 'msg': msg }
    
    self._setMetadata()
    return { 'isOk': True }

class WorkerPLScene(WorkerProcessingImage):
  PL_API_KEY = os.environ.get('PL_API_KEY')
  
  def __init__(self, idWorker):
    super(WorkerPLScene, self).__init__( idWorker )
    
  def setImage(self, image):
    if self.PL_API_KEY is None:
      msg = "API KEY for Planet Labs is not defined in host"
      return { 'isOk': False, 'msg': msg }

    self._clear()
    self.nameImage = image['name']
    opts = [
      ( 'VERSION', 'V0' ),
      ( 'API_KEY', self.PL_API_KEY ),
      ( 'SCENE', self.nameImage ),
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
    
    self._setMetadata()
    return { 'isOk': True }
