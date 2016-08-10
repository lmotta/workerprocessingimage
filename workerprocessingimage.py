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
    band = p['ds'].GetRasterBand( p['bandNumbers'][0] )
    datatype = band.DataType
    
    # p['bandBlockSize'] ['x'],['y'], ['xy']
    
    # Read Band = nXOff, nYOff, nXSize, nYSize, nBufXSize, nBufYSize, eBufType
    self.dataRead = [
      p['xoff'],  p['yoff'], p['xsize'], p['ysize'],
      p['xsize'], p['ysize'], datatype
    ]
    self.fs = gdal_sctruct_types[ datatype ] * p['xysize'] # Read Band
    self.isSrcBand, self.src = False, None
    bandTotal = len( p['bandNumbers'] )
    if bandTotal > 1:
      self.src = p['ds']
      self.dataRead += [  p['bandNumbers'] ]
      self.fs *= bandTotal
      band = None
    else:
      self.src = band
      self.isSrcBand = True

  def getValues(self):
    data = self.src.ReadRaster( *self.dataRead )
    if self.isSrcBand:
      self.src = None
    values = list( struct.unpack( self.fs, data ) )
    del data
    return values

class WorkerProcessingImage(object):
  isKilled = False
  driverMem = gdal.GetDriverByName('MEM')
  driverTif = gdal.GetDriverByName('GTiff')
  algorithms_description = {
    'mask': {
      'description': "Calculate the mask, 255 for pixels > 0",
      'arguments': "Number of one band",
      'bandsTotal': 1
    },
    'norm-diff': {
      'description': "Calculate normalize difference",
      'arguments': "Numbers of two bands",
      'bandsTotal': 2
    }
  }

  def __init__(self, idWorker):
    super(WorkerProcessingImage, self).__init__()
    self.idWorker = idWorker
    self.nameImage, self.ds, self.metadata = None, None, None
    self.bandNumbers, self.bandBlockSize = None, None
    self.algorithms = self.algorithms_description.copy()
    self.algorithms['mask'].update( {
        'datatype': gdal.GDT_Byte,
        'func': self._algMask
    } )
    self.algorithms['norm-diff'].update( {
        'datatype': gdal.GDT_Float32,
        'func': self._algNormDiff
    } )
  
  def __del__(self):
    self._clear()

  def _clear(self):
    self.ds = None
    if not self.metadata is None:
      self.metadata.clear()

  def _processBandOut(self, outDS, algorithm):
    p = {
      'ds': self.ds, 'bandNumbers': self.bandNumbers, 'bandBlockSize': self.bandBlockSize,
      'xsize':  self.metadata['xsize'], 'xoff': self.metadata['xoff'],
      'ysize':  self.metadata['ysize'], 'yoff': self.metadata['yoff'],
      'xysize': self.metadata['xysize']
    }
    wvi = WorkerValuesImage( p )
    imgValues = wvi.getValues()
    del wvi
    outValues = p['xysize'] * [ None ]
    xx = xrange( p['xsize'] )
    for y in xrange( p['ysize'] ):
      if self.isKilled:
        break
      for x in xx:
        outValues[ y * p['xsize'] + x ] = algorithm( imgValues, y, x )
    del imgValues[:]
    outBand = outDS.GetRasterBand(1)
    fs = gdal_sctruct_types[ outBand.DataType ] * p['xysize']
    data = struct.pack( fs, *outValues )
    del outValues[:]
    outBand.WriteRaster( 0, 0, outDS.RasterXSize, outDS.RasterYSize, data )
    del data
    outBand.FlushCache()
    outBand = None

  def _setMetadata(self, subset):
    xoff, xsize, yoff, ysize = 0, self.ds.RasterXSize, 0, self.ds.RasterYSize
    transform = self.ds.GetGeoTransform()
    haveSubset = False 
    if not subset is None:
      xoff,  yoff  = subset['x1'], subset['y1']
      xsize, ysize = subset['x2'] - subset['x1'] + 1, subset['y2'] - subset['y1'] + 1
      lt = list( transform )
      lt[0] += xoff * transform[1]
      lt[3] += yoff * transform[5]
      transform = tuple( lt )
      haveSubset = True
    self.metadata = {
        'transform': transform,
        'srs': self.ds.GetProjection(),
        'xsize': xsize, 'xoff': xoff, 'ysize': ysize, 'yoff': yoff,
        'xysize': xsize * ysize, 'subset': haveSubset,
        'totalbands': self.ds.RasterCount
    }

  def _algMask(self, ds):
    def alg(values, y, x):
      # id2d = y * self.metadata['xsize'] + x
      # id3d = ( bandIndex * self.metadata['xysize'] ) + id2d
      # bandIndex = 0 -> id3d = id2d
      #
      # self.bandBlockSize['x'], self.bandBlockSize['y'], self.bandBlockSize['xy']
      #
      band1 = y * self.metadata['xsize'] + x
      return 255 if values[ band1 ] > 0 else 0
    self. _processBandOut( ds, alg )
  
  def _algNormDiff(self, ds):
    def alg(values, y, x):
      # id2d = y * self.metadata['xsize'] + x
      # id3d = ( bandIndex * self.metadata['xysize'] ) + id2d
      # bandIndex = 0 -> id3d = id2d
      # bandIndex = 1 -> id3d = self.metadata['xysize'] + id2d
      #
      # self.bandBlockSize['x'], self.bandBlockSize['y'], self.bandBlockSize['xy']
      #
      band1 = y * self.metadata['xsize'] + x
      band2 = self.metadata['xysize'] + band1

      vdiff = float( values[ band1 ] - values[ band2 ] )
      vsum  = float( values[ band1 ] + values[ band2 ] )
      return 0.0 if vsum == 0.0 else vdiff / vsum
    self. _processBandOut( ds, alg )

  #def setImage(self, image, subset):
    # self._clear()
    # TODO, self.ds = ...
    # self._setMetadata( subset )
    # return { 'isOk': True }

  def run(self, algorithm):
    def getNameOut():
      subset = "_subset" if self.metadata ['subset'] else ""
      bands = "-".join( map( lambda i: "B%d" % i, self.bandNumbers ) )
      d = ( self.nameImage, subset, algorithm['name'], bands, self.idWorker )
      return "%s%s_%s_%s_work%d.tif" % d
   
    def createDSOut():
      def removeOut():
        if os.path.exists( filenameOut ):
          os.remove( filenameOut )
        aux = "%s.aux.xml" % filenameOut
        if os.path.exists( aux ):
          os.remove( aux )
     
      removeOut()
      bandsTotal = self.algorithms[ algorithm['name'] ]['bandsTotal']
      datatype = self.algorithms[ algorithm['name'] ]['datatype']
      d = ( filenameOut, self.metadata['xsize'], self.metadata['ysize'], bandsTotal, datatype )
      ds = None
      try:
        ds = self.driverTif.Create( *d )
      except RuntimeError:
        return None
      ds.SetProjection( self.metadata['srs'] )
      ds.SetGeoTransform( self.metadata['transform'] )
      return ds
  
    for i in xrange( len( algorithm['bandNumbers'] ) ):
      bn = algorithm['bandNumbers'][ i ]
      if bn > self.metadata['totalbands']:
        msg = "Band '%d' is greater than total of bands '%d'" % ( bn, self.metadata['totalbands'] )
        return { 'isOk': False, 'msg': msg }
    self.bandNumbers = algorithm['bandNumbers']

    filenameOut = getNameOut()
    ds = createDSOut()
    if ds is None:
      msg = "Error creating output image from '%s'" % self.nameImage
      return { 'isOk': False, 'msg': msg }

    bandBlockSizes = map( lambda b: ds.GetRasterBand( b ).GetBlockSize(), self.bandNumbers )
    totalbands = len( bandBlockSizes )
    if totalbands > 1:
      sumX, sumY = 0, 0
      for i in xrange( len( bandBlockSizes ) ):
        sumX += bandBlockSizes[ i ][0]
        sumY += bandBlockSizes[ i ][1]
      if not sumX  == totalbands * bandBlockSizes[0][0] or not sumY  == totalbands * bandBlockSizes[0][1]:
        msg = ",".join( map( lambda b: str(b), self.bandNumbers ) )
        msg = "Bands '%s' of image '%s' have different block sizes" % ( msg, self.nameImage )
        return { 'isOk': False, 'msg': msg }
    self.bandBlockSize = {
      'x':  bandBlockSizes[0][0],
      'y':  bandBlockSizes[0][1],
      'xy': bandBlockSizes[0][0] * bandBlockSizes[0][1]
    }
    
    self.algorithms[ algorithm['name'] ]['func']( ds )

    ds = None
    return { 'isOk': True, 'filename': filenameOut }

class WorkerLocalImage(WorkerProcessingImage):
  def __init__(self, idWorker):
    super(WorkerLocalImage, self).__init__( idWorker )
    
  def setImage(self, image, subset):
    def checkSubset():
      def checkOutX():
        size = self.ds.RasterXSize
        for i in ( 1, 2 ):
          s = subset[ "x%d" % i ]
          if s > size:
            msg = "Coordinate X%d '%d' is greater then number of columns '%d'" % ( i, s, size)
            return { 'isOk': False, 'msg': msg }
        return { 'isOk': True }
      def checkOutY():
        size = self.ds.RasterYSize
        for i in ( 1, 2 ):
          s = subset[ "y%d" % i ]
          if s > size:
            msg = "Coordinate Y%d '%d' is greater then number of lines '%d'" % ( i, s, size)
            return { 'isOk': False, 'msg': msg}
        return { 'isOk': True }
      
      vreturn = checkOutX()
      if not vreturn['isOk']:
        return vreturn
      return checkOutY()

    self._clear()
    self.nameImage = os.path.splitext(os.path.basename( image['name'] ) )[0]
    msg = None
    try:
      self.ds = gdal.Open( image['name'], GA_ReadOnly )
    except RuntimeError:
      msg = gdal.GetLastErrorMsg()
    if not msg is None:
      return { 'isOk': False, 'msg': msg }
    
    if not subset is None:
      vreturn = checkSubset()
      if not vreturn['isOk']:
        return vreturn

    self._setMetadata( subset )
    return { 'isOk': True }

class WorkerPLScene(WorkerProcessingImage):
  PL_API_KEY = os.environ.get('PL_API_KEY')
  
  def __init__(self, idWorker):
    super(WorkerPLScene, self).__init__( idWorker )
    
  def setImage(self, image,subset):
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
    
    self._setMetadata( subset )
    return { 'isOk': True }
