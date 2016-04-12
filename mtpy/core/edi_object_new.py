# -*- coding: utf-8 -*-
"""
Created on Tue Dec 22 16:03:31 2015

@author: jpeacock
"""

import os
import numpy as np
import datetime

import mtpy.utils.format as MTft
import mtpy.utils.calculator as MTcc
import mtpy.utils.exceptions as MTex
import mtpy.utils.filehandling as MTfh
import mtpy.core.z as MTz

tab = ' '*4

class Edi(object):
    """
    This class is for .edi files, mainly reading and writing.  Has been tested
    on Winglink and Phoenix output .edi's, which are meant to follow the 
    archaic EDI format put forward by SEG. Can read impedance, Tipper and/or
    spectra data.  
    
    The Edi class contains a class for each major section of the .edi file.
    
    Arguments
    ---------------
        
        **edi_fn** : string
                     full path to .edi file to be read in. 
                     *default* is None. If an .edi file is input, it is 
                     automatically read in and attributes of Edi are filled
       
    
    Methods
    ---------------
    ===================== =====================================================
    Methods               Description  
    ===================== =====================================================
    read_edi_file         Reads in an edi file and populates the associated
                          classes and attributes. 
    write_edi_file        Writes an .edi file following the EDI format given
                          the apporpriate attributes are filled.  Writes out
                          in impedance and Tipper format.
    _read_data            Reads in the impedance and Tipper blocks, if the 
                          .edi file is in 'spectra' format, read_data converts
                          the data to impedance and Tipper.
    _read_mt              Reads impedance and tipper data from the appropriate
                          blocks of the .edi file.
    _read_spectra         Reads in spectra data and converts it to impedance 
                          and Tipper data.                     
    ===================== =====================================================
    
    Attributes
    ---------------
        
    ===================== ========================================== ==========
    Attributes            Description                                default
    ===================== ========================================== ==========    
    Data_sect             DataSection class, contains basin 
                          information on the data collected and in
                          whether the data is in impedance or 
                          spectra.
    Define_measurement    DefineMeasurement class, contains 
                          information on how the data was 
                          collected.
    edi_fn                full path to edi file read in              None
    Header                Header class, contains metadata on 
                          where, when, and who collected the data
    Info                  Information class, contains information 
                          on how the data was processed and how the
                          transfer functions where estimated.
    Tipper                mtpy.core.z.Tipper class, contains the
                          tipper data
    Z                     mtpy.core.z.Z class, contains the
                          impedance data
    _block_len            number of data in one line.                6  
    _data_header_str      header string for each of the data         '!****{0}****!'
                          section   
    _num_format           string format of data.                     ' 15.6e'
    _t_labels             labels for tipper blocks                 
    _z_labels             labels for impedance blocks
    ===================== ========================================== ========== 
    
    Examples
    ---------------------
    :Change Latitude: ::
        
        >>> import mtpy.core.edi as mtedi
        >>> edi_obj = mtedi.Edi(edi_fn=r"/home/mt/mt01.edi")
        >>> # change the latitude
        >>> edi_obj.header.lat = 45.7869
        >>> new_edi_fn = edi_obj.write_edi_file()
    """

    def __init__(self, edi_fn=None):
        
        self.edi_fn = edi_fn
        self.Header = Header()
        self.Info = Information()
        self.Define_measurement = DefineMeasurement()
        self.Data_sect = DataSection()
        self.Z = MTz.Z()
        self.Tipper = MTz.Tipper()
        
        self._z_labels = [['zxxr', 'zxxi', 'zxx.var'],
                          ['zxyr', 'zxyi', 'zxy.var'],
                          ['zyxr', 'zyxi', 'zyx.var'],
                          ['zyyr', 'zyyi', 'zyy.var']]
                         
        self._t_labels = [['txr.exp', 'txi.exp', 'txvar.exp'],
                          ['tyr.exp', 'tyi.exp', 'tyvar.exp']]
                          
        self._data_header_str = '!****{0}****!\n'
                          
        self._num_format = ' 15.6e'
        self._block_len = 6
        
        if self.edi_fn is not None:
            self.read_edi_file()
            
    def read_edi_file(self, edi_fn=None):
        """
        Read in an edi file and fill attributes of each section's classes. 
        Including: 
            * Header
            * Info
            * Define_measurement
            * Data_sect
            * Z
            * Tipper
            
            .. note:: Automatically detects if data is in spectra format.  All
                  data read in is converted to impedance and Tipper.
        
        Arguments
        -------------
        
            **edi_fn** : string
                         full path to .edi file to be read in
                         *default* is None
                         
        
                  
        Examples
        -------------
        
        :Read edi: ::
        
            >>> import mtpy.core.Edi as mtedi
            >>> edi_obj = mtedi.Edi()
            >>> edi_obj.read_edi_file(edi_fn=r"/home/mt/mt01.edi")
                         
        """
        
        if edi_fn is not None:
            self.edi_fn = edi_fn
            
        if self.edi_fn is None:
            raise MTex.MTpyError_EDI("No edi file input, check edi_fn")
            
        if os.path.isfile(self.edi_fn) is False:
            raise MTex.MTpyError_EDI("Could not find {0}, check path".format(self.edi_fn))
        
        
        self.Header = Header(edi_fn=self.edi_fn)
        self.Info = Information(edi_fn=self.edi_fn)
        self.Define_measurement = DefineMeasurement(edi_fn=self.edi_fn)
        self.Data_sect = DataSection(edi_fn=self.edi_fn)
        
        self._read_data()
        
        if self.Header.lat is None:
            self.Header.lat = self.Define_measurement.reflat
            print 'Got latitude from reflat for {0}'.format(self.Header.dataid)
        if self.Header.lon is None:
            self.Header.lon = self.Define_measurement.reflon
            print 'Got longitude from reflon for {0}'.format(self.Header.dataid)
        if self.Header.elev is None:
            self.Header.elev = self.Define_measurement.refelev
            print 'Got elevation from refelev for {0}'.format(self.Header.dataid)
        
        print "Read in edi file for station {0}".format(self.Header.dataid)
        
    def _read_data(self):
        """
        read either impedance or spectra data
        """
        
        if self.edi_fn is None:
            raise MTex.MTpyError_EDI('No edi file input, check edi_fn')
        if os.path.isfile(self.edi_fn) is False:
            raise MTex.MTpyError_EDI('No edi file input, check edi_fn')
            
        with open(self.edi_fn, 'r') as fid:
            lines = fid.readlines()[self.Data_sect.line_num+2:]
        
        if self.Data_sect.data_type == 'spectra':
            self._read_spectra(lines)
        
        elif self.Data_sect.data_type == 'z':
            self._read_mt(lines)
            
    def _read_mt(self, data_lines):
        """
        read in impedance and tipper data if its there
        """
        data_dict = {}
        data_find = False
        for line in data_lines:
            if line.find('>') == 0 and line.find('!') == -1:
                line_list = line[1:].strip().split()
                key = line_list[0].lower()
                if key[0] == 'z' or key[0] == 't' or key == 'freq':
                    data_find = True
                    data_dict[key] = []
                else:
                    data_find = False
                
        
            elif data_find == True and line.find('>') == -1 and line.find('!') == -1:
                d_lines = line.strip().split()
                for ii, dd in enumerate(d_lines):
                    # check for empty values and set them to 0, check for any
                    # other characters sometimes there are ****** for a null
                    # component
                    try:
                        d_lines[ii] = float(dd)
                        if d_lines[ii] == 1.0e32:
                            d_lines[ii] = 0.0
                    except ValueError:
                        d_lines[ii] = 0.0
                data_dict[key] += d_lines
        
        ## fill useful arrays
        freq_arr = np.array(data_dict['freq'], dtype=np.float)
        
        ## fill impedance tensor
        self.Z.freq = freq_arr.copy()
        self.Z.z = np.zeros((self.Data_sect.nfreq, 2, 2), dtype=np.complex)
        self.Z.zerr = np.zeros((self.Data_sect.nfreq, 2, 2), dtype=np.float)
        
        self.Z.z[:, 0, 0] = np.array(data_dict['zxxr'])+\
                             np.array(data_dict['zxxi'])*1j
        self.Z.z[:, 0, 1] = np.array(data_dict['zxyr'])+\
                            np.array(data_dict['zxyi'])*1j
        self.Z.z[:, 1, 0] = np.array(data_dict['zyxr'])+\
                            np.array(data_dict['zyxi'])*1j
        self.Z.z[:, 1, 1] = np.array(data_dict['zyyr'])+\
                            np.array(data_dict['zyyi'])*1j
        
        self.Z.zerr[:, 0, 0] = np.array(data_dict['zxx.var'])
        self.Z.zerr[:, 0, 1] = np.array(data_dict['zxy.var'])
        self.Z.zerr[:, 1, 0] = np.array(data_dict['zyx.var'])
        self.Z.zerr[:, 1, 1] = np.array(data_dict['zyy.var'])

        
        ## fill tipper data if there it exists
        self.Tipper.tipper = np.zeros((self.Data_sect.nfreq, 1, 2), 
                                      dtype=np.complex) 
        self.Tipper.tippererr = np.zeros((self.Data_sect.nfreq, 1, 2),
                                         dtype=np.float) 
        self.Tipper.freq = freq_arr.copy()

        if 'txr.exp' in data_dict.keys():
            self.Tipper.tipper[:, 0, 0] = np.array(data_dict['txr.exp'])+\
                                            np.array(data_dict['txi.exp'])*1j
            self.Tipper.tipper[:, 0, 1] = np.array(data_dict['tyr.exp'])+\
                                            np.array(data_dict['tyi.exp'])*1j
            
            self.Tipper.tippererr[:, 0, 0] = np.array(data_dict['txvar.exp'])    
            self.Tipper.tippererr[:, 0, 1] = np.array(data_dict['tyvar.exp'])
              
        else:
            print 'Could not find any Tipper data.'
            
    def _read_spectra(self, data_lines):
        """
        read in spectra data
        """
        
        data_dict = {}
        
    def write_edi_file(self, new_edi_fn=None):
        """
        Write a new edi file from either an existing .edi file or from data
        input by the user into the attributes of Edi.
        
        Arguments
        -----------
        
            **new_edi_fn** : string
                             full path to new edi file.
                             *default* is None, which will write to the same
                             file as the input .edi with as:
                             r"/home/mt/mt01_1.edi"
                             
        Examples
        -----------
        
        :Write EDI file: ::
            
            >>> import mtpy.core.edi as mtedi
            >>> edi_obj = mtedi.Edi(edi_fn=r"/home/mt/mt01/edi")
            >>> edi_obj.Header.dataid = 'mt01_rr'
            >>> edi_obj.write_edi_file() 
        """
        
        if new_edi_fn is None:
            if self.edi_fn is not None:
                new_edi_fn = self.edi_fn
            else:
                new_edi_fn = os.path.join(os.getcwd(), 
                                          '{0}.edi'.format(self.Header.dataid))
        new_edi_fn = MTfh.make_unique_filename(new_edi_fn)
            
        if self.Header.dataid is None:
            self.read_edi_file()
            
        # write lines
        header_lines = self.Header.write_header()
        info_lines = self.Info.write_info()
        define_lines = self.Define_measurement.write_define_measurement()
        dsect_lines = self.Data_sect.write_data_sect()
        
        # write out frequencies
        freq_lines = [self._data_header_str.format('frequencies'.upper())]
        freq_lines += self._write_data_block(self.Z.freq, 'freq')
        
        # write out rotation angles
        zrot_lines = [self._data_header_str.format('impedance rotation angles'.upper())]
        zrot_lines += self._write_data_block(self.Z.rotation_angle, 'zrot')
        
        # write out data only impedance and tipper
        z_data_lines = [self._data_header_str.format('impedances'.upper())]
        for ii in range(2):
            for jj in range(2):
                z_lines_real = self._write_data_block(self.Z.z[:, ii, jj].real, 
                                                      self._z_labels[2*ii+jj][0])
                z_lines_imag = self._write_data_block(self.Z.z[:, ii, jj].imag, 
                                                      self._z_labels[2*ii+jj][1])
                z_lines_var = self._write_data_block(self.Z.zerr[:, ii, jj], 
                                                     self._z_labels[2*ii+jj][2])
                                           
                z_data_lines += z_lines_real
                z_data_lines += z_lines_imag
                z_data_lines += z_lines_var
                
        # write out rotation angles
        trot_lines = [self._data_header_str.format('tipper rotation angles'.upper())]
        if type(self.Tipper.rotation_angle) is float:
            trot = np.repeat(self.Tipper.rotation_angle, self.Tipper.freq.size)
        else:
            trot = self.Tipper.rotation_angle
        trot_lines += self._write_data_block(trot, 'trot')
                
        # write out tipper lines       
        t_data_lines = [self._data_header_str.format('tipper'.upper())]        
        for jj in range(2):
            t_lines_real = self._write_data_block(self.Tipper.tipper[:, 0, jj].real, 
                                                  self._t_labels[jj][0])
            t_lines_imag = self._write_data_block(self.Tipper.tipper[:, 0, jj].imag, 
                                                  self._t_labels[jj][1])
            t_lines_var = self._write_data_block(self.Tipper.tippererr[:, 0, jj], 
                                                 self._t_labels[jj][2])
                                       
            t_data_lines += t_lines_real
            t_data_lines += t_lines_imag
            t_data_lines += t_lines_var
            
        edi_lines = header_lines+\
                    info_lines+\
                    define_lines+\
                    dsect_lines+\
                    freq_lines+\
                    zrot_lines+\
                    z_data_lines+\
                    trot_lines+\
                    t_data_lines+['>END']
                    
        with open(new_edi_fn, 'w') as fid:
            fid.write(''.join(edi_lines))

        print 'Wrote {0}'.format(new_edi_fn)            
        return new_edi_fn
        
    def _write_data_block(self, data_comp_arr, data_key):
        """
        write a data block 
        
        return a list of strings
        """
        if data_key.lower().find('z') >= 0 and \
            data_key.lower() not in ['zrot', 'trot']:
            block_lines = ['>{0} ROT=ZROT // {1:.0f}\n'.format(data_key.upper(), 
                          data_comp_arr.size)]        
        elif data_key.lower().find('t') >= 0 and \
            data_key.lower() not in ['zrot', 'trot']:
            block_lines = ['>{0} ROT=TROT // {1:.0f}\n'.format(data_key.upper(), 
                          data_comp_arr.size)]
        elif data_key.lower() == 'freq':
            block_lines = ['>{0} // {1:.0f}\n'.format(data_key.upper(), 
                          data_comp_arr.size)]
                          
        elif data_key.lower() in ['zrot', 'trot']:
             block_lines = ['>{0} // {1:.0f}\n'.format(data_key.upper(), 
                          data_comp_arr.size)]
                          
        else:
            raise MTex.MTpyError_EDI('Cannot write block for {0}'.format(data_key))
        
        for d_index, d_comp in enumerate(data_comp_arr, 1):
            if d_comp == 0.0 and data_key.lower() not in ['zrot', 'trot']:
                d_comp = float(self.Header.empty)
            # write the string in the specified format    
            num_str = '{0:{1}}'.format(d_comp, self._num_format)
            
            # check to see if a new line is needed
            if d_index%self._block_len == 0:
                num_str += '\n'
            # at the end of the block add a return
            if d_index == data_comp_arr.size:
                num_str += '\n'
    
            block_lines.append(num_str)
            
        return block_lines
    
    #----------------------------------------------------------------------- 
    # set a few important properties  
    # --> Latitude    
    def _get_lat(self):
         """ 
         get latitude
         """
         
         return self.Header.lat
                        
    def _set_lat(self, input_lat):
        """
        set latitude and make sure it is converted to a float
        """
        
        self.Header.lat = MTft._assert_position_format('lat', input_lat)
        print 'Converted input latitude to decimal degrees: {0: .6f}'.format(
                                                               self.Header.lat)
        
    lat = property(fget=_get_lat, fset=_set_lat, 
                   doc='Latitude in decimal degrees')
    
    # --> Longitude               
    def _get_lon(self):
         return self.Header.lon
                        
    def _set_lon(self, input_lon):
        self.Header.lon = MTft._assert_position_format('lon', input_lon)
        print 'Converted input longitude to decimal degrees: {0: .6f}'.format(
                                                               self.Header.lon)
        
    lon = property(fget=_get_lon, fset=_set_lon, 
                   doc='Longitude in decimal degrees')
                   
    # --> Elevation               
    def _get_elev(self):
         return self.Header.elev
                        
    def _set_elev(self, input_elev):
        self.Header.elev = MTft._assert_position_format('elev', input_elev)
        
    elev = property(fget=_get_elev, fset=_set_elev, 
                   doc='Elevation in meters')
                   
    # --> station
    def _get_station(self):
        return self.Header.dataid
        
    def _set_station(self, new_station):
        if type(new_station) is not str:
            new_station = '{0}'.format(new_station)
        self.Header.dataid = new_station
        self.Data_sect.sectid = new_station
    
    station = property(fget=_get_station, fset=_set_station, 
                       doc="station name")
#==============================================================================
#  Header object        
#==============================================================================
class Header(object):
    """
    Header class contains all the information in the header section of the .edi
    file. A typical header block looks like::
        
        >HEAD

            ACQBY=None
            ACQDATE=None
            DATAID=par28ew
            ELEV=0.000
            EMPTY=1e+32
            FILEBY=WG3DForward
            FILEDATE=2016/04/11 19:37:37 UTC
            LAT=-30:12:49
            LOC=None
            LON=139:47:50
            PROGDATE=2002-04-22
            PROGVERS=WINGLINK EDI 1.0.22
    
    Arguments
    -------------
    
        **edi_fn** : string
                     full path to .edi file to be read in. 
                     *default* is None. If an .edi file is input, it is 
                     automatically read in and attributes of Header are filled
                     
    Attributes
    -------------

    Many of the attributes are needed in the .edi file.  They are marked with
    a yes for 'In .edi'

    ============== ======================================= ======== ===========
    Attributes     Description                             Default  In .edi     
    ============== ======================================= ======== ===========
    acqby          Acquired by                             None     yes
    acqdate        Acquired date (YYYY-MM-DD)              None     yes
    dataid         Station name, should be a string        None     yes
    edi_fn         Full path to .edi file                  None     no
    elev           Elevation of station (m)                None     yes
    empty          Value for missing data                  1e32     yes
    fileby         File written by                         None     yes   
    filedate       Date the file is written (YYYY-MM-DD)   None     yes
    header_list    List of header lines                    None     no 
    lat            Latitude of station [1]_                None     yes
    loc            Location name where station was         None     yes 
                   collected
    lon            Longitude of station [1]_               None     yes
    phoenix_edi    [ True | False ] if phoenix .edi format False    no
    progdate       Date of program version to write .edi   None     yes
    progvers       Version of program writing .edi         None     yes  
    stdvers        Standard version                        None     yes
    units          Units of distance                       m        yes
    _header_keys   list of metadata input into .edi        [2]_ 
                   header block.                                    no
    ============== ======================================= ======== ===========
    
    .. rubric:: footnotes
    .. [1] Internally everything is converted to decimal degrees.  Output is
          written as HH:MM:SS.ss so Winglink can read them in. 
    .. [2] If you want to change what metadata is written into the .edi file
           change the items in _header_keys.  Default attributes are:
               * acqby 
               * acqdate
               * dataid
               * elev
               * fileby
               * lat
               * loc
               * lon
               * filedate
               * empty
               * progdate
               * progvers
          
    Methods
    -------------
    
    ====================== ====================================================
    Methods                Description
    ====================== ====================================================
    get_header_list        get header lines from edi file
    read_header            read in header information from header_lines
    write_header           write header lines, returns a list of lines to write
    ====================== ====================================================
          

    Examples
    --------------    
    
    :Read Header: ::
    
        >>> import mtpy.core.edi as mtedi
        >>> header_obj = mtedi.Header(edi_fn=r"/home/mt/mt01.edi")
        
    """
    
    def __init__(self, edi_fn=None, **kwargs):
        self.edi_fn = edi_fn
        self.dataid = None
        self.acqby = None
        self.fileby = None
        self.acqdate = None
        self.units = None
        self.filedate = datetime.datetime.utcnow().strftime(
                                                    '%Y/%m/%d %H:%M:%S UTC')       
        self.loc = None
        self.lat = None
        self.lon = None
        self.elev = None
        self.empty = 1E32
        self.progvers = None
        self.progdate = None
        self.phoenix_edi = False
        
        self.header_list = None
        
        self._header_keys = ['acqby', 
                             'acqdate',
                             'dataid',
                             'elev',
                             'fileby',
                             'lat',
                             'loc',
                             'lon',
                             'filedate',
                             'empty',
                             'progdate',
                             'progvers']
        
        for key in kwargs.keys():
            setattr(self, key, kwargs[key])
            
        if self.edi_fn is not None:
            self.read_header()
            
    def get_header_list(self):
        """
        Get the header information from the .edi file in the form of a list,
        where each item is a line in the header section.
        """
       
        if self.edi_fn == None:
            print 'No edi file to read'
            return
        if os.path.isfile(self.edi_fn) == False:
            print 'Could not find {0}, check path'.format(self.edi_fn)
            
        self.header_list = []
        head_find = False
        count = 0
        with open(self.edi_fn, 'r') as fid:
            for line in fid:
                if line.find('>') == 0:
                    count += 1
                    if line.lower().find('head') > 0:
                        head_find = True
                    else:
                        head_find = False
                    if count == 2 and head_find == False:
                        break
                elif count == 1 and line.find('>') != 0 and head_find == True:
                    line = line.strip()
                    # skip any blank lines
                    if len(line) > 2:
                        self.header_list.append(line.strip())
                        
        self.header_list = self._validate_header_list(self.header_list)
    
    def read_header(self, header_list=None):
        """
        read a header information from either edi file or a list of lines
        containing header information.
        
        Arguments
        -----------
        
            **header_list** : list
                              should be read from an .edi file or input as
                              ['key_01=value_01', 'key_02=value_02']
                              
        Examples
        ----------
        
        :Input header_list: ::
        
            >>> h_list = ['lat=36.7898', 'lon=120.73532', 'elev=120.0', ...
            >>>           'dataid=mt01']
            >>> import mtpy.core.edi as mtedi
            >>> header = mtedi.Header()
            >>> header.read_header(h_list)
            
        """

        if header_list is not None:
            self.header_list = self._validate_header_list(header_list)
            
        if self.header_list is None and self.edi_fn is None:
            print 'Nothing to read. header_list and edi_fn are None'
            
        if self.header_list is None and self.edi_fn is not None:
            self.get_header_list()
        
        for h_line in self.header_list:
            h_list = h_line.split('=')
            key = h_list[0].lower()
            value = h_list[1].replace('"', '')
            
            if key in 'latitude':
                key = 'lat'
                value = MTft._assert_position_format(key, value)
            
            elif key in 'longitude':
                key = 'lon'
                value = MTft._assert_position_format(key, value)
                
            elif key in 'elevation':
                key = 'elev'
                try:
                    value = float(value)
                except ValueError:
                    value = 0.0
                    print 'No elevation data'
                    
            elif key in ['country', 'state', 'loc', 'location', 'prospect']:
                key = 'loc'
                try:
                    if getattr(self, key) is not None:
                        value = '{0}, {1}'.format(getattr(self, key), value)
                except KeyError:
                    pass
            # test if its a phoenix formated .edi file
            elif key in ['progvers']:
                if value.lower().find('mt-editor') != -1:
                    self.phoenix_edi = True
                    
            elif key in ['fileby']:
                if value == '':
                    value = 'mtpy'
                
            setattr(self, key, value)
            
    def write_header(self, header_list=None):
        """
        Write header information to a list of lines.
        
        Arguments
        -------------
        
            **header_list** : list
                              should be read from an .edi file or input as
                              ['key_01=value_01', 'key_02=value_02']
            
        Returns
        ---------------
            
            **header_lines** : list
                               list of lines containing header information
                               will be of the form
                               ['>HEAD\n',
                                '    key_01=value_01\n']
                                if None is input then reads from input .edi 
                                file or uses attribute information to write
                                metadata.
        """

        if header_list is not None:
            self.read_header(header_list)
            
        if self.header_list is None and self.edi_fn is not None:
            self.get_header_list()
            
        header_lines = ['>HEAD\n\n']
        for key in sorted(self._header_keys):
            value = getattr(self, key)
            if key in ['progdate', 'progvers']:
                if value is None:
                    value = 'mtpy'
            elif key in ['lat', 'lon']:
                value = MTft.convert_dms_tuple2string(
                                        MTft.convert_degrees2dms_tuple(value))
            if key in ['elev']:
                try:
                    value = '{0:.3f}'.format(value)
                except ValueError:
                    value = '0.000'
                    
            if key in ['filedate']:
                value = datetime.datetime.utcnow().strftime(
                                                    '%Y/%m/%d %H:%M:%S UTC')
                                                    
            header_lines.append('{0}{1}={2}\n'.format(tab, key.upper(), value))
        header_lines.append('\n')
        return header_lines
        
    def _validate_header_list(self, header_list):
        """
        make sure the input header list is valid
        
        returns a validated header list
        """
        
        if header_list is None:
            print 'No header information to read'
            return None
            
        new_header_list = []
        for h_line in header_list:
            h_line = h_line.strip().replace('"', '')
            if len(h_line) > 1:
                h_list = h_line.split('=')
                if len(h_list) == 2:
                    key = h_list[0]
                    value = h_list[1]
                    new_header_list.append('{0}={1}'.format(key, value))
        
        return new_header_list
        
#==============================================================================
# Info object
#==============================================================================
class Information(object):
    """
    Contain, read, and write info section of .edi file
    
    not much to really do here, but just keep it in the same format that it is
    read in as, except if it is in phoenix format then split the two paragraphs
    up so they are sequential.
    
    """
    
    def __init__(self, edi_fn=None):
        self.edi_fn = edi_fn
        self.info_list = None
        
        if self.edi_fn is not None:
            self.read_info()
            
    def get_info_list(self):
        """
        get a list of lines from the info section
        """
        
        if self.edi_fn is None:
            print 'no edi file input, check edi_fn attribute'            
            return
        if os.path.isfile(self.edi_fn) is False:
            print 'Could not find {0}, check path'.format(self.edi_fn)
            return
            
        self.info_list = []
        info_find = False
        phoenix_file = False
        phoenix_list_02 = []
        count = 0
        with open(self.edi_fn, 'r') as fid:
            for line in fid:
                if line.find('>') == 0:
                    count += 1
                    if line.lower().find('info') > 0:
                        info_find = True
                    else:
                        info_find = False
                    if count > 2 and info_find == False:
                        break
                elif count > 1 and line.find('>') != 0 and info_find == True:
                    if line.lower().find('run information') >= 0:
                        phoenix_file = True
                    if phoenix_file == True and len(line) > 40:
                        self.info_list.append(line[0:37].strip())
                        phoenix_list_02.append(line[38:].strip())
                    else:
                        if len(line.strip()) > 1:
                            self.info_list.append(line.strip())
                        
        self.info_list += phoenix_list_02
        # validate the information list
        self.info_list = self._validate_info_list(self.info_list)
        
    def read_info(self, info_list=None):
        """
        read information section of the .edi file
        """
        
        if info_list is not None:
            self.info_list = self._validate_info_list(info_list)
            
        if self.edi_fn is not None and self.info_list is None:
            self.get_info_list()
            
        if self.info_list is None:
            print "Could not read information"
            return
            
    def write_info(self, info_list=None):
        """
        
        """
        
        if info_list is not None:
            self.info_list = self._validate_info_list(info_list)
        
            
        info_lines = ['>INFO\n\n']
        for line in self.info_list:
            info_lines.append('{0}{1}\n'.format(tab, line))
        
        return info_lines
            
         
    def _validate_info_list(self, info_list):
        """
        check to make sure the info list input is valid, really just checking
        for Phoenix format where they put two columns in the file and remove 
        any blank lines and the >info line
        """
        
        new_info_list = []
        for line in info_list:
            # get rid of empty lines
            lt = str(line).strip()
            if len(lt) > 1:
                if line.find('>') == 0:
                    pass
                else:
                    new_info_list.append(line.strip())
                    
        return new_info_list
        
            
#==============================================================================
#  Define measurement class       
#==============================================================================
class DefineMeasurement(object):
    """
    DefineMeasurement class holds information about the measurement.  This 
    includes how each channel was setup.  The main block contains information 
    on the reference location for the station.  This is a bit of an archaic 
    part and was meant for a multiple station .edi file.  This section is also
    important if you did any forward modeling with Winglink cause it only gives
    the station location in this section.  The other parts are how each channel
    was collected.  An example define measurement section looks like::
    
        >=DEFINEMEAS
        
            MAXRUN=999
            MAXMEAS=9999
            UNITS=M
            REFTYPE=CART
            REFLOC="par28ew"
            REFLAT=-30:12:49.4693
            REFLONG=139:47:50.87
            REFELEV=0
            
        >HMEAS ID=1001.001 CHTYPE=HX X=0.0 Y=0.0 Z=0.0 AZM=0.0 
        >HMEAS ID=1002.001 CHTYPE=HY X=0.0 Y=0.0 Z=0.0 AZM=90.0 
        >HMEAS ID=1003.001 CHTYPE=HZ X=0.0 Y=0.0 Z=0.0 AZM=0.0 
        >EMEAS ID=1004.001 CHTYPE=EX X=0.0 Y=0.0 Z=0.0 X2=0.0 Y2=0.0 
        >EMEAS ID=1005.001 CHTYPE=EY X=0.0 Y=0.0 Z=0.0 X2=0.0 Y2=0.0 
        >HMEAS ID=1006.001 CHTYPE=HX X=0.0 Y=0.0 Z=0.0 AZM=0.0 
        >HMEAS ID=1007.001 CHTYPE=HY X=0.0 Y=0.0 Z=0.0 AZM=90.0 
    
    Arguments
    -------------
    
        **edi_fn** : string
                     full path to .edi file to read in.
                     
    Attributes
    -------------
    
    ================= ==================================== ======== ===========
    Attributes        Description                          Default  In .edi     
    ================= ==================================== ======== ===========
    edi_fn            Full path to edi file read in        None     no
    maxchan           Maximum number of channels measured  None     yes 
    maxmeas           Maximum number of measurements       9999     yes
    maxrun            Maximum number of measurement runs   999      yes
    meas_####         HMeasurement or EMEasurment object   None     yes
                      defining the measurement made [1]_
    refelev           Reference elevation (m)              None     yes  
    reflat            Reference latitude [2]_              None     yes  
    refloc            Reference location                   None     yes
    reflon            Reference longituted [2]_            None     yes  
    reftype           Reference coordinate system          'cart'   yes
    units             Units of length                      m        yes 
    _define_meas_keys Keys to include in define_measurment [3]_     no
                      section.          
    ================= ==================================== ======== ===========                
    
    .. rubric:: footnotes
    .. [1] Each channel with have its own define measurement and depending on
           whether it is an E or H channel the metadata will be different.  
           the #### correspond to the channel number.
    .. [2] Internally everything is converted to decimal degrees.  Output is
          written as HH:MM:SS.ss so Winglink can read them in. 
    .. [3] If you want to change what metadata is written into the .edi file
           change the items in _header_keys.  Default attributes are:
               * maxchan
               * maxrun
               * maxmeas
               * reflat
               * reflon
               * refelev
               * reftype
               * units

    """
    
    def __init__(self, edi_fn=None):
        self.edi_fn = edi_fn
        self.measurement_list = None
        
        self.maxchan = None
        self.maxmeas = 7
        self.maxrun = 999
        self.refelev = None
        self.reflat = None
        self.reflon = None
        self.reftype = 'cartesian'
        self.units = 'm'
        
        self._define_meas_keys = ['maxchan',
                                  'maxrun',
                                  'maxmeas',
                                  'reflat',
                                  'reflon',
                                  'refelev',
                                  'reftype',
                                  'units']
                                  
        if self.edi_fn is not None:
            self.read_define_measurement()
        
    def get_measurement_lists(self):
        """
        get measurement list including measurement setup
        """
        if self.edi_fn is None:
            print 'No edi file input, check edi_fn attribute'
            return 
            
        if os.path.isfile(self.edi_fn) is False:
            print 'Could not find {0}, check path'.format(self.edi_fn)
            
        self.measurement_list = []
        meas_find = False
        count = 0
        with open(self.edi_fn, 'r') as fid:
            for line in fid:
                if line.find('>=') == 0:
                    count += 1
                    if line.lower().find('definemeas') > 0:
                        meas_find = True
                    else:
                        meas_find = False
                    if count == 2 and meas_find == False:
                        break
                elif count == 1 and line.find('>') != 0 and meas_find == True:
                    line = line.strip()
                    if len(line) > 2:
                        self.measurement_list.append(line.strip())
                
                # look for the >XMEAS parts
                elif count == 1 and line.find('>') == 0 and meas_find == True:
                    if line.find('!') > 0:
                        pass
                    else:
                        line_list = line.strip().split()
                        m_dict = {}
                        for ll in line_list[1:]:
                            ll_list = ll.split('=')
                            key = ll_list[0].lower()
                            value = ll_list[1]
                            m_dict[key] = value
                        self.measurement_list.append(m_dict)
                        
    def read_define_measurement(self, measurement_list=None):
        """
        read the define measurment section of the edi file
        
        should be a list with lines for:
            - maxchan 
            - maxmeas
            - maxrun
            - refelev
            - reflat
            - reflon
            - reftype
            - units
            - dictionaries for >XMEAS with keys:
                - id
                - chtype
                - x
                - y
                - axm
                -acqchn
        
        """
        
        if measurement_list is not None:
            self.measurement_list = measurement_list
            
        if self.measurement_list is None and self.edi_fn is not None:
            self.get_measurement_lists()
            
        if self.measurement_list is None and self.edi_fn is None:
            print 'Nothing to read, check edi_fn or measurement_list attributes'
            return
       
        m_count = 1    
        for line in self.measurement_list:
            if type(line) is str:
                line_list = line.split('=')
                key = line_list[0].lower()
                value = line_list[1]
                if key in 'reflatitude':
                    key = 'reflat'
                    value = MTft._assert_position_format('lat', value)
                elif key in 'reflongitude':
                    key = 'reflon'
                    value = MTft._assert_position_format('lon', value)
                elif key in 'refelevation':
                    key = 'refelev'
                    value = MTft._assert_position_format('elev', value)
                elif key in 'maxchannels':
                    key = 'maxchan'
                    value = int(value)
                elif key in 'maxmeasurements':
                    key = 'maxmeas'
                    value = int(value)
                setattr(self, key, value)
        
            elif type(line) is dict:
                try:
                    key = 'meas_{0:02.0f}'.format(float(line['id']))
                except KeyError:
                    key = 'meas_{0:02}'.format(m_count)
                if line['chtype'].lower().find('h') >= 0:
                    value = HMeasurement(**line)
                elif line['chtype'].lower().find('e') >= 0:
                    value = EMeasurement(**line)
                setattr(self, key, value)
                
    def write_define_measurement(self, measurement_list=None):
        """
        write the define measurement block as a list of strings
        """
        
        if measurement_list is not None:
            self.read_define_measurement(measurement_list=measurement_list)
            
        measurement_lines = ['>=DEFINEMEAS\n\n']
        for key in self._define_meas_keys:
            value = getattr(self, key)
            if key == 'reflat' or key == 'reflon':
                value = MTft.convert_dms_tuple2string(
                                        MTft.convert_degrees2dms_tuple(value))
            elif key == 'refelev':
                value = '{0:.3f}'.format(value)
            
            measurement_lines.append('{0}{1}={2}\n'.format(tab,
                                                           key.upper(),
                                                           value))
        measurement_lines.append('\n')
                                                           
        ## need to write the >XMEAS type
        m_key_list = [kk for kk in self.__dict__.keys() if kk.find('meas_')==0]
        if len(m_key_list) == 0:
            print 'No XMEAS information.'
        else:
            for key in sorted(m_key_list):
                m_obj = getattr(self, key)
                if m_obj.chtype.lower().find('h') >= 0:
                    head = 'hmeas'
                elif m_obj.chtype.lower().find('e') >= 0:
                    head = 'emeas'                
                else:
                    head = None
                
                m_list = ['>{0}'.format(head.upper())]
                for mkey, mfmt in zip(m_obj._kw_list, m_obj._fmt_list):
                    m_list.append(' {0}={1:{2}}'.format(mkey.upper(),
                                                        getattr(m_obj, mkey),
                                                        mfmt))
                m_list.append('\n')
                measurement_lines.append(''.join(m_list))
        
        return measurement_lines
            
#==============================================================================
# magnetic measurements
#==============================================================================
class HMeasurement(object):
    """
    HMeasurement contains metadata for a magnetic field measurement
    
    Attributes
    ------------
    
    ====================== ====================================================
    Attributes             Description
    ====================== ====================================================
    id                     Channel number
    chtype                 [ HX | HY | HZ | RHX | RHY ]
    x                      x (m) north from reference point (station)
    y                      y (m) east from reference point (station)  
    azm                    angle of sensor relative to north = 0
    acqchan                name of the channel acquired usually same as chtype
    ====================== ====================================================
    
    Example
    ------------
    
    :Fill Metadata: ::
    
        >>> import mtpy.core.edi as mtedi
        >>> h_dict = {'id': '1', 'chtype':'hx', 'x':0, 'y':0, 'azm':0}
        >>> h_dict['acqchn'] = 'hx'
        >>> hmeas = mtedi.HMeasurement(**h_dict)
    """
    
    def __init__(self, **kwargs):
        
        self._kw_list = ['id', 'chtype', 'x', 'y', 'azm', 'acqchan']
        self._fmt_list = ['<4.4g','<3', '<4.1f', '<4.1f', '<4.1f', '<4']
        for key in self._kw_list:
            setattr(self, key, None)
        
        for key in kwargs.keys():
            try:
                setattr(self, key, float(kwargs[key]))
            except ValueError:
                setattr(self, key, kwargs[key])

#==============================================================================
# electric measurements            
#==============================================================================
class EMeasurement(object):
    """
    EMeasurement contains metadata for an electric field measurement
    
    Attributes
    ------------
    
    ====================== ====================================================
    Attributes             Description
    ====================== ====================================================
    id                     Channel number
    chtype                 [ EX | EY ]
    x                      x (m) north from reference point (station) of one 
                           electrode of the dipole
    y                      y (m) east from reference point (station) of one 
                           electrode of the dipole
    x2                     x (m) north from reference point (station) of the 
                           other electrode of the dipole
    y2                     y (m) north from reference point (station) of the 
                           other electrode of the dipole
    acqchan                name of the channel acquired usually same as chtype
    ====================== ====================================================
    
    Example
    ------------
    
    :Fill Metadata: ::
    
        >>> import mtpy.core.edi as mtedi
        >>> e_dict = {'id': '1', 'chtype':'ex', 'x':0, 'y':0, 'x2':50, 'y2':50}
        >>> e_dict['acqchn'] = 'ex'
        >>> emeas = mtedi.EMeasurement(**e_dict)
    """
    
    def __init__(self, **kwargs):
        
        self._kw_list = ['id', 'chtype', 'x', 'y', 'x2', 'y2', 'acqchan']
        self._fmt_list = ['<4.4g', '<3', '<4.1f', '<4.1f', '<4.1f', '<4.1f',
                          '<4']
        for key in self._kw_list:
            setattr(self, key, None)
        
        for key in kwargs.keys():
            try:
                setattr(self, key, float(kwargs[key]))
            except ValueError:
                setattr(self, key, kwargs[key])
        
        
#==============================================================================
# data section        
#==============================================================================
class DataSection(object):
    """
    DataSection contains the small metadata block that describes which channel
    is which.  A typical block looks like::
        
        >=MTSECT
        
            ex=1004.001
            ey=1005.001
            hx=1001.001
            hy=1002.001
            hz=1003.001
            nfreq=14
            sectid=par28ew
            nchan=None
            maxblks=None
            
    Arguments
    -------------
        **edi_fn** : string
                     full path to .edi file to read in.
                     
    Attributes
    -------------
    
    ================= ==================================== ======== ===========
    Attributes        Description                          Default  In .edi     
    ================= ==================================== ======== ===========
    ex                ex channel id number                 None     yes  
    ey                ey channel id number                 None     yes
    hx                hx channel id number                 None     yes
    hy                hy channel id number                 None     yes
    hz                hz channel id number                 None     yes
    nfreq             number of frequencies                None     yes
    sectid            section id, should be the same
                      as the station name -> Header.dataid None     yes 
    maxblks           maximum number of data blocks        None     yes
    nchan             number of channels                   None     yes
    _kw_list          list of key words to put in metadata [1]_     no 
    ================= ==================================== ======== ===========
        
    .. rubric:: Footnotes
    .. [1] Changes these values to change what is written to edi file    
    """
    def __init__(self, edi_fn=None):
        self.edi_fn = edi_fn
        
        self.data_type = 'z'
        self.line_num = 0
        self.data_sect_list = None
        
        self._kw_list = ['ex', 
                         'ey',
                         'hx',
                         'hy',
                         'hz',
                         'nfreq',
                         'sectid',
                         'nchan',
                         'maxblks']
                         
        for key in self._kw_list:
            setattr(self, key, None)
            
        if self.edi_fn is not None:
            self.read_data_sect()
        
        
    def get_data_sect(self):
        """
        read in the data of the file, will detect if reading spectra or 
        impedance.
        """
        
        if self.edi_fn is None:
            raise MTex.MTpyError_EDI('No edi file to read. Check edi_fn')
            
        if os.path.isfile(self.edi_fn) is False:
            raise MTex.MTpyError_EDI('Could not find {0}. Check path'.format(self.edi_fn))
        
        self.data_sect_list = []
        data_sect_find = False
        count = 0
        with open(self.edi_fn) as fid:
            for ii, line in enumerate(fid):
                if line.find('>=') == 0:
                    count += 1
                    if line.lower().find('sect') > 0:
                        data_sect_find = True
                        self.line_num = ii
                        if line.lower().find('spect') > 0:
                            self.data_type = 'spectra'
                        elif line.lower().find('mt') > 0:
                            self.data_type = 'z'
                    else:
                        data_sect_find = False
                    if count > 2 and data_sect_find == False:
                        break
                elif count == 2 and line.find('>') != 0 and \
                    data_sect_find == True:
                    if len(line.strip()) > 2:
                        self.data_sect_list.append(line.strip())
                        
    def read_data_sect(self, data_sect_list=None):
        """
        read data section
        """
        
        if data_sect_list is not None:
            self.data_sect_list = data_sect_list
            
        if self.edi_fn is not None and self.data_sect_list is None:
            self.get_data_sect()
            
        for d_line in self.data_sect_list:
            d_list = d_line.split('=')
            if len(d_list) > 1:
                key = d_list[0].lower()
                try:
                    value = int(d_list[1].strip())
                except ValueError:
                    value = d_list[1].strip().replace('"', '')
            
                setattr(self, key, value)
                
    def write_data_sect(self, data_sect_list=None):
        """
        write a data section
        """
        
        if data_sect_list is not None:
            self.read_data_sect(data_sect_list)
            
        if self.data_type == 'spectra':
            data_sect_lines = ['\n>=spectrasect\n'.upper()]
            
        if self.data_type == 'z':
            data_sect_lines = ['\n>=mtsect\n'.upper()]
        for key in self._kw_list:
            data_sect_lines.append('{0}{1}={2}\n'.format(tab, 
                                                         key.upper(), 
                                                         getattr(self, key)))
        
        data_sect_lines.append('\n')
        
        return data_sect_lines
                        
    