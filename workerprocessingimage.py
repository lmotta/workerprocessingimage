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
  def __init__(self, p ):
    self.ds, self.numberBands = p['ds'], p['numberBands']
    self.xb = xrange( len( self.numberBands ) )
    self.bands = [ self.ds.GetRasterBand( self.numberBands[ b ] ) for b in self.xb ]    
    datatype = self.bands[0].DataType
    # bandRead: nXOff, nYOff, nXSize, nYSize, nBufXSize, nBufYSize, eBufType
    self.dataRead = [ 0, None, p['xsize'], 1, p['xsize'], 1, datatype ] # None replace with 'row'
    self.idRow = 1
    self.fs = gdal_sctruct_types[ datatype ] * p['xsize']
    self.splitValues = None
    numBands = len( self.xb )
    if numBands > 1:
      self._getValues = self._getValuesBands
      #self._getValues = self.getValues_ORIGIN
      #return
      self.dataRead += [ self.numberBands ]
      self.fs *= numBands
      self.ds = self.bands[0].GetDataset()
      self.xsplit = xrange( 0, p['xsize'] * numBands, p['xsize'] )
      self.splitValues = lambda l: [ l[ i : i + p['xsize'] ] for i in self.xsplit ]
    else:
      self._getValues = self._getValuesBand

  def __del__(self):
    for b in self.xb:
      self.bands[ b ].FlushCache()
      self.bands[ b ] = None

  def getValues_ORIGIN(self, row):
    def getValuesImage(b):
      data = self.bands[ b ].ReadRaster( *self.dataRead )
      values = list( struct.unpack( self.fs, data ) )
      del data
      return values

    self.dataRead[ self.idRow ] = row
    return map( getValuesImage, self.xb )

  def _getValuesBand(self, row):
    self.dataRead[ self.idRow ] = row
    data = self.bands[ 0 ].ReadRaster( *self.dataRead )
    values = list( struct.unpack( self.fs, data ) ) 
    del data
    return  [ values ]

  def _getValuesBands(self, row):
    self.dataRead[ self.idRow ] = row
    data = self.ds.ReadRaster( *self.dataRead )
    values = list( struct.unpack( self.fs, data ) )
    del data
    lst_values = self.splitValues( values )
    del values[:]
    return lst_values
  
  def getValues(self, row):
    return self._getValues( row )

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

  def _processBandOut(self, ds, bands, algorithm):
    xb = xrange( len( bands ) )
    xx = xrange( self.metadata['x'] )
    value_out  = [ None for x in xx ]
    params = { 'ds': self.ds, 'numberBands': bands, 'xsize': self.metadata['x'] }
    wvi = WorkerValuesImage( params )
    band_out = ds.GetRasterBand(1)
    fs = gdal_sctruct_types[ band_out.DataType ] * self.metadata['x']
    for row in xrange( self.metadata['y'] ):
      values_img = wvi.getValues( row )
      for x in xx:
        value_out[ x ] = algorithm( values_img, x )
      del values_img[:]
      line = struct.pack( fs, *value_out )
      band_out.WriteRaster( 0, row, self.metadata['x'], 1, line )
      del line
      if self.isKilled:
        break
    del value_out
    del wvi
    band_out.FlushCache()
    band_out = None
    
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
    ds = None

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
