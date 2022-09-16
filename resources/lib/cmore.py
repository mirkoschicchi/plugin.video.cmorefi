# -*- coding: utf-8 -*-
"""
A Kodi-agnostic library for CMore
"""
import os
import json
import codecs
import http.cookiejar
import time
import unicodedata
import urllib.parse

import calendar
from datetime import datetime, timedelta

import requests

class CMore(object):
    def __init__(self, settings_folder, debug=False):
        self.debug = debug
        self.http_session = requests.Session()
        self.settings_folder = settings_folder
        self.tempdir = os.path.join(settings_folder, 'tmp')
        if not os.path.exists(self.tempdir):
            os.makedirs(self.tempdir)
        self.cookie_jar = http.cookiejar.LWPCookieJar(os.path.join(self.settings_folder, 'cookie_file'))
        self.config_path = os.path.join(self.settings_folder, 'configuration.json')
        self.config = self.get_config()

        try:
            self.cookie_jar.load(ignore_discard=True, ignore_expires=True)
        except IOError:
            pass
        self.http_session.cookies = self.cookie_jar

    class CMoreError(Exception):
        def __init__(self, value):
            self.value = value

        def __str__(self):
            return repr(self.value)

    def log(self, string):
        if self.debug:
            try:
                print('[CMore]: %s' % string)
            except UnicodeEncodeError:
                # we can't anticipate everything in unicode they might throw at
                # us, but we can handle a simple BOM
                bom = unicodedata(codecs.BOM_UTF8, 'utf8')
                print('[CMore]: %s' % string.replace(bom, ''))
            except:
                pass

    def make_request(self, url, method, params=None, payload=None, headers=None):
        """Make an HTTP request. Return the response."""
        self.log('Request URL: %s' % url)
        self.log('Method: %s' % method)
        self.log('Params: %s' % params)
        self.log('Payload: %s' % payload)
        self.log('Headers: %s' % headers)
        try:
            if method == 'get':
                req = self.http_session.get(url, params=params, headers=headers)
            elif method == 'put':
                req = self.http_session.put(url, params=params, data=payload, headers=headers)
            else:  # post
                req = self.http_session.post(url, params=params, data=payload, headers=headers)
            self.log('Response code: %s' % req.status_code)
            self.log('Response: %s' % req.content)
            self.cookie_jar.save(ignore_discard=True, ignore_expires=False)
            self.raise_cmore_error(req.content)
            return req.content

        except requests.exceptions.ConnectionError as error:
            self.log('Connection Error: - %s' % error.message)
            raise
        except requests.exceptions.RequestException as error:
            self.log('Error: - %s' % error.value)
            raise

    def raise_cmore_error(self, response):
        try:
            error = json.loads(response)
            if isinstance(error, dict):
                if 'error' in error.keys():
                    if 'message' in error['error'].keys():
                        raise self.CMoreError(error['error']['message'])
                    elif 'code' in error['error'].keys():
                        raise self.CMoreError(error['error']['code'])
                if 'response' in error.keys(): # Response is not always error but we need this to check if login is OK
                    if error['response']['code'] == 'AUTHENTICATION_FAILED':
                        raise self.CMoreError(error['response']['code'])
            elif isinstance(error, str):
                raise self.CMoreError(error)

            #raise self.CMoreError('Error')  # generic error message

        except TypeError:
            pass
        except KeyError:
            pass
        except ValueError:  # when response is not in json
            pass

    def get_config(self):
        """Return the config in a dict."""
        try:
            config = json.load(open(self.config_path))
        except IOError:
            self.download_config()
            config = json.load(open(self.config_path))

        return config

    def download_config(self):
        """Download the C More configuration."""
        url = 'https://www.katsomo.fi/mb/v2/static/svod/web/config/web'

        config_data = self.make_request(url, 'get', params='')
        with open(self.config_path, 'w') as fh_config:
            fh_config.write(config_data)

    def login(self, username=None, password=None):
        url = 'https://api.katsomo.fi/api/authentication/user/login.json'

        method = 'post'
        payload = {
            'username': username,
            'password': password,
            'rememberMe': 'true'
        }

        return self.make_request(url, method, payload=payload)

    def get_search_data(self, query):
        url = self.config['dynamicMbApiUrl'] + '/search'
        params = {
            'query': query,
            'size': 100
        }

        data = json.loads(self.make_request(url, 'get', params=params))
        return data['assets'] + data['categories']

    def get_path_dataurl(self, path):
        paths = self.get_page(page_type='/paths')
        for i in paths:
            if i['visibleUrl'] == path:
                return i

    # Get actual dataurl for target and return content
    def get_target_path(self, target):
        paths = self.get_page(page_type='/paths')
        parsed = urllib.parse.urlparse.urlparse(target)

        for i in paths:
            if i['path'] == parsed.path:

                params = {
                    'sort': urllib.parse.urlparse.parse_qs(parsed.query)['sort'],
                    'size': 100
                }
                data = json.loads(self.make_request(i['dataUrl'], 'get', params=params))

                return data['result']

    def get_page(self, page_type=None, dataurl=None):
        if dataurl:
            url = dataurl
        else:
            url = self.config['staticMbApiUrl'] + page_type

        data = json.loads(self.make_request(url, 'get'))
        return data

    def parse_page(self, dataurl=None):
        page = self.get_page(dataurl=dataurl)

        if isinstance(page, list):
            return page
        elif 'result' in page.keys():
            return page['result']  # movies/series
        elif page.get('category'): # Event categories (Formula 1)
            if page['category'].get('groups'):
                return page['category']['groups'] # Return only categories

        # if nothing matches
        self.log('Failed to parse page.')
        return False

    def get_stream(self, video_id):
        stream = {}
        allowed_formats = ['ism', 'ismusp', 'mpd']
        url = self.config['vimondApiUrl'] + '/api/web/asset/{0}/play.json'.format(video_id)
        params = {'protocol': 'MPD'}
        data_dict = json.loads(self.make_request(url, 'get', params=params, headers=None))['playback']

        stream['drm_protected'] = data_dict['drmProtected']

        if isinstance(data_dict['items']['item'], list):
            for i in data_dict['items']['item']:
                if i['mediaFormat'] in allowed_formats:
                    stream['mpd_url'] = i['url']
                    if stream['drm_protected']:
                        stream['license_url'] = i['license']['@uri']
                        stream['drm_type'] = i['license']['@name']
                    break
        else:
            stream['mpd_url'] = data_dict['items']['item']['url']
            if stream['drm_protected']:
                stream['license_url'] = data_dict['items']['item']['license']['@uri']
                stream['drm_type'] = data_dict['items']['item']['license']['@name']

        return stream

    def parse_datetime(self, event_date=None, epg_date=None):
        """Parse date string to datetime object."""
        if event_date:
            date_time_format = '%Y-%m-%dT%H:%M:%SZ'
            datetime_obj = datetime(*(time.strptime(event_date, date_time_format)[0:6]))
        else:
            date_time_format = '%Y-%m-%dT%H:%M:%S'
            date = epg_date.split('+')
            datetime_obj = datetime(*(time.strptime(date[0], date_time_format)[0:6]))
        return datetime_obj

    def get_current_time(self, utc=None):
        """Return the current local time."""
        if utc:
            return datetime.utcnow()
        else:
            return datetime.now()

    # Sport live streams start time is in UTC, we need to convert it to localtime
    def utc_to_local(self, utc_dt):
        # get integer timestamp to avoid precision lost
        timestamp = calendar.timegm(utc_dt.timetuple())
        local_dt = datetime.fromtimestamp(timestamp)
        assert utc_dt.resolution >= timedelta(microseconds=1)
        return local_dt.replace(microsecond=utc_dt.microsecond)

    def aslocaltimestr(self, utc_dt):
        return self.utc_to_local(self.parse_datetime(event_date=utc_dt)).strftime('%d.%m.%Y %H:%M')