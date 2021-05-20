
# =============================================================================================
# This program is free software: you can redistribute it and/or modify it under the terms of
# the GNU General Public License as published by the Free Software Foundation, either version
# 3 of the License, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY;
# without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.
# This script must/should come together with a copy of the GNU General Public License. If not,
# access <http://www.gnu.org/licenses/> to find and read it.
#
# Author: Pedro Vernetti G.
# Name: OmniLyrics
# Description: MusicBrainz Picard plugin to fetch song lyrics from the web via GCS.
#
# #  In order to have this plugin working (if it is currently not), place it at:
#    ~/.config/MusicBrainz/Picard/plugins
# =============================================================================================

import re, time, requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import iso639



PLUGIN_NAME = 'OmniLyrics'
PLUGIN_AUTHOR = 'Pedro Vernetti G.'
PLUGIN_DESCRIPTION = 'Fetch lyrics from multiple sites via Google Custom Search Engine. ' \
                     'Lyrics provided are for educational purposes and personal use only. ' \
                     'Commercial use is not allowed.<br /><br />' \
                     'In order to use ' + PLUGIN_NAME + ' you need to set up your own Google Custom Search Engine at ' \
                     '<a href="https://cse.google.com/cse/create/new">cse.google.com</a> ' \
                     'and get your own Google Custom Search API key at ' \
                     '<a href="https://developers.google.com/custom-search/v1/overview#api_key">developers.google.com</a>.'
PLUGIN_VERSION = '0.1'
PLUGIN_API_VERSIONS = ['2.0', '2.1', '2.2', '2.3', '2.4', '2.5', '2.6']
PLUGIN_LICENSE = 'GPLv3'
PLUGIN_LICENSE_URL = 'https://www.gnu.org/licenses/gpl-3.0.en.html'

if (not (__name__ == "__main__")):
    runningAsPlugin = True
    from PyQt5 import QtWidgets
    from picard import config, log
    from picard.config import TextOption
    from picard.file import File
    from picard.metadata import register_track_metadata_processor
    from picard.track import Track
    from picard.ui.itemviews import BaseAction, register_file_action, register_track_action
    from picard.ui.options import OptionsPage, register_options_page
else:
    BaseAction = object
    runningAsPlugin = False
    from sys import argv, stderr, exit as sysexit
    from os import environ



def _letrasScraper( page ):
    all_extracts = page.select(r'div[class*="cnt-letra"]')
    if (not all_extracts): return None
    lyrics = r''
    for extract in all_extracts:
        for br in extract.find_all(r'br'): br.replace_with('\n')
        for p in extract.find_all(r'p'):
            lyrics += p.get_text() + '\n\n'
    return lyrics.strip()

def _geniusScraperMethod1( page ):
    extract = page.select(r'.lyrics')
    if (not extract): return None
    return extract[0].get_text().replace(r'<br>', '\n').strip()

def _geniusScraperMethod2( page ):
    all_extracts = page.select(r'div[class*="Lyrics__Container-sc-"]')
    if (not all_extracts): return None
    lyrics = r''
    for extract in all_extracts:
        for br in extract.find_all(r'br'): br.replace_with('\n')
        lyrics += extract.get_text()
    return lyrics.strip()

def _geniusScraper( page ):
    lyrics = _geniusScraperMethod1(page) or _geniusScraperMethod2(page)
    return lyrics

def _aZLyricsScraper( page ):
    extract = page.find(r'div', {r'id': None, r'class': None})
    if (not extract): return None
    for br in extract.find_all(r'br'): br.replace_with('\n')
    return extract.get_text().replace('\n\n', '\n').strip()

def _lyricsModeScraper( page ):
    extract = page.find(r'div', {r'id': r'lyrics_text'})
    for div in extract.find_all(r'div'): div.replace_with(r'')
    for br in extract.find_all(r'br'): br.replace_with('\n')
    return extract.get_text().replace('\n\n', '\n').strip()

def _vagalumeScraper( page ):
    extract = page.find(r'div', {r'id': r'lyrics'})
    if (not extract): return None
    for br in extract.find_all(r'br'): br.replace_with('\n')
    return extract.get_text().strip()

def _lyricsComScraper( page ):
    extract = page.find(r'pre', {r'id': r'lyric-body-text'})
    if (not extract): return None
    for a in extract.find_all(r'a'): a.replace_with_children()
    return extract.get_text().strip()

def _lyricsManiaScraper( page ):
    extract = page.find(r'div', {r'class': r'lyrics-body'})
    if (not extract): return None
    for br in extract.find_all(r'br'): br.replace_with('\n')
    return extract.get_text().replace('\n\n', '\n').strip()

# def _lHitScraper( page ):
    # extract = page.find(r'div', {r'class': r'div-more-in-page'})
    # if (not extract): return None
    #TODO: request returns blank string

def _glamShamScraper( page ):
    extract = page.find_all(r'font', class_=r'general')[5]
    if (not extract): return None
    for br in extract.find_all(r'br'): br.replace_with('\n')
    return extract.get_text().strip()

def _lyricsBellScraper( page ):
    extract = page.select(r'.lyrics-col p')
    if (not extract): return None
    lyrics = r''
    for i in range(len(extract)):
        lyrics += extract[i].get_text() + '\n\n'
    lyrics = lyrics.replace(r'<br>', '\n').strip()
    return lyrics

def _lyricsTEDScraper( page ):
    extract = page.select(r'.lyric-content p')
    if (not extract): return None
    lyrics = r''
    for i in range(len(extract)):
        lyrics += extract[i].get_text().strip() + '\n\n'
    return lyrics.replace(r'<br>', '\n').strip()

def _lyricsOffScraper( page ):
    extract = page.select(r'#main_lyrics p')
    if (not extract): return None
    lyrics = r''
    for i in range(len(extract)):
        lyrics += extract[i].get_text(separator='\n').strip() + '\n\n'
    return lyrics.strip()

def _lyricsMINTScraper( page ):
    extract = page.find(r'section', {r'id': r'lyrics'}).find_all(r'p')
    if (not extract): return None
    lyrics = r''
    for i in range(len(extract)):
        lyrics += extract[i].get_text().strip() + '\n\n'
    return lyrics.strip()



class OmniLyrics( BaseAction ):

    NAME = "Fetch Lyrics"

    scrapers = { r'letras.mus':     _letrasScraper,
                 r'genius':         _geniusScraper,
                 r'azlyrics':       _aZLyricsScraper,
                 r'lyricsmode':     _lyricsModeScraper,
                 r'vagalume':       _vagalumeScraper,
                 r'lyrics.com':     _lyricsComScraper,
                 r'lyricsmania':    _lyricsManiaScraper,
                 r'glamsham':       _glamShamScraper,
                 r'lyricsbell':     _lyricsBellScraper,
                 r'lyricsted':      _lyricsTEDScraper,
                 r'lyricsoff':      _lyricsOffScraper,
                 r'lyricsmint':     _lyricsMINTScraper, }

    validGCSLanguages = { r'ar', r'bg', r'ca', r'cs', r'da', r'de', r'el',
                          r'en', r'es', r'et', r'fi', r'fr', r'hr', r'hu',
                          r'id', r'is', r'it', r'iw', r'ja', r'ko', r'lt',
                          r'lv', r'nl', r'no', r'pl', r'pt', r'ro', r'ru',
                          r'sk', r'sl', r'sr', r'sv', r'tr', }

    headers = { r'User-Agent': r'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:88.0) Gecko/20100101 Firefox/88.0',
                r'Referer': r'https://www.google.com/',
                r'Accept': r'text/html,application/xhtml+xml', }

    requestFailureHistory = {}

    def __init__( self ):
        super().__init__()
        if (not runningAsPlugin):
            self.gcsAPIKey = environ[r'GCS_API_KEY']
            self.gcsEngineID = environ[r'GCS_ENGINE_ID']
            if (type(self.gcsAPIKey) != str):
                stderr.write('GCS_API_KEY not set\n')
                sysexit(1)
            if (type(self.gcsEngineID) != str):
                stderr.write('GCS_ENGINE_ID not set\n')
                sysexit(1)

    def _request( self, url, params=None, headers=None ):
        netloc = urlparse(url).netloc
        if (netloc in self.requestFailureHistory):
            if (self.requestFailureHistory[netloc][1] == 429):
                if (time.time() > (self.requestFailureHistory[netloc][0] + 3600)):
                    self.requestFailureHistory.pop(netloc, None)
                else:
                    return None
            else:
                if (time.time() > (self.requestFailureHistory[netloc][0] + 60)):
                    self.requestFailureHistory.pop(netloc, None)
                else:
                    return None
        limit = time.time() + 10
        while time.time() <= limit:
            try:
                response = requests.get(url, params=params, headers=headers)
                if (response.status_code == 200): break
                if (response.status_code == 429):
                    self.requestFailureHistory[netloc] = (time.time(), 429)
                    break
            except:
                pass
        if (response.status_code != 200):
            self.requestFailureHistory[netloc] = (time.time(), response.status_code)
            if (not runningAsPlugin): print(r'HTTP ' + str(response.status_code))
            return None
        else: return response

    def _query( self, song, language ):
        if (runningAsPlugin):
            self.gcsAPIKey = config.setting[r'gcsAPIKey']
            self.gcsEngineID = config.setting[r'gcsEngineID']
            if ((type(self.gcsAPIKey) != str) or (type(self.gcsEngineID) != str)):
                error = 'GCS API key or machine ID missing'
                log.debug('{}: {}'.format(PLUGIN_NAME, error))
                return None
        customSearchURL = r'https://www.googleapis.com/customsearch/v1/siterestrict'
        customSearchParameters = {r'key': self.gcsAPIKey, r'cx': self.gcsEngineID, r'q': song,}
        if (language != r'und'):
            try: language = iso639.languages.part3.get(language).part1
            except: language = r'und'
            if (language in self.validGCSLanguages):
                customSearchParameters[r'lr'] = (r'lang_' + language)
        response = self._request(customSearchURL, params=customSearchParameters)
        return response

    def _lyrics( self, resultURL ):
        page = self._request(resultURL, headers=self.headers)
        page = BeautifulSoup(page.content, r'lxml')
        for domain, scraper in self.scrapers.items():
            if (domain in resultURL): return scraper(page)
        return None # no scrapper available for this search result

    def fetchLyrics( self, artist, title, language ):
        if (not runningAsPlugin):
            lang = iso639.languages.part3.get(language, iso639.languages.part3[r'und']).name
            lang = language + r' (' + lang + r')'
            print('\n TITLE:    ', title, '\n ARTIST:   ', artist, '\n LANGUAGE: ', lang, '\n')
        query = self._query((artist.strip() + r' ' + title.strip()), language)
        if (not query): return r''
        query = query.json()
        correctedQuery = query.get(r'spelling', {}).get(r'correctedQuery')
        if (correctedQuery): query = self._query(correctedQuery, language)
        queryResults = query.get(r'items', [])
        # try scraping lyrics from top search results:
        for i in range(len(queryResults)):
            result_url = queryResults[i][r'link']
            try: lyrics = self._lyrics(result_url)
            except: lyrics = r''
            if (lyrics): return re.sub(r'[\t \u00A0\u1680\u2000-\u200A\u202F\u205F\u3000]+', r' ', lyrics)
        return r'' # no results

    def process( self, album, metadata, track, release, action=False ):
        if ((not action) and (len(metadata.get(r'lyrics', r'')))): return
        artist = metadata.get(r'artist', None)
        if (not artist):
            log.debug(r'{}: cannot fetch lyrics without artist information'.format(PLUGIN_NAME))
            return
        title = metadata.get(r'title', None)
        if (not title):
            log.debug(r'{}: cannot fetch lyrics without track title information'.format(PLUGIN_NAME))
            return
        language = metadata.get(r'language', metadata.get(r'~releaselanguage', r'und'))
        if (language not in iso639.languages.part3):
            if (language.title() in iso639.languages.name):
                language = iso639.languages.name(language.title()).part3
            elif (language in iso639.languages.part1):
                language = iso639.languages.part1(language).part3
            else:
                language = r'und'
        if (language == r'und'):
            metadata[r'language'] = r'' #TODO is this the right key?
        elif (language == r'zxx'):
            metadata[r'lyrics'] = r'[Instrumental]'
            return
        else:
            metadata[r'language'] = language #TODO is this the right key?
        log.debug(r'{}: fetching lyrics for "{}" by '.format(PLUGIN_NAME, title, artist))
        lyrics = self.fetchLyrics(artist, title, language)
        if (not lyrics): return
        log.debug('{}: lyrics found for for "{}" by {}'.format(PLUGIN_NAME, title, artist))
        print(lyrics)
        print('\n')
        if (not metadata.get(r'lyrics', None)): metadata[r'lyrics'] = lyrics

    def callback( self, objs ):
        for obj in objs:
            if isinstance(obj, Track):
                for f in obj.linked_files: self.process(None, f.metadata, None, None, True)
            elif isinstance(obj, File):
                self.process(None, obj.metadata, None, None, True)



if (runningAsPlugin):

    class OmniLyricsOptionsPage( OptionsPage ):

        NAME = r'omnilyrics'
        TITLE = PLUGIN_NAME
        PARENT = r'plugins'

        options = [TextOption(r'setting', r'gcsAPIKey', r' '),
                   TextOption(r'setting', r'gcsEngineID', r' ')]

        def __init__( self, parent=None ):
            super().__init__(parent)
            self.box = QtWidgets.QVBoxLayout(self)
            self.disclaimer = QtWidgets.QLabel(self)
            self.disclaimer.setText('Lyrics fetched by ' + PLUGIN_NAME + ' are for educational purposes and personal use only.\n'
                                    'Commercial use is not allowed.\n')
            self.box.addWidget(self.disclaimer)
            self.apiKeyLabel = QtWidgets.QLabel(self)
            self.apiKeyLabel.setText('Google Custom Search API Key')
            self.box.addWidget(self.apiKeyLabel)
            self.apiKeyDescription = QtWidgets.QLabel(self)
            self.apiKeyDescription.setText('TODO' '... sorry')
            self.apiKeyDescription.setOpenExternalLinks(True)
            self.box.addWidget(self.apiKeyDescription)
            self.apiKeyInput = QtWidgets.QLineEdit(self)
            self.box.addWidget(self.apiKeyInput)
            self.idLabel = QtWidgets.QLabel(self)
            self.idLabel.setText('Engine ID (of your Google Custom Search Engine)')
            self.box.addWidget(self.idLabel)
            self.idDescription = QtWidgets.QLabel(self)
            self.idDescription.setText('TODO' '... sorry')
            self.idDescription.setOpenExternalLinks(True)
            self.box.addWidget(self.idDescription)
            self.idInput = QtWidgets.QLineEdit(self)
            self.box.addWidget(self.idInput)
            self.spacer = QtWidgets.QSpacerItem(0, 0, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding)
            self.box.addItem(self.spacer)

        def load( self ):
            self.apiKeyInput.setText(config.setting[r'gcsAPIKey'])
            self.idInput.setText(config.setting[r'gcsEngineID'])

        def save( self ):
            config.setting[r'gcsAPIKey'] = self.apiKeyInput.text()
            config.setting[r'gcsEngineID'] = self.idInput.text()



    register_file_action(OmniLyrics())
    register_track_action(OmniLyrics())
    # register_track_metadata_processor(OmniLyrics().process)
    register_options_page(OmniLyricsOptionsPage)



else:

    omnilyrics = OmniLyrics()
    lyrics = r''
    if (len(argv) == 4): lyrics = omnilyrics.fetchLyrics(argv[-3], argv[-2], argv[-1])
    elif (len(argv) == 3): lyrics = omnilyrics.fetchLyrics(argv[-2], argv[-1], r'und')
    else: print("Usage: python3 '" + argv[0] + "' ARTIST TITLE [LANGUAGE]")
    if (len(lyrics)): print(lyrics)
