import uuid, time, requests, hashlib, platform, os
import datetime
import urllib.parse

import zipfile
from shutil import copyfile

import xmltodict

from typing import List, Dict

from ..utils.utils import get_challenge, get_epoch_time, get_system_hostname, hash_file, calculate_checksum, generate_meta_file_contents

class DDAN:

    def __init__(self, api_key: str, analyzer_ip, protocol_version:str = "1.5", verify_cert:bool = False, cert_path:str = False):
        """
        DDAN used to create an interface for all rest calls offered by DDAN appliance and DTAS.

        :param api_key: ddan api key found under help menu
        :param analyzer_ip: IP of DDAN APPLIANCE
        :param protocol_veriosn: current version is 1.5
        :param verify_cert: path to cert file
        :param cert_path: optional CA certificates to trust for certificate verification
        """

        self.uuid = str(uuid.uuid4())
        self.api_key = api_key
        self.analyzer_ip = analyzer_ip
        self.protocol_version = protocol_version
        self.use_checksum_calculating_order = True
        self.product_name = "TDA"
        self.client_hostname = get_system_hostname()
        self.source_id = "1"  # source_id of 1 == User submission
        self.source_name = "ddpyclient"
        self.verify_cert = verify_cert

        if not verify_cert:
            requests.packages.urllib3.disable_warnings()
        else:
            self.verify_cert = cert_path

        self._register()

    def test_connection(self):
        """
        Issue a request to make sure that all settings are correct and the connection to Analyzer's API is good.

        :return: http response code
        """

        url = "https://{}/web_service/sample_upload/test_connection".format(self.analyzer_ip)
        headers = {"X-DTAS-ChecksumCalculatingOrder": "X-DTAS-ProtocolVersion,X-DTAS-Time,X-DTAS-Challenge"}
        r = requests.get(url, verify=False, headers=self._build_headers(headers))
        return r

    def get_black_lists(self, last_query_id:str = "0"):
        '''Issue a request to retrieve all blacklist information'''
        if not ((type(last_query_id) == str) and (last_query_id.isdigit())):
            raise ValueError("get_blacklists parameter 'last_query_id' must be a STRING with a value that's greater than '0'")

        url = "https://{}/web_service/sample_upload/get_black_lists".format(self.analyzer_ip)
        print(url)
        headers = {
            "X-DTAS-ClientUUID": self.uuid,
            "X-DTAS-LastQueryID": str(last_query_id),
            "X-DTAS-ChecksumCalculatingOrder": "X-DTAS-ProtocolVersion,X-DTAS-ClientUUID,X-DTAS-LastQueryID," \
                                               "X-DTAS-Time,X-DTAS-Challenge"
        }

        r = requests.get(url, verify=self.verify_cert, headers=self._build_headers(headers))
        return r

    def _register(self):
        '''Send a registration request to register or update registration information on Analyzer.'''
        url = "https://{}/web_service/sample_upload/register".format(self.analyzer_ip)

        headers = {
            "X-DTAS-ProductName": self.product_name,
            "X-DTAS-ClientHostname": self.client_hostname,
            "X-DTAS-ClientUUID": self.uuid,
            "X-DTAS-SourceID": self.source_id,
            "X-DTAS-SourceName": self.source_name,
            "X-DTAS-ChecksumCalculatingOrder": "X-DTAS-ProtocolVersion,X-DTAS-ProductName,X-DTAS-ClientHostname," \
                                               "X-DTAS-ClientUUID,X-DTAS-SourceID,X-DTAS-SourceName,X-DTAS-Time," \
                                               "X-DTAS-Challenge",
        }

        r = requests.get(url, verify=self.verify_cert, headers=self._build_headers(headers))
        return r


    def submit_file(self, path_to_file:str):
        """
        Upload a file to Analyzer for analysis
        :param path_to_file:

        :return: http response code
        """

        try:
            url = 'https://{}/web_service/sample_upload/simple_upload_sample'.format(self.analyzer_ip)

            headers = {
                "X-DTAS-ClientUUID": self.uuid,
                "X-DTAS-SourceID": self.source_id,
                "X-DTAS-SourceName": self.source_name,
                "X-DTAS-SHA1": hash_file(path_to_file),
                "X-DTAS-SampleType": "0",  # 0 for file, 1 for URL
                "X-DTAS-ChecksumCalculatingOrder": "X-DTAS-ProtocolVersion,X-DTAS-ClientUUID,X-DTAS-SourceID,X-DTAS-SourceName,"\
                                                   "X-DTAS-SHA1,X-DTAS-Time,X-DTAS-SampleType,X-DTAS-Challenge",
            }

            files = {'uploadsample': open(path_to_file, 'rb')}
            r = requests.post(url, verify=self.verify_cert, headers=self._build_headers(headers), files=files)
            return r
        except Exception as ex:
            print(ex)

    def upload_sample(self, path_to_file:str, archive_password: str = '1234'):

        try:

            now = datetime.datetime.now()
            now.strftime("%Y%m%d-%H%M%S")
            path, filename = os.path.split(path_to_file)
            file_hash = hash_file(path_to_file)
            archive_name = 'Archive.zip'
            url = 'https://{}/web_service/sample_upload/upload_sample'.format(self.analyzer_ip)
            meta_string = generate_meta_file_contents(filename, file_hash, archive_password, self.uuid, self.source_id)
            meta_file_name = "{}.meta".format(file_hash)
            meta_file = open(meta_file_name, 'w')
            meta_file.write(meta_string)
            meta_file.close()

            log_file_name = ("{}.log".format(file_hash))
            log_file = open(log_file_name, 'w')
            date_enc = urllib.parse.quote(now.strftime("%m/%d/%Y %H:%M:%S")).replace("/", "%2f")
            log_file.write("Date=%s" % date_enc)
            log_file.close()

            copyfile(path_to_file, filename)

            os.rename(filename, "{}.dat".format(file_hash))

            with zipfile.ZipFile(archive_name, 'w') as myzip:
                myzip.write(meta_file_name)
                myzip.write(log_file_name)
                myzip.write("{}.dat".format(file_hash))

            header_archive_name = ("{}_{}.zip").format(now.strftime("%Y%m%d-%H%M%S"), hash_file(archive_name))

            headers = {
                "X-DTAS-ClientUUID": self.uuid,
                "X-DTAS-SourceID": self.source_id,
                "X-DTAS-SourceName": self.source_name,
                "X-DTAS-Archive-SHA1": hash_file(archive_name),
                "X-DTAS-Archive-Filename": header_archive_name,
                "X-DTAS-ChecksumCalculatingOrder": "X-DTAS-ProtocolVersion,X-DTAS-ClientUUID,X-DTAS-SourceID,X-DTAS-SourceName,"\
                                                   "X-DTAS-Archive-SHA1,X-DTAS-Archive-Filename,X-DTAS-Time,X-DTAS-Challenge",
            }


            file_obj = {'Archive.zip': open('Archive.zip', 'rb')}
            final_headers = self._build_headers(headers)
            print(final_headers)


            with open(archive_name, 'rb') as fh:
                mydata = fh.read()
                r = requests.put(url, verify=self.verify_cert, headers=final_headers, files=file_obj)
                print("R: ", r)
            return r
        except Exception as ex:
            print(ex)

    def get_report(self, sha1val):
        """
        Upload a file data to Analyzer for analysis
        :param sha1val:

        :return: report dict
        """

        try:
            url = 'https://{}/web_service/sample_upload/get_report'.format(self.analyzer_ip)

            headers = {
                "X-DTAS-ClientUUID": self.uuid,
                "X-DTAS-SHA1": sha1val,
                "X-DTAS-ReportType": '0', # 0 for Single Image (default), 1 for Multiple Images. If the sample was analyzed by multiple image types, choose the report having the highest ROZ rating. If the ROZ ratings are all the same, choose the report having the lowest image type ID. (optional)
                "X-DTAS-ChecksumCalculatingOrder": "X-DTAS-ProtocolVersion,X-DTAS-ClientUUID,"\
                                                   "X-DTAS-SHA1,X-DTAS-ReportType,X-DTAS-Time,X-DTAS-Challenge",
            }
            
            r = requests.get(url, verify=self.verify_cert, headers=self._build_headers(headers),)
            
            report = xmltodict.parse(r.text, attr_prefix='', dict_constructor=dict)
            
            return report
        except Exception as ex:
            print(ex)
            return {}

    def _build_headers(self, call_headers):
        """
        Internal class method to contruct call headers and calculate X-DTAS checksum

        :param call_headers: headers specific to call
        :return: entire headers dict including added headers needed for all calls.
        """

        headers = {
            "X-DTAS-ProtocolVersion": self.protocol_version,
            "X-DTAS-Time": get_epoch_time(),
            "X-DTAS-Challenge": get_challenge(),
        }

        headers.update(call_headers)
        headers["X-DTAS-Checksum"] = self._calculate_checksum(headers)
        return headers

    def _calculate_checksum(self, headers, body=""):
        """Calculate the header checksum used for authentication."""

        x_dtas_checksumcalculatingorder = ' '
        # TODO: Extend method to handle use_checksum_calculating_order property == False
        if self.use_checksum_calculating_order == True:
            x_dtas_checksumcalculatingorder_list = headers['X-DTAS-ChecksumCalculatingOrder'].split(",")
            x_dtas_checksumcalculatingorder = ""
            for i in x_dtas_checksumcalculatingorder_list:
                x_dtas_checksumcalculatingorder += headers[i]
        else:
            for key, value in headers.items():
                x_dtas_checksumcalculatingorder += value


        x_dtas_checksum = hashlib.sha1((self.api_key + x_dtas_checksumcalculatingorder).encode('utf-8')).hexdigest()
        return x_dtas_checksum

