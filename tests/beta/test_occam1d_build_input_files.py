#! /usr/bin/env python
"""
Description:

    This script is to create input files required to run occam1d inversion, which include:

    OccamStartup1D
    Model1D
    Occam1d_DataFile_DET.dat.

    These input files are created from a standard edi data file.
    
References: 
    examples/tests/occam1d_buildinputfiles.py

CreationDate:   31/10/2017
Developer:      fei.zhang@ga.gov.au

Revision History:
    LastUpdate:     31/10/2017   FZ
"""

# import section

import os
import tests.util_functions as ufun
from tests.beta import *

from unittest import TestCase

import mtpy.modeling.occam1d as mtoc1d  # Wrapper class to interact with Occam1D


class TestOccam1D(TestCase):
    def setUp(self):

        # set the dir to the output from the previously correct run
        self._expected_output_dir = os.path.join(SAMPLE_DIR,'Occam1d')

        if not os.path.isdir(self._expected_output_dir):
            self._expected_output_dir = None

        # directory to save created input files
        self._output_dir = os.path.join(TEMP_OUT_DIR, 'Occam1d')
        # ufun.clean_recreate(self._output_dir) # this may remove other test functions' output
        if not os.path.exists(self._output_dir):
            os.mkdir(self._output_dir)

    def _main_func(self, path2edifile):
        """
        test function should be successful with a default path2edifile
        :return:
        """
        edifile_name = os.path.basename(path2edifile)
        tmpdir = edifile_name[:-4]  + "_dir" # remove the trailing .edi
        tmp_save_path = os.path.join(self._output_dir, tmpdir)
        ufun.clean_recreate(tmp_save_path)

        # create data file
        ocd = mtoc1d.Data()  # create an object and assign values to arguments

        ocd.write_data_file(edi_file=path2edifile,
                            mode='det',
                            # mode, can be te, tm, det (for res/phase) or tez, tmz, zdet for real/imag impedance tensor values
                            save_path= tmp_save_path,
                            res_errorfloor=5,  # percent error floor
                            phase_errorfloor=1,  # error floor in degrees
                            z_errorfloor=2.5,
                            remove_outofquadrant=True)

        # create model file
        ocm = mtoc1d.Model(n_layers=100,  # number of layers
                           target_depth=10000,  # target depth in metres, before padding
                           z1_layer=10  # first layer thickness in metres
                           )
        ocm.write_model_file(save_path = tmp_save_path)

        # create startup file
        ocs = mtoc1d.Startup(data_fn=ocd.data_fn,  # basename of data file *default* is Occam1DDataFile
                             model_fn=ocm.model_fn,  # basename for model file *default* is Model1D
                             max_iter=200,  # maximum number of iterations to run
                             target_rms=0.0)

        ocs.write_startup_file()

        return tmp_save_path

    def test_fun1(self):
        """ use the same pb23c.edi to reproduce previous run results"""

        outdir = self._main_func(os.path.join(EDI_DATA_DIR,'pb23c.edi') )

        for afile in ("Model1D", "Occam1d_DataFile_DET.dat", "OccamStartup1D"):

            output_data_file =  os.path.join(outdir, afile)
            self.assertTrue(os.path.isfile(output_data_file), "output data file not found")

            expected_data_file = os.path.join(self._expected_output_dir, afile)

            self.assertTrue(os.path.isfile(expected_data_file),
                            "Ref output data file does not exist, nothing to compare with"
                            )

            print ("Comparing", output_data_file, "and", expected_data_file)

            count = ufun.diffiles(output_data_file, expected_data_file)
            if afile == "OccamStartup1D":
                self.assertTrue(count == 1, "Only-1 different line in for this file %s" % afile)
            else:
                self.assertTrue(count == 0, "The output files different in %s lines" % count)

    def test_fun2(self):
        """ another test edi case: The output files should be different !!!"""

        #outdir = self._main_func(r'E:/Githubz/mtpy/examples/data/edi_files/pb25c.edi')
        outdir = self._main_func(os.path.join(EDI_DATA_DIR,'pb25c.edi') )


        #for afile in ("Model1D", "Occam1d_DataFile_DET.dat", "OccamStartup1D"):
        for afile in [ "Occam1d_DataFile_DET.dat", ]:  # only one file is different, the other 2 files same?

            output_data_file = os.path.join(outdir, afile)
            self.assertTrue(os.path.isfile(output_data_file), "output data file not found")

            expected_data_file = os.path.join(self._expected_output_dir, afile)

            self.assertTrue(os.path.isfile(expected_data_file),
                            "Ref output data file does not exist, nothing to compare with"
                            )

            print ("Comparing", output_data_file, "and", expected_data_file)

            count = ufun.diffiles(output_data_file, expected_data_file)

            self.assertTrue(count > 0, "The output files should be different !!!")


