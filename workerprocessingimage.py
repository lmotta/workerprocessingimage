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

class WorkerPoolValuesImage():
  def __init__(self, bands, paramsRead):
    self.bands = bands
    self.p = paramsRead

  def setRow(self, row):
    self.row = row

  def getValues(self, id):
    band = self.bands[ id ]
    xsize, ysize = self.p['xsize'], self.p['ysize']
    d = ( self.p['xoff'], self.row, xsize, ysize, xsize, ysize, band.DataType )
    line = band.ReadRaster( *d )
    fs = gdal_sctruct_types[ band.DataType ] * xsize * ysize
    values = list( struct.unpack( fs, line) )
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
      wpvi.setRow( row )
      idBands = range( len( bands_img ) )
      values_img = map( wpvi.getValues, idBands )
      del idBands[:]
      return values_img

    bands_img  = [ self.ds.GetRasterBand( bands[ i ] ) for i in xrange( len( bands ) ) ]
    value_out  = [ None for i in xrange( self.metadata['x'] ) ]
    band_out = ds.GetRasterBand(1)
    xoff, xsize, ysize = 0, self.metadata['x'], 1
    format_struct = gdal_sctruct_types[ band_out.DataType ] * xsize * ysize
    wpvi = WorkerPoolValuesImage( bands_img, { 'xoff': xoff, 'xsize': xsize, 'ysize': ysize } )
    for row in xrange( self.metadata['y'] ):
      values_img = getValuesImage( row )
      for i in xrange( self.metadata['x'] ):
        value_out[ i ] = func( values_img, i )
      del values_img[:]
      line = struct.pack( format_struct, *value_out )
      band_out.WriteRaster( xoff, row, xsize, ysize, line )
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
