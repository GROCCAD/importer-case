#!/usr/bin/env python
import base64
from itertools import groupby
import json
import os
from pprint import pprint
import sys
from operator import itemgetter

import requests



# Make sure running Python 3
if sys.version_info < (3, 0, 0):
    print('This script assumes Python 3.')
    sys.exit(-1)


BASE_URL = 'https://caseregistry.imsglobal.org/ims/case/v1p0'

CREDENTIALS_PATH = os.environ.get('CASE_CREDENTIALS_PATH', 'credentials/casenetwork.json')
# of the form { "client_id": "<client id>", "client_secret": "<client secret>" }
CLIENTOKEN_ENDPOINT = 'https://oauth2-case.imsglobal.org/oauth2server/clienttoken'
BEARERCHECK_ENDPOINT = 'https://oauth2-case.imsglobal.org/oauth2server/bearercheck'




class CASEClient(object):
    client_id = None
    client_secret = None
    access_token = None

    def __init__(self, client_id=None, client_secret=None):
        self.set_credentials(client_id=client_id, client_secret=client_secret)
        self.obtain_access_token()
        if self.is_authenticated():
            print('Client successfully authenticated.')

    def set_credentials(self, client_id=None, client_secret=None):
        if client_id and client_secret:
            self.client_id = client_id
            self.client_secret = client_secret
        elif os.path.exists(CREDENTIALS_PATH):
            print('Loading credentails from', CREDENTIALS_PATH)
            credentials = json.load(open(CREDENTIALS_PATH))
            self.client_id = credentials['client_id']
            self.client_secret = credentials['client_secret']
        else:
            print('Failed to load client_id and client_secret credentials.')
            sys.exit(-2)

    def obtain_access_token(self):
        """
        Call CLIENTOKEN_ENDPOINT to obtain access_token for the CASE API.
        """
        # set scope values (space-delimited list)
        scopes_requested = [
            "http://purl.imsglobal.org/casenetwork/case/v1p0/scope/core.readonly",
            "http://purl.imsglobal.org/casenetwork/case/v1p0/scope/all.readonly",
        ]
        scope = " ".join(scopes_requested)

        # prepare POST data and headers
        data = {
            "grant_type": "client_credentials",
            "scope": scope,
        }
        header_str = self.client_id + ':' + self.client_secret
        header_bytes = header_str.encode('ascii')
        basic_auth_header = base64.b64encode(header_bytes).decode('ascii')
        headers = {
            "Authorization": "Basic {}".format(basic_auth_header)
        }
        
        # POST request
        print('POST', CLIENTOKEN_ENDPOINT)
        response = requests.post(CLIENTOKEN_ENDPOINT, data, headers=headers, verify=False)
        assert response.ok, 'Failed to get access_token.' + str(response.text)
        access_token = response.json()['access_token']
        self.access_token = access_token

    def is_authenticated(self):
        url = BEARERCHECK_ENDPOINT + '?token={t}'.format(t=self.access_token)
        response = requests.get(url, verify=False)
        if response.ok:
            return True
        else:
            return False


    def get(self, path, params=None):
        """
        Makes the GET request to BASE_URL/{path}?{querystring} with querystring
        build from the parameters dictionary `params`.
        Returns JSON data returned by the API.
        """
        url = BASE_URL + path

        # build querystring from params
        if params:
            querystring = '?' + '&'.join([key+'='+str(val) for key, val in params.items()])
            url += querystring
        headers = {
            "Authorization": "Bearer {}".format(self.access_token)
        }
        print('GET', url)
        response = requests.get(url, headers=headers, verify=False)
        if response.status_code in [401, 403]:
            if not self.is_authenticated():
                self.obtain_access_token()
                headers = {
                    "Authorization": "Bearer {}".format(self.access_token)
                }
                response = requests.get(url, headers=headers, verify=False)
        if response.ok:
            return response.json()
        else:
            print('Error ' + str(response.status_code) + ' on GET ' + url)
            print(response.content)
            response.raise_for_status()        


    def get_documents(self):
        """
        Call BASE_URL/CFDocuments repeatedly to get complete list of `CFDocuments`.
        Returns complete list of `CFDocuments`s.
        """
        chunk_size = 50
        max_requests = 10
        CFDocuments_endpoint = '/CFDocuments'

        documents = []
        done = False
        counter = 0
        while done == False and counter < max_requests:
            params = {
                'offset': chunk_size*counter,
                'limit': chunk_size,
                'sort': 'identifier',
                'orderBy': 'asc',
            }
            data = self.get(CFDocuments_endpoint, params=params)
            documents_chunk = data['CFDocuments']
            if documents_chunk:
                documents.extend(documents_chunk)
                counter += 1
            else:
                done = True  # stop when receive empty list
        return documents




if __name__ == '__main__':
    """
    Calls CASE API to get complete list of docs and print them grouped by creator.
    """
    print('Calling CASE API at BASE_URL=', BASE_URL)

    client = CASEClient()
    all_documents = client.get_documents()
    print('Creator > CFDocuments::', len(all_documents), 'in total')
    print('====================================')
    sorted_documents = sorted(all_documents, key=itemgetter('creator', 'title'))
    documents_by_creator = dict((k, list(g)) for k, g in groupby(sorted_documents, key=itemgetter('creator')))
    for creator, documents in documents_by_creator.items():
        print('  - Creator:', creator)
        for document in documents:
            print('      -', document['title'], '('+document['adoptionStatus']+')', document['identifier'])
            # pprint(document)
            # print('\n')

