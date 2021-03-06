import unittest
import tempfile
import shutil
import os
import glob
import logging
import subprocess
import oeqa.utils.ftools as ftools
from oeqa.utils.decorators import testcase 
from oeqa.selftest.base import oeSelfTest
from oeqa.utils.commands import runCmd, bitbake, get_bb_var
from oeqa.utils.httpserver import HTTPService

class oeSDKExtSelfTest(oeSelfTest):
    """
    # Bugzilla Test Plan: 6033
    # This code is planned to be part of the automation for eSDK containig
    # Install libraries and headers, image generation binary feeds, sdk-update.
    """

    @staticmethod
    def get_esdk_environment(env_eSDK, tmpdir_eSDKQA):
        # XXX: at this time use the first env need to investigate
        # what environment load oe-selftest, i586, x86_64
        pattern = os.path.join(tmpdir_eSDKQA, 'environment-setup-*')
        return glob.glob(pattern)[0]
    
    @staticmethod
    def run_esdk_cmd(env_eSDK, tmpdir_eSDKQA, cmd, postconfig=None, **options):
        if postconfig:
            esdk_conf_file = os.path.join(tmpdir_eSDKQA, 'conf', 'local.conf')
            with open(esdk_conf_file, 'a+') as f:
                f.write(postconfig)
        if not options:
            options = {}
        if not 'shell' in options:
            options['shell'] = True

        runCmd("cd %s; . %s; %s" % (tmpdir_eSDKQA, env_eSDK, cmd), **options)

    @staticmethod
    def generate_eSDK(image):
        pn_task = '%s -c populate_sdk_ext' % image
        bitbake(pn_task)

    @staticmethod
    def get_eSDK_toolchain(image):
        pn_task = '%s -c populate_sdk_ext' % image

        sdk_deploy = get_bb_var('SDK_DEPLOY', pn_task)
        toolchain_name = get_bb_var('TOOLCHAINEXT_OUTPUTNAME', pn_task)
        return os.path.join(sdk_deploy, toolchain_name + '.sh')
    
    @staticmethod
    def update_configuration(cls, image, tmpdir_eSDKQA, env_eSDK, ext_sdk_path):
        sstate_dir = os.path.join(os.environ['BUILDDIR'], 'sstate-cache')
        cls.http_service = HTTPService(sstate_dir)
        cls.http_service.start()
        cls.http_url = "http://127.0.0.1:%d" % cls.http_service.port

        oeSDKExtSelfTest.generate_eSDK(cls.image)

        cls.ext_sdk_path = oeSDKExtSelfTest.get_eSDK_toolchain(cls.image)
        runCmd("%s -y -d \"%s\"" % (cls.ext_sdk_path, cls.tmpdir_eSDKQA))

        cls.env_eSDK = oeSDKExtSelfTest.get_esdk_environment('', cls.tmpdir_eSDKQA)

        sstate_config="""
SDK_LOCAL_CONF_WHITELIST = "SSTATE_MIRRORS"
SSTATE_MIRRORS =  "file://.* http://%s/PATH"
CORE_IMAGE_EXTRA_INSTALL = "perl"
        """ % cls.http_url

        with open(os.path.join(cls.tmpdir_eSDKQA, 'conf', 'local.conf'), 'a+') as f:
            f.write(sstate_config)

    @classmethod
    def setUpClass(cls):
        # If there is an exception in setUpClass it will not run tearDownClass
        # method and it leaves HTTP server running forever, so we need to be
        # sure tearDownClass is run.
        try:
            cls.tmpdir_eSDKQA = tempfile.mkdtemp(prefix='eSDKQA')

            # Start to serve sstate dir
            sstate_dir = get_bb_var('SSTATE_DIR')
            cls.http_service = HTTPService(sstate_dir)
            cls.http_url = "http://127.0.0.1:%d" % cls.http_service.port
            cls.http_service.start()

            cls.image = 'core-image-minimal'
            oeSDKExtSelfTest.generate_eSDK(cls.image)

            # Install eSDK
            cls.ext_sdk_path = oeSDKExtSelfTest.get_eSDK_toolchain(cls.image)
            runCmd("%s -y -d \"%s\"" % (cls.ext_sdk_path, cls.tmpdir_eSDKQA))

            cls.env_eSDK = oeSDKExtSelfTest.get_esdk_environment('', cls.tmpdir_eSDKQA)

            # Configure eSDK to use sstate mirror from poky
            sstate_config="""
SDK_LOCAL_CONF_WHITELIST = "SSTATE_MIRRORS"
SSTATE_MIRRORS =  "file://.* http://%s/PATH"
            """ % cls.http_url
            with open(os.path.join(cls.tmpdir_eSDKQA, 'conf', 'local.conf'), 'a+') as f:
                f.write(sstate_config)
        except:
            cls.tearDownClass()
            raise

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmpdir_eSDKQA)
        cls.http_service.stop()

    @testcase (1602)
    def test_install_libraries_headers(self):
        pn_sstate = 'bc'
        bitbake(pn_sstate)
        cmd = "devtool sdk-install %s " % pn_sstate
        oeSDKExtSelfTest.run_esdk_cmd(self.env_eSDK, self.tmpdir_eSDKQA, cmd)
    
    @testcase(1603)
    def test_image_generation_binary_feeds(self):
        image = 'core-image-minimal'
        cmd = "devtool build-image %s" % image
        oeSDKExtSelfTest.run_esdk_cmd(self.env_eSDK, self.tmpdir_eSDKQA, cmd)

    @testcase(1567)
    def test_sdk_update_http(self):
        cmd = "devtool sdk-update %s" % self.http_url
        oeSDKExtSelfTest.update_configuration(self, self.image, self.tmpdir_eSDKQA, self.env_eSDK, self.ext_sdk_path)
        oeSDKExtSelfTest.run_esdk_cmd(self.env_eSDK, self.tmpdir_eSDKQA, cmd)
        self.http_service.stop()

if __name__ == '__main__':
    unittest.main()
