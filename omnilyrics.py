
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
# #  In order to have this plugin working (if it is currently not), install its dependencies:
#    'beautifulsoup4', r'unidecode, 'iso-639' and 'langdetect'
# #  ...then place it at: ~/.config/MusicBrainz/Picard/plugins
# =============================================================================================

import re, time, requests
from random import shuffle
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from unidecode import unidecode
import iso639
from langdetect import detect_langs as langdetect



PLUGIN_NAME = 'OmniLyrics'
PLUGIN_AUTHOR = 'Pedro Vernetti G.'
PLUGIN_DESCRIPTION = 'Fetch lyrics from multiple sites via Google Custom Search Engine. ' \
                     'Lyrics provided are for educational purposes and personal use only. ' \
                     'Commercial use is not allowed.<br /><br />' \
                     'In order to use ' + PLUGIN_NAME + ' you need to set up your own Google Custom Search Engine at ' \
                     '<a href="https://cse.google.com/cse/create/new">cse.google.com</a> ' \
                     'and get your own Google Custom Search API key at ' \
                     '<a href="https://developers.google.com/custom-search/v1/overview#api_key">developers.google.com</a>.'
PLUGIN_VERSION = '0.3'
PLUGIN_API_VERSIONS = ['2.0', '2.1', '2.2', '2.3', '2.4', '2.5', '2.6']
PLUGIN_LICENSE = 'GPLv3'
PLUGIN_LICENSE_URL = 'https://www.gnu.org/licenses/gpl-3.0.en.html'

if (not (__name__ == "__main__")):
    runningAsPlugin = True
    from functools import partial
    from PyQt5 import QtWidgets
    from picard import config, log
    from picard.config import TextOption, BoolOption
    from picard.file import File, register_file_post_addition_to_track_processor
    from picard.metadata import register_track_metadata_processor
    from picard.plugin import PluginPriority
    from picard.track import Track
    from picard.ui.itemviews import BaseAction, register_file_action, register_track_action
    from picard.ui.options import OptionsPage, register_options_page
    from picard.util import thread
else:
    BaseAction = object
    runningAsPlugin = False
    from sys import argv, stderr, exit as sysexit
    from os import environ



def _letrasScraper( page, normArtist, normTitle ):
    title = page.find_all(r'div', {r'class': r'cnt-head_title'})
    if (title):
        artist = title[0].find_all(r'h2')
        title = title[0].find_all(r'h1')
        if (artist):
            artist = re.sub(r'\W', r'', unidecode(artist[0].get_text().casefold()))
            if (artist != normArtist): return None
        if (title):
            title = re.sub(r'\W', r'', unidecode(title[0].get_text().casefold()))
            if (title != normTitle): return None
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

def _geniusScraper( page, normArtist, normTitle ):
    title = page.find_all(r'h1')
    if (title):
        title = re.sub(r'[^a-z0-9]', r'', title[0].get_text().casefold())
        if (title != normTitle): return None
    artist = page.find_all(r'a', {r'class': r'header_with_cover_art-primary_info-primary_artist'})
    if (artist):
        artist = re.sub(r'[^a-z0-9]', r'', artist[0].get_text().casefold())
        if (artist != normArtist): return None
    lyrics = _geniusScraperMethod1(page) or _geniusScraperMethod2(page)
    return lyrics

def _aZLyricsScraper( page, normArtist, normTitle ):
    title = page.find_all(r'h1')
    if (title):
        title = re.sub(r'[^a-z0-9]', r'', title[0].get_text()[1:-7].casefold())
        if (title != normTitle): return None
    artist = page.find_all(r'h2')
    if (artist):
        artist = re.sub(r'[^a-z0-9]', r'', artist[0].get_text()[:-7].casefold())
        if (artist != normArtist): return None
    extract = page.find(r'div', {r'id': None, r'class': None})
    if (not extract): return None
    for br in extract.find_all(r'br'): br.replace_with('\n')
    return extract.get_text().replace('\n\n', '\n').strip()

def _lyricsModeScraper( page, normArtist, normTitle ):
    title = page.select(r'h1[class*=song_name]')
    if (title):
        title = title[0].find_all(r'span')
        if (title):
            artist = re.sub(r'[^a-z0-9]', r'', title[0].get_text()[1:-7].casefold())
            if (artist != normArtist): return None
            if (len(title) > 1):
                title = re.sub(r'[^a-z0-9]', r'', title[1].get_text()[1:-7].casefold())
                if (title != normTitle): return None
    extract = page.find(r'div', {r'id': r'lyrics_text'})
    for div in extract.find_all(r'div'): div.replace_with(r'')
    for br in extract.find_all(r'br'): br.replace_with('\n')
    return extract.get_text().replace('\n\n', '\n').strip()

def _vagalumeScraper( page, normArtist, normTitle ):
    artist = page.find_all(r'h1')
    if (artist):
        if (len(artist) > 1):
            title = re.sub(r'[^a-z0-9]', r'', artist[1].get_text().casefold())
            if (title != normTitle): return None
        artist = re.sub(r'[^a-z0-9]', r'', artist[0].get_text().casefold())
        if (artist != normArtist): return None
    extract = page.find(r'div', {r'id': r'lyrics'})
    if (not extract): return None
    for br in extract.find_all(r'br'): br.replace_with('\n')
    return extract.get_text().strip()

def _lyricsComScraper( page, normArtist, normTitle ):
    title = page.find_all(r'h1', {r'id': r'lyric-title-text'})
    if (title):
        title = re.sub(r'[^a-z0-9]', r'', title[0].get_text().casefold())
        if (title != normTitle): return None
    artist = page.find_all(r'h3', {r'class': r'lyric-artist'})
    if (artist):
        artist = artist[0].find_all(r'a')
        if (artist):
            artist = re.sub(r'[^a-z0-9]', r'', artist[0].get_text().casefold())
            if (artist != normArtist): return None
    extract = page.find(r'pre', {r'id': r'lyric-body-text'})
    if (not extract): return None
    for a in extract.find_all(r'a'): a.replace_with_children()
    return extract.get_text().strip()

def _lyricsManiaScraper( page, normArtist, normTitle ):
    title = page.find_all(r'h1')
    if (title):
        title = re.sub(r'[^a-z0-9]', r'', title[0].get_text().casefold())
        if (title != normTitle): return None
    artist = page.find_all(r'h2')
    if (artist):
        artist = re.sub(r'[^a-z0-9]', r'', artist[0].get_text().casefold())
        if (artist != normArtist): return None
    extract = page.find(r'div', {r'class': r'lyrics-body'})
    if (not extract): return None
    for br in extract.find_all(r'br'): br.replace_with('\n')
    return extract.get_text().replace('\n\n', '\n').strip()

# def _lHitScraper( page, normArtist, normTitle ):
    # extract = page.find(r'div', {r'class': r'div-more-in-page'})
    # if (not extract): return None
    #TODO: request returns blank string

def _metroLyricsScraper( page, normArtist, normTitle ):
    title = page.find_all(r'h1')
    if (title):
        title = re.sub(r'[^a-z0-9]', r'', title[0].get_text()[:-7].casefold())
        if (title != (normArtist + normTitle)): return None
    extract = page.find(r'div', {r'id': r'lyrics-body-text'})
    if (not extract): return None
    for br in extract.find_all(r'br'): br.replace_with('\n')
    lyrics = r''
    for p in extract.find_all(r'p', {r'class': r'verse'}):
        lyrics += (p.get_text().replace('\n\n', '\n') + '\n\n')
    return lyrics.strip()

def _lyricsBellScraper( page, normArtist, normTitle ):
    title = page.find_all(r'h1')
    if (title):
        title = re.sub(r'[^a-z0-9]', r'', title[0].get_text().casefold())
        if (title != (normTitle + r'lyrics' + normArtist)): return None
    extract = page.select(r'.lyrics-col p')
    if (not extract): return None
    lyrics = r''
    for i in range(len(extract)):
        lyrics += extract[i].get_text() + '\n\n'
    lyrics = lyrics.replace(r'<br>', '\n').strip()
    return lyrics

def _lyricsTEDScraper( page, normArtist, normTitle ):
    title = page.find_all(r'h1')
    if (title):
        title = re.sub(r'[^a-z0-9]', r'', title[0].get_text().casefold())
        if (not title.startswith(normTitle)): return None
    extract = page.select(r'.lyric-content p')
    if (not extract): return None
    lyrics = r''
    for i in range(len(extract)):
        lyrics += extract[i].get_text().strip() + '\n\n'
    return lyrics.replace(r'<br>', '\n').strip()

def _lyricsOffScraper( page, normArtist, normTitle ):
    title = page.find_all(r'h1')
    if (title):
        title = re.sub(r'[^a-z0-9]', r'', title[0].get_text().casefold())
        if (not title.startswith(normTitle)): return None
    extract = page.select(r'#main_lyrics p')
    if (not extract): return None
    lyrics = r''
    for i in range(len(extract)):
        lyrics += extract[i].get_text(separator='\n').strip() + '\n\n'
    return lyrics.strip()

def _lyricsMINTScraper( page, normArtist, normTitle ):
    title = page.find_all(r'h1')
    if (title):
        title = re.sub(r'[^a-z0-9]', r'', title[0].get_text().casefold())
        if (title != (normTitle + r'lyrics' + normArtist)): return None
    extract = page.find(r'section', {r'id': r'lyrics'}).find_all(r'p')
    if (not extract): return None
    lyrics = r''
    for i in range(len(extract)):
        lyrics += extract[i].get_text().strip() + '\n\n'
    return lyrics.strip()

def _glamShamScraper( page, normArtist, normTitle ):
    extract = page.find_all(r'font', class_=r'general')[5]
    if (not extract): return None
    for br in extract.find_all(r'br'): br.replace_with('\n')
    return extract.get_text().strip()



def _letrasURL( artist, title ):
    artistURL = re.sub(r'[\s/-]+', r'-', re.sub(r'[^\w\s/-]', r'', unidecode(artist.casefold())))
    artistURL = r'https://www.letras.mus.br/' + artistURL.strip(r'-') + r'/'
    try: artistPage = requests.get(artistURL, headers=OmniLyrics.headers)
    except: return None
    if (not artistPage): return None
    artistPage = BeautifulSoup(artistPage.content, r'lxml')
    songs = artistPage.find_all(r'a', {r'class': r'song-name'})
    if (not songs):
        songs = artistPage.find_all(r'div', {r'class': r'list-container'})
        if (not songs): return None
        songs = songs[0].find_all(r'a')
        title = re.sub(r'\W', r'', title.casefold())
        for song in songs:
            if (re.sub(r'\W', r'', song.get_text().casefold()).endswith(title)):
                return (r'https://www.letras.mus.br' + song[r'href'])
        return None
    title = re.sub(r'\W', r'', title.casefold())
    for song in songs:
        if (re.sub(r'\W', r'', song.get_text().casefold()).endswith(title)):
            return (r'https://www.letras.mus.br' + song[r'href'])
    return None

def _geniusURL( artist, title ):
    artist = unidecode(artist[0].title() + artist[1:].casefold())
    title = unidecode(re.sub(r'[æǽǣǳǆĳǉǌœȹ]', r'', title.casefold())).replace(r'&', r' and ')
    artist = re.sub(r'[\s-]+', r'-', re.sub(r'[^\w\s-]+', r'', artist)).strip(r'-')
    title = re.sub(r'[\s-]+', r'-', re.sub(r'[^\w\s-]+', r'', title)).strip(r'-')
    return (r'https://genius.com/' + artist + r'-' + title + r'-lyrics')

def _aZLyricsURL( artist, title ):
    artist = re.sub(r'\W+', r'', unidecode(artist.casefold()))
    title = re.sub(r'\W+', r'', unidecode(title.casefold()))
    return (r'https://www.azlyrics.com/lyrics/' + artist[0] + r'/' + artist + r'/' + title + '.html')

def _lyricsModeURL( artist, title ):
    artist = re.sub(r'[^a-z0-9\s_-]+', r'', artist.upper().casefold())
    title = re.sub(r'[^a-z0-9\s_-]+', r'', title.upper().casefold())
    artist = re.sub(r'[\s_-]+', r'_', artist).strip(r'_')
    title = re.sub(r'[\s_-]+', r'_', title).strip(r'_')
    return (r'https://www.lyricsmode.com/lyrics/' + artist[0] + r'/' + artist + r'/' + title + r'.html')

def _vagalumeURL( artist, title ):
    artist = re.sub(r'\W+', r'-', unidecode(artist.casefold())).strip(r'-')
    title = re.sub(r'\W+', r'-', unidecode(title.casefold())).strip(r'-')
    return (r'https://www.vagalume.com.br/' + artist + r'/' + title + r'.html')

def _lyricsComURL( artist, title ):
    pass #TODO

def _lyricsManiaURL( artist, title ):
    pass #TODO

def _metroLyricsURL( artist, title ):
    artist = re.sub(r'\s+', r'-', re.sub(r'[^\w\s]', r'', unidecode(artist.casefold())))
    title = re.sub(r'\s+', r'-', re.sub(r'[^\w\s]', r'', unidecode(title.casefold())))
    return (r'https://www.metrolyrics.com/' + title.strip(r'-') + r'-' + artist.strip(r'-') + r'.html')



class OmniLyrics( BaseAction ):

    NAME = "Fetch Lyrics"

    scrapers = { r'letras.mus':     _letrasScraper,
                 r'genius':         _geniusScraper,
                 r'azlyrics':       _aZLyricsScraper,
                 r'lyricsmode':     _lyricsModeScraper,
                 r'vagalume':       _vagalumeScraper,
                 r'lyrics.com':     _lyricsComScraper,
                 r'lyricsmania':    _lyricsManiaScraper,
                 r'metrolyrics':    _metroLyricsScraper,
                 r'lyricsbell':     _lyricsBellScraper,
                 r'lyricsted':      _lyricsTEDScraper,
                 r'lyricsoff':      _lyricsOffScraper,
                 r'lyricsmint':     _lyricsMINTScraper,
                 r'glamsham':       _glamShamScraper, }

    _autoURLS = [ _letrasURL, _geniusURL, _aZLyricsURL, _lyricsModeURL,
                  _vagalumeURL, _lyricsComURL, _lyricsManiaURL, _metroLyricsURL ]

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
        try:
            response = requests.get(url, params=params, headers=headers)
            status = response.status_code
        except:
            status = 418
        if (status == 429):
            self.requestFailureHistory[netloc] = (time.time(), 429)
            return None
        elif (status != 200):
            return None
            # limit = time.time() + 10
            # while time.time() <= limit:
                # try:
                    # response = requests.get(url, params=params, headers=headers)
                    # if (response.status_code == 200):
                        # status = response.status_code
                        # break
                    # if (response.status_code == 429):
                        # self.requestFailureHistory[netloc] = (time.time(), 429)
                        # return None
                # except:
                    # status = 418
            # if (status != 200):
                # self.requestFailureHistory[netloc] = (time.time(), response.status_code)
                # if (not runningAsPlugin): print(r'HTTP ' + str(response.status_code))
                # return None
        else:
            return response

    def _query( self, song, language ):
        if (runningAsPlugin):
            self.gcsAPIKey = config.setting[r'gcsAPIKey']
            self.gcsEngineID = config.setting[r'gcsEngineID']
            if ((type(self.gcsAPIKey) != str) or (type(self.gcsEngineID) != str)): return None
        customSearchURL = r'https://www.googleapis.com/customsearch/v1/siterestrict'
        customSearchParameters = {r'key': self.gcsAPIKey, r'cx': self.gcsEngineID, r'q': song,}
        if (language != r'und'):
            try: language = iso639.languages.part3.get(language).part1
            except: language = r'und'
            if (language in self.validGCSLanguages):
                customSearchParameters[r'lr'] = (r'lang_' + language)
        response = self._request(customSearchURL, params=customSearchParameters)
        return response

    def _lyrics( self, lyricsURL, normArtist, normTitle ):
        if (not lyricsURL): return None
        page = self._request(lyricsURL, headers=self.headers)
        if (not page): return None
        page = BeautifulSoup(page.content, r'lxml')
        for domain, scraper in self.scrapers.items():
            if (domain in lyricsURL): return scraper(page, normArtist, normTitle)
        return None # no scraper available for this search result

    def _fetchThroughGCS( self, artist, title, language ):
        query = re.sub(r'[^\w\s]', r'', (artist.strip() + r' ' + title.strip()))
        query = self._query(query, language)
        if (not query): return r''
        query = query.json()
        correctedQuery = query.get(r'spelling', {}).get(r'correctedQuery')
        if (correctedQuery): query = self._query(correctedQuery, language).json()
        queryResults = query.get(r'items', [])
        # try scraping lyrics from top search results:
        normArtist = re.sub(r'[^a-z0-9]', r'', artist.casefold())
        normTitle = re.sub(r'[^a-z0-9]', r'', title.casefold())
        for i in range(len(queryResults)):
            resultURL = queryResults[i][r'link']
            try: lyrics = self._lyrics(resultURL, normArtist, normTitle)
            except: lyrics = r''
            if (lyrics):
                if (not runningAsPlugin):
                    print('Lyrics for "' + title + '" fetched through GCS from ' + resultURL + '\n')
                return lyrics
        return r'' # no results

    def _fetchDirectly( self, artist, title, language ):
        urls = [generateURL(artist, title) for generateURL in self._autoURLS]
        urls = [url for url in urls if ((type(url) == str) and len(url))]
        shuffle(urls)
        normArtist = re.sub(r'[^a-z0-9]', r'', artist.casefold())
        normTitle = re.sub(r'[^a-z0-9]', r'', title.casefold())
        for url in urls:
            lyrics = self._lyrics(url, normArtist, normTitle)
            if (lyrics):
                if (not runningAsPlugin):
                    print('Lyrics for "' + title + '" fetched from ' + url + '\n')
                return lyrics
        return r''

    def fetchLyrics( self, artist, title, language ):
        if (not artist):
            log.debug(r'{}: cannot fetch lyrics without artist information'.format(PLUGIN_NAME))
            return r''
        if (not title):
            log.debug(r'{}: cannot fetch lyrics without track title information'.format(PLUGIN_NAME))
            return r''
        if (not runningAsPlugin):
            lang = iso639.languages.part3.get(language, iso639.languages.part3[r'und']).name
            lang = language + r' (' + lang + r')'
            print('\n TITLE:    ', title, '\n ARTIST:   ', artist, '\n LANGUAGE: ', lang, '\n')
        lyrics = self._fetchDirectly(artist, title, language)
        if (not lyrics): lyrics = self._fetchThroughGCS(artist, title, language)
        return lyrics

    def _fixedLanguage( self, language ):
        language = re.sub(r'[\s_-]+', r' ', language)
        if (language in iso639.languages.part1):
            return iso639.languages.part1[language].part3
        else:
            language = language.title()
            if (language in iso639.languages.name):
                return iso639.languages.name[language].part3
            else:
                return r'und'

    def _detectLanguage( self, lyrics ):
        if (not lyrics): return (r'und', 1)
        lyrics = re.sub(r' +', r' ', re.sub(r'\W', r' ', re.sub(r'\[[^\]]*\]', r'', lyrics)))
        if (len(lyrics) < 5): return (r'und', 1)
        lang = langdetect(lyrics)[0]
        return (iso639.languages.part1[lang.lang[:2]].part3, lang.prob)

    def _repeatedLine( self, x ):
        line = x.group(1)
        nextChar = x.group(5)
        if (not nextChar): nextChar = r''
        times = x.group(3) if (not x.group(4)) else x.group(4)
        if (re.match(r'^\n *\[[^\n\]]+\] *$', line)):
            line += '\n'
            if (re.match(r'\w$', nextChar)): return ((line * int(times)) + nextChar)
        return ((line * int(times)) + '\n' + nextChar)

    def _expandedLyrics( self, lyrics ):
        lyrics = '\n' + lyrics + '\n'
        wellKnownPartNames = r'(vers|stro|(pr\w\W?)?chor|refr|estribillo|ritornello|solo\W\w|[^\n]+\Wsolo|'
        wellKnownPartNames += r'リフレイ|후렴|英語|惯称|рефре́н)'
        wellKnownPartNames = r'([^\n]\n)(\n)?\[(( *[0-9]+ *)?' + wellKnownPartNames + r'[^\n]*)\]'
        partNameFix = lambda x: x.group(1) + '\n' + r'[' + x.group(3).casefold() + r']'
        lyrics = re.sub(wellKnownPartNames, partNameFix, lyrics, flags=re.IGNORECASE)
        lyrics = '\n' + lyrics.replace('\n\n', '\n\n\n') + '\n'
        repeatedLines = r'(\n[^\n]+)[\[(]\s*([Xx]\s*([1-9][0-9]*)|([1-9][0-9]*)\s*[Xx])\s*[)\]] *\n(.)?'
        lyrics = re.sub(repeatedLines, self._repeatedLine, lyrics, flags=re.MULTILINE)
        partsWithDescr = re.compile(r'\n(\[[\w\s:&,/+_-]+[\w\s+]\])\n(([^\n]+\n)+)\n', re.MULTILINE)
        parts = [(part[0], part[1]) for part in partsWithDescr.findall(lyrics)]
        for part in parts:
            lyrics = re.sub((re.escape(part[0]) + r'\n\n'), (part[1] + r'\n'), lyrics)
        return partsWithDescr.sub(r'\n\2\n', lyrics)

    def lyricsMadeTidy( self, lyrics ):
        horizontalSpace = r'[\t \u00A0\u1680\u2000-\u200A\u202F\u205F\u3000]'
        lyrics = re.sub((horizontalSpace + r'+'), r' ', lyrics)
        lyrics = re.sub(r'(\r+\n|\r*\n\r+|\u0085)', r'\n', lyrics, flags=re.MULTILINE)
        lyrics = lyrics.replace(r'\r', r'\n')
        lyrics = re.sub(r' (\n|$)', r'\1', lyrics, flags=re.MULTILINE)
        lyrics = re.sub(r'(^|\n) ', r'\1', lyrics, flags=re.MULTILINE)
        lyrics = re.sub(r'\n *[.*-_#~] *\n', r'\n\n', lyrics, flags=re.MULTILINE)
        lyrics = re.sub(r'(\[\w+( +\w+)?\])', lambda x: x.group(1).casefold(), lyrics)
        wellKnownMeta1 = r'\[(.*solo|intro.*|outro|instru.*|.*instrumental)\]'
        wellKnownMeta2 = r'\[(.*solo|instru.*|.*instrumental)\]'
        lyrics = re.sub((r'([^\n]\n)' + wellKnownMeta1), r'\1\n[\2]', lyrics, flags=re.IGNORECASE)
        lyrics = re.sub((wellKnownMeta2 + r'(\n[^\n])'), r'[\1]\n\2', lyrics, flags=re.IGNORECASE)
        lyrics = re.sub(r'\n.*https?://.*\n', r'\n', lyrics)
        lyrics = self._expandedLyrics(lyrics)
        lyrics = re.sub(r'\n\n+', r'\n\n', lyrics, flags=re.MULTILINE)
        return lyrics.strip()

    def process( self, album, metadata, track, release, action=False ):
        language = metadata.get(r'language', metadata.get(r'~releaselanguage', r'und')).strip().casefold()
        if (language not in iso639.languages.part3):
            language = self._fixedLanguage(language)
        if (language == r'und'):
            metadata.pop(r'language', None)
        else:
            metadata[r'language'] = language
            if (language == r'zxx'):
                metadata[r'lyrics'] = r'[instrumental]'
                metadata.pop(r'lyricist', None)
                return
        lyrics = metadata.get(r'lyrics', r'')
        nonstandardLyricsTags = []
        for key in metadata:
            if (re.match(r'^(.*\W)?lyrics\W.*$', key, flags=re.IGNORECASE)):
                if (not lyrics): lyrics = metadata[key]
                nonstandardLyricsTags += [key]
        for tagName in nonstandardLyricsTags: metadata.pop(tagName, None)
        if ((language != r'zxx') and (action or ((not lyrics) and config.setting[r'autoFetch']))):
            artist = metadata.get(r'artist', metadata.get(r'albumartist', None))
            if (not artist):
                artist = metadata.get(r'artistsort', metadata.get(r'albumartistsort', None))
            title = metadata.get(r'title', metadata.get(r'_recordingtitle', metadata.get(r'work', None)))
            fetchedLyrics = self.fetchLyrics(artist, title, language)
            if (len(fetchedLyrics)): lyrics = fetchedLyrics
        if (re.match(r'^\Winstrumental\W$', lyrics, flags=re.IGNORECASE)):
            metadata[r'lyrics'] = r'[instrumental]'
            metadata[r'language'] = r'zxx'
            metadata.pop(r'lyricist', None)
            return
        #if (not lyrics): lyrics = self._searchForOldLyrics(track)
        detectedLanguage = self._detectLanguage(lyrics)
        if ((language == r'und') or (detectedLanguage[1] > 0.9)):
            if (detectedLanguage[0] != r'und'): metadata[r'language'] = detectedLanguage[0]
        metadata[r'lyrics'] = self.lyricsMadeTidy(lyrics)

    def _finish( self, file, result=None, error=None ):
        if not error:
            self.tagger.window.set_statusbar_message(
                N_('Lyrics for "%(filename)s" successfully updated.'),
                {'filename': file.filename}
            )
        else:
            self.tagger.window.set_statusbar_message(
                N_('Could not update lyrics for "%(filename)s".'),
                {'filename': file.filename}
            )

    def processTrack( self, album, metadata, track, release ):
        for f in track.linked_files:
            thread.run_task(partial(self.process, album, metadata, track, release, False), partial(self._finish, f))

    def processFile( self, track, file ):
        thread.run_task(partial(self.process, None, file.metadata, track, None, False), partial(self._finish, file))

    def callback( self, objs ):
        for obj in objs:
            if (isinstance(obj, Track)):
                for f in obj.linked_files:
                    thread.run_task(partial(self.process, None, f.metadata, obj, None, True), partial(self._finish, f))
            elif (isinstance(obj, File)):
                thread.run_task(partial(self.process, None, obj.metadata, None, None, True), partial(self._finish, obj))



if (runningAsPlugin):

    class OmniLyricsOptionsPage( OptionsPage ):

        NAME = PLUGIN_NAME.casefold()
        TITLE = PLUGIN_NAME
        PARENT = r'tags' # r'plugins' ?

        options = [TextOption(r'setting', r'gcsAPIKey', r' '),
                   TextOption(r'setting', r'gcsEngineID', r' '),
                   BoolOption(r'setting', r'autoFetch', False)]

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
            self.autoFetch = QtWidgets.QCheckBox(self)
            self.autoFetch.setCheckable(True)
            self.autoFetch.setChecked(False)
            self.autoFetch.setText(r'Fetch lyrics from the web automatically after scanning')
            self.box.addWidget(self.autoFetch)
            self.spacer2 = QtWidgets.QSpacerItem(0, 0, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding)
            self.box.addItem(self.spacer2)
            self.spacer3 = QtWidgets.QSpacerItem(0, 0, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding)
            self.box.addItem(self.spacer3)

        def load( self ):
            self.apiKeyInput.setText(config.setting[r'gcsAPIKey'])
            self.idInput.setText(config.setting[r'gcsEngineID'])
            self.autoFetch.setChecked(config.setting[r'autoFetch'])

        def save( self ):
            config.setting[r'gcsAPIKey'] = self.apiKeyInput.text()
            config.setting[r'gcsEngineID'] = self.idInput.text()
            config.setting[r'autoFetch'] = self.autoFetch.isChecked()



    register_file_action(OmniLyrics())
    register_file_post_addition_to_track_processor(OmniLyrics().processFile, priority=PluginPriority.LOW)
    # register_track_action(OmniLyrics())
    # register_track_metadata_processor(OmniLyrics().processTrack, priority=PluginPriority.LOW)
    register_options_page(OmniLyricsOptionsPage)



else:

    omnilyrics = OmniLyrics()
    lyrics = r''
    if (len(argv) == 4): lyrics = omnilyrics.fetchLyrics(argv[-3], argv[-2], argv[-1])
    elif (len(argv) == 3): lyrics = omnilyrics.fetchLyrics(argv[-2], argv[-1], r'und')
    else: print("Usage: python3 '" + argv[0] + "' ARTIST TITLE [LANGUAGE]")
    if (len(lyrics)): print(omnilyrics.lyricsMadeTidy(lyrics))
