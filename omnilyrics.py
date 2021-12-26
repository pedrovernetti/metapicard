
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
from urllib.parse import urlparse, quote as urlquote
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
PLUGIN_VERSION = '0.4'
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
    title = page.find_all(r'div', {r'class': r'cnt-head_title'}) if normTitle else None
    if (title):
        artist = title[0].find_all(r'h2') if normArtist else None
        title = title[0].find_all(r'h1')
        if (artist):
            artist = re.sub(r'\W', r'', unidecode(artist[0].get_text().casefold()))
            if (artist != normArtist): return None
        if (title):
            title = unidecode(title[0].get_text().casefold())
            if (re.sub(r'\W', r'', title) != normTitle): return None
    all_extracts = page.select(r'div[class*="cnt-letra"]')
    if (not all_extracts): return None
    lyrics = r''
    for extract in all_extracts:
        for br in extract.find_all(r'br'): br.replace_with('\n')
        for p in extract.find_all(r'p', recursive=False):
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
    title = page.find_all(r'h1') if normTitle else None
    if (title):
        title = re.sub(r'[^a-z0-9]', r'', title[0].get_text().casefold())
        if (title != normTitle): return None
    artistElementClass = r'header_with_cover_art-primary_info-primary_artist'
    artist = page.find_all(r'a', {r'class': artistElementClass}) if normArtist else None
    if (artist):
        artist = re.sub(r'[^a-z0-9]', r'', artist[0].get_text().replace(r'&', r'and').casefold())
        if (artist != normArtist): return None
    lyrics = _geniusScraperMethod1(page) or _geniusScraperMethod2(page)
    return lyrics

def _musixmatchScraper( page, normArtist, normTitle ):
    title = page.select(r'h1[class*="mxm-track-title__track"]') if normTitle else None
    if (title):
        for element in title[0].find_all(r'small'): element.clear()
        title = re.sub(r'[^a-z0-9]', r'', title[0].get_text().casefold())
        if (title != normTitle): return None
    artist = page.select(r'a[class*="mxm-track-title__artist"]') if normArtist else None
    if (artist):
        artist = re.sub(r'[^a-z0-9]', r'', artist[0].get_text().casefold())
        if (artist != normArtist): return None
    for script in page.find_all(r'script'): script.replace_with('\n')
    for garbage in page.select(r'div[class*="review-changes"]'): garbage.clear()
    extract = page.find_all(r'div', {r'class': r'mxm-lyrics'})
    if (not extract): return None
    problematic = re.compile(r'^lyrics__content__(error|warning)')
    if (extract[0].find_all(r'span', {r'class': problematic})):
        extract = extract[0].find_all(r'span', {r'class': None, r'id': None})
        if ((not extract) or (len(extract) < 2)): return None
        return extract[1].get_text().strip()
    else:
        extract = extract[0].select(r'p[class*="mxm-lyrics__content"]')
        if (not extract): return None
        return extract[0].get_text().strip()

def _aZLyricsScraper( page, normArtist, normTitle ):
    title = page.find_all(r'h1') if normTitle else None
    if (title):
        title = re.sub(r'[^a-z0-9]', r'', title[0].get_text()[1:-7].casefold())
        if (title != normTitle): return None
    artist = page.find_all(r'h2') if normArtist else None
    if (artist):
        artist = re.sub(r'[^a-z0-9]', r'', artist[0].get_text()[:-7].casefold())
        if (artist != normArtist): return None
    extract = page.find(r'div', {r'id': None, r'class': None})
    if (not extract): return None
    for br in extract.find_all(r'br'): br.replace_with('\n')
    return extract.get_text().replace('\n\n', '\n').strip()

def _lyricsModeScraper( page, normArtist, normTitle ):
    title = page.select(r'h1[class*=song_name]') if normTitle else None
    if (title):
        title = title[0].find_all(r'span')
        if (title):
            artist = re.sub(r'[^a-z0-9]', r'', title[0].get_text()[1:-7].casefold()) if normArtist else None
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
            title = re.sub(r'[^a-z0-9]', r'', artist[1].get_text().casefold()) if normTitle else None
            if (title != normTitle): return None
        artist = re.sub(r'[^a-z0-9]', r'', artist[0].get_text().casefold()) if normArtist else None
        if (artist != normArtist): return None
    extract = page.find(r'div', {r'id': r'lyrics'})
    if (not extract): return None
    for br in extract.find_all(r'br'): br.replace_with('\n')
    return extract.get_text().strip()

def _lyricsComScraper( page, normArtist, normTitle ):
    title = page.find_all(r'h1', {r'id': r'lyric-title-text'}) if normTitle else None
    if (title):
        title = re.sub(r'[^a-z0-9]', r'', title[0].get_text().casefold())
        if (title != normTitle): return None
    artist = page.find_all(r'h3', {r'class': r'lyric-artist'}) if normArtist else None
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
    title = page.find_all(r'h1') if normTitle else None
    if (title):
        title = re.sub(r'[^a-z0-9]', r'', title[0].get_text().casefold())
        if (title != normTitle): return None
    artist = page.find_all(r'h2') if normArtist else None
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
    title = page.find_all(r'h1') if (normArtist and normTitle) else None
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

def _darkLyricsScraper( page, normArtist, normTitle ):
    artist = page.find_all(r'h1') if (normArtist) else None
    if (artist):
        artist = re.sub(r'[^a-z0-9]', r'', artist[0].get_text()[:-7].casefold())
        if (artist != normArtist): return None
    songs = page.find_all(r'div', {r'class': r'lyrics'})
    if (not songs): return None
    songs = songs[0]
    for br in songs.find_all(r'br'): br.replace_with('\n')
    for a in songs.find_all(r'a'): a.replace_with_children()
    for h3 in songs.find_all(r'h3'):
        h3.string = r'##' + re.sub(r'[^a-z0-9]', r'', re.sub(r'^[0-9]+\.?\s*', r'', h3.get_text().casefold()))
    for div in songs.find_all(r'div'): div.clear()
    songs = re.sub('[\x00-\x09\x0B-\x1F\x7F\x80-\x9F]', r'', re.sub(r'\n\n', r'\n', songs.text))
    songs = '\n' + songs.rsplit('\n', 3)[0].strip() + '\n\n##END'
    lyrics = re.search((r'\n##\w*' + normTitle + r'\n((([^#][^\n]*)? *\n)+)'), songs, flags=re.MULTILINE)
    if (not lyrics): return None
    return lyrics[1].strip()

def _lyricsBellScraper( page, normArtist, normTitle ):
    title = page.find_all(r'h1') if (normArtist and normTitle) else None
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
    title = page.find_all(r'h1') if (normArtist and normTitle) else None
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
    title = page.find_all(r'h1') if (normArtist and normTitle) else None
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
    title = page.find_all(r'h1') if (normArtist and normTitle) else None
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
    artistURL = re.sub(r'[^\w\s/-]', r'', unidecode(artist.casefold())).replace(r'&', r'e')
    artistURL = r'https://www.letras.mus.br/' + re.sub(r'[\s/-]+', r'-', artistURL).strip(r'-') + r'/'
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

def _musixmatchURL( artist, title ):
    artist = re.sub(r'[^\w-]', r'', re.sub('[\s.!&()\[\]\x27-]+', r'-', artist).strip(r'-'))
    title = re.sub(r'[^\w-]', r'', re.sub('[\s.!&()\[\]\x27-]+', r'-', title).strip(r'-'))
    return (r'https://www.musixmatch.com/lyrics/' + artist + r'/' + title)

def _aZLyricsURL( artist, title ):
    artist = re.sub(r'\W+', r'', unidecode(artist.casefold()))
    title = re.sub(r'\W+', r'', unidecode(title.casefold()))
    return (r'https://www.azlyrics.com/lyrics/' + artist + r'/' + title + '.html')

def _lyricsModeURL( artist, title ):
    artist = re.sub(r'[^a-z0-9\s_-]+', r'', artist.upper().casefold())
    title = re.sub(r'[^a-z0-9\s_-]+', r'', title.upper().casefold())
    artist = re.sub(r'[\s_-]+', r'_', artist).strip(r'_')
    title = re.sub(r'[\s_-]+', r'_', title).strip(r'_')
    initial = artist[0] if (artist[0] in r'abcdefghijklmnopqrstuvwxyz') else r'0-9'
    return (r'https://www.lyricsmode.com/lyrics/' + initial + r'/' + artist + r'/' + title + r'.html')

def _vagalumeURL( artist, title ):
    artist = re.sub(r'\W+', r'-', unidecode(artist.casefold())).strip(r'-')
    title = re.sub(r'\W+', r'-', unidecode(title.casefold())).strip(r'-')
    return (r'https://www.vagalume.com.br/' + artist + r'/' + title + r'.html')

def _lyricsComURL( artist, title ):
    artistURL = urlquote(re.sub(r'\s+', r'-', artist.strip()))
    artistURL = r'https://www.lyrics.com/artist/' + artistURL
    try: artistPage = requests.get(artistURL, headers=OmniLyrics.headers)
    except: return None
    if (not artistPage): return None
    artistPage = BeautifulSoup(artistPage.content, r'lxml')
    songs = artistPage.find_all(r'a')
    if (not songs): return None
    songs = [songs[i] for i in range(len(songs)-1, -1, -1) if (songs[i].get(r'href', r'').startswith(r'/lyric/'))]
    title = re.sub(r'\W', r'', title.casefold())
    for song in songs:
        if (re.sub(r'\W', r'', song.get_text().casefold()).endswith(title)):
            return (r'https://www.lyrics.com' + song[r'href'])
    return None

def _lyricsManiaURL( artist, title ):
    artist = re.sub(r'\s+', r'_', unidecode(artist.casefold().replace(r'&', r'and')))
    artist = r'_' + re.sub(r'^the_(.*)$', r'\1_the', re.sub(r'[^\w_/]', r'', artist))
    title = re.sub(r'\s+', r'_', unidecode(title.casefold().replace(r'&', r'and')))
    title = re.sub(r'[^\w_/]', r'', title) + r'_lyrics'
    return (r'https://www.lyricsmania.com/' + title + artist + r'.html')

def _metroLyricsURL( artist, title ):
    artist = re.sub(r'\s+', r'-', re.sub(r'[^\w\s]', r'', unidecode(artist.casefold())))
    title = re.sub(r'\s+', r'-', re.sub(r'[^\w\s]', r'', unidecode(title.casefold())))
    return (r'https://www.metrolyrics.com/' + title.strip(r'-') + r'-' + artist.strip(r'-') + r'.html')

def _darkLyricsURL( artist, title ):
    artistURL = re.sub(r'[^a-z0-9]', r'', artist.casefold())
    initial = artistURL[0] if (artistURL[0] in r'abcdefghijklmnopqrstuvwxyz') else r'19'
    artistURL = r'http://www.darklyrics.com/' + initial + r'/' + artistURL + r'.html'
    try: artistPage = requests.get(artistURL, headers=OmniLyrics.headers)
    except: return None
    if (not artistPage): return None
    artistPage = BeautifulSoup(artistPage.content, r'lxml')
    albums = artistPage.find_all(r'div', {r'class': r'album'})
    title = re.sub(r'\W', r'', title.casefold())
    for album in albums:
        if (album.get_text().strip().casefold().startswith(r'album:')):
            for a in album.find_all(r'a'):
                if (re.sub(r'\W', r'', a.get_text().casefold()).endswith(title)):
                    return re.sub(r'#.*$', r'', (r'http://www.darklyrics.com/' + a[r'href'][3:]))
    return None



class OmniLyrics( BaseAction ):

    NAME = "Fetch/Update Lyrics"

    scrapers = { r'letras.mus':     _letrasScraper,
                 r'genius':         _geniusScraper,
                 r'musixmatch':     _musixmatchScraper,
                 r'azlyrics':       _aZLyricsScraper,
                 r'lyricsmode':     _lyricsModeScraper,
                 r'vagalume':       _vagalumeScraper,
                 r'www.lyrics.com': _lyricsComScraper,
                 r'lyricsmania':    _lyricsManiaScraper,
                 r'metrolyrics':    _metroLyricsScraper,
                 r'darklyrics':     _darkLyricsScraper,
                 r'lyricsbell':     _lyricsBellScraper,
                 r'lyricsted':      _lyricsTEDScraper,
                 r'lyricsoff':      _lyricsOffScraper,
                 r'lyricsmint':     _lyricsMINTScraper,
                 r'glamsham':       _glamShamScraper, }

    _autoURLS = [ _letrasURL, _geniusURL, _musixmatchURL, _aZLyricsURL, _lyricsModeURL,
                  _vagalumeURL, _lyricsComURL, _lyricsManiaURL, _metroLyricsURL, _darkLyricsURL ]

    validGCSLanguages = { r'ar', r'bg', r'ca', r'cs', r'da', r'de', r'el',
                          r'en', r'es', r'et', r'fi', r'fr', r'hr', r'hu',
                          r'id', r'is', r'it', r'iw', r'ja', r'ko', r'lt',
                          r'lv', r'nl', r'no', r'pl', r'pt', r'ro', r'ru',
                          r'sk', r'sl', r'sr', r'sv', r'tr', }

    headers = { r'User-Agent': r'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:88.0) Gecko/20100101 Firefox/88.0',
                r'Referer': r'https://www.google.com/',
                r'Accept': r'text/html,application/xhtml+xml', }

    def __init__( self ):
        super().__init__()
        if (not runningAsPlugin):
            self.gcsAPIKey = environ.get(r'GCS_API_KEY', None)
            self.gcsEngineID = environ.get(r'GCS_ENGINE_ID', None)
        self.requestFailureHistory = {}

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
        if (not (self.gcsAPIKey and self.gcsEngineID)): return None
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
        lyrics = None
        for domain, scraper in self.scrapers.items():
            if (domain in lyricsURL): lyrics = scraper(page, normArtist, normTitle)
            if (lyrics): return lyrics
        return None # no scraper available for this search result

    def fetchLyricsFrom( self, url ):
        if (not runningAsPlugin):
            supportedSite = False
            netloc = urlparse(url).netloc
            for domain, _ in self.scrapers.items():
                if (domain in netloc): supportedSite = True
            if (not supportedSite):
                print(r'"' + netloc + r'" not supported')
                return None
        return self._lyrics(url, None, None)

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

    def _directFetchingLoop( self, urlRecipes, artist, title, language ):
        normArtist = re.sub(r'[^a-z0-9]', r'', artist.casefold().replace(r'&', r'and'))
        normTitle = re.sub(r'[^a-z0-9]', r'', title.casefold())
        for urlRecipe in urlRecipes:
            url = urlRecipe(artist, title)
            if (not ((type(url) == str) and len(url))): continue
            lyrics = self._lyrics(url, normArtist, normTitle)
            if (lyrics):
                if (not runningAsPlugin):
                    print('Lyrics for "' + title + '" fetched from ' + url + '\n')
                return lyrics
            print(url, r' failed')
        return None

    def _fetchDirectly( self, artist, title, language ):
        urlRecipes = self._autoURLS
        shuffle(urlRecipes)
        lyrics = self._directFetchingLoop(urlRecipes, artist, title, language)
        if ((not lyrics) and re.match(r'^.*\(.*\)\s*$', title)):
            title = re.sub(r'\s*\(.*\)\s*$', r'', title)
            lyrics = self._directFetchingLoop(urlRecipes, artist, title, language)
        return lyrics

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

    def _multiplier( self, x ):
        previousChar = x.group(1)
        num = x.group(3) if (not x.group(4)) else x.group(4)
        end = x.group(5)
        if (previousChar): return (previousChar + r' x' + num + '\n')
        else: return (r'x' + num + end)

    def _repeatedLine( self, x ):
        line = x.group(1)
        nextChar = x.group(3)
        if (not nextChar): nextChar = r''
        times = x.group(2)
        if (re.match(r'^\n *\[[^\n\]]+\] *$', line)):
            line += '\n'
            if (re.match(r'\w$', nextChar)): return ((line * int(times)) + nextChar)
        return ((line * int(times)) + '\n' + nextChar)

    def _repeatedPart( self, x ):
        beg = x.group(1)
        if (beg != '\n\n'): beg = '\n' + beg
        part = '\n' + beg + x.group(2) + '\n'
        times = x.group(4)
        return ((part * int(times)) + '\n')

    def _expandedLyrics( self, lyrics ):
        lyrics = '\n\n' + lyrics + '\n\n'
        wellKnownPartNames = r'(vers|stro|(pr\w\W?|p\wst?\W?)?chor|refr|estribillo|ritornello|'
        wellKnownPartNames += r'リフレイ|후렴|英語|惯称|рефре́н)'
        wellKnownPartNames = r'([^\n]\n|^)(\n*)?\[(( *[0-9]+ *)?' + wellKnownPartNames + r'[^\]\n]*)\] *'
        partNameFix = lambda x: x.group(1) + '\n' + r'[' + re.sub(r'\W', r'', x.group(3).casefold()) + r']'
        lyrics = re.sub(wellKnownPartNames, partNameFix, lyrics, flags=re.IGNORECASE)
        bridge = r'\[\W*(bridge|p(o|ue)nte?|브리지|бриджа?|köprü)\W*\] *\n'
        if (not re.findall((bridge + r' *\n'), lyrics, flags=re.IGNORECASE)):
            lyrics = re.sub((r'\n *' + bridge), r'\n\n', lyrics, flags=re.IGNORECASE)
        lyrics = '\n' + lyrics.replace('\n\n', '\n\n\n') + '\n'
        multiplier = r'([^\s\[(])? *[\[(]? *([Xx] *([1-9][0-9]*)|([1-9][0-9]*) *[Xx]) *[\])]? *(\n|$)'
        lyrics = re.sub(multiplier, self._multiplier, lyrics)
        repeatedLines = r'(\n[^\n]+?) x([1-9][0-9]*)\n(.)?'
        lyrics = re.sub(repeatedLines, self._repeatedLine, lyrics, flags=re.MULTILINE)
        repeatedParts = r'(\n\n|^\n?|\[[^\]\n]+\]\n)(([^\n]+\n)+)x([1-9][0-9]*)\n'
        lyrics = re.sub(repeatedParts, self._repeatedPart, lyrics, flags=re.MULTILINE)
        partsWithDescr = re.compile(r'\n(\[[\w\s:&,/+_-]+[\w\s+]\])\n(([^\n]+\n)+)\n', re.MULTILINE)
        parts = [(part[0], part[1]) for part in partsWithDescr.findall(lyrics)]
        for part in parts:
            escaped = re.escape(part[0]).replace(r'\[', r'\[(repeat\W*)?', 1) + r'\n\n'
            lyrics = re.sub(escaped, (part[1] + r'\n'), lyrics)
        return partsWithDescr.sub(r'\n\2\n', lyrics)

    def lyricsMadeTidy( self, lyrics ):
        lyrics = re.sub(r'["ˮ“”‟❝❞＂]', r'"', re.sub(r'[´`’ʼʹʻʽˈˊʹ՚᾽᾿‘‛′‵＇]', "'", lyrics))
        lyrics = re.sub('[‐‑֊־﹣⁃\u1806]', r'-', lyrics).replace(r'…', r'...')
        horizontalSpace = r'[\t \u00A0\u1680\u2000-\u200A\u202F\u205F\u3000]'
        lyrics = re.sub((horizontalSpace + r'+'), r' ', lyrics)
        lyrics = re.sub(r'(\r+\n|\r*\n\r+|\u0085)', r'\n', lyrics, flags=re.MULTILINE)
        lyrics = lyrics.replace(r'\r', r'\n')
        lyrics = re.sub(r' (\n|$)', r'\1', lyrics, flags=re.MULTILINE)
        lyrics = re.sub(r'(^|\n) ', r'\1', lyrics, flags=re.MULTILINE)
        lyrics = re.sub(r'\n *[.*-_#~] *\n', r'\n\n', lyrics, flags=re.MULTILINE)
        lyrics = re.sub(r'(\[\w+( +\w+)?\])', lambda x: x.group(1).casefold(), lyrics)
        flagsIM = re.IGNORECASE | re.MULTILINE
        wellKnownDumbMeta = re.compile(r'(^|\n)[^\w\[]*(chorus|verse( [0-9]+\W*)?)[^\w\]\n]*', flagsIM)
        lyrics = wellKnownDumbMeta.sub(r'\n\1[\2]', lyrics)
        wellKnownMeta1 = r'\[(.*solo|intro.*|outro|instru.*|.*instrumental)\]'
        wellKnownMeta2 = r'\[(.*solo|instru.*|.*instrumental)\]'
        lyrics = re.sub((r'([^\n]\n)' + wellKnownMeta1), r'\1\n[\2]', lyrics, flags=flagsIM)
        lyrics = re.sub((wellKnownMeta2 + r'(\n[^\n])'), r'[\1]\n\2', lyrics, flags=flagsIM)
        lyrics = re.sub(r'(^|\n)[^\n]*https?://[^\n]*($|\n)', r'\n', lyrics, flags=flagsIM)
        lyrics = re.sub(r'^\s*\[?produ\w+ (by|p\wr|von|a[fv]).*($|\n)', r'\n', lyrics, flags=flagsIM)
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
                lyrics = metadata.get(r'lyrics', r'').strip()
                if ((not lyrics) or (re.sub(r'\W', r'', unidecode(lyrics.casefold())) == r'instrumental')):
                    metadata[r'lyrics'] = r'[instrumental]'
                metadata.pop(r'lyricist', None)
                return
        lyrics = metadata.get(r'lyrics', r'').strip()
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
        if (re.sub(r'\W', r'', unidecode(lyrics.casefold())) == r'instrumental'):
            metadata[r'lyrics'] = r'[instrumental]'
            metadata[r'language'] = r'zxx'
            metadata.pop(r'lyricist', None)
            return
        #if (not lyrics): lyrics = self._searchForOldLyrics(track)
        lyrics = self.lyricsMadeTidy(lyrics)
        detectedLanguage = self._detectLanguage(lyrics)
        if ((language == r'und') or (detectedLanguage[1] > 0.9)):
            if (detectedLanguage[0] != r'und'): metadata[r'language'] = detectedLanguage[0]
        metadata[r'lyrics'] = lyrics

    def _finish( self, file, result=None, error=None ):
        if not error:
            self.tagger.window.set_statusbar_message(
                N_('Lyrics for "%(filename)s" successfully fetched/updated.'),
                {'filename': re.sub(r'^.*/', r'', file.filename)}
            )
        else:
            self.tagger.window.set_statusbar_message(
                N_('Could not fetch/update lyrics for "%(filename)s".'),
                {'filename': re.sub(r'^.*/', r'', file.filename)}
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

        options = [TextOption(r'setting', r'gcsAPIKey', r''),
                   TextOption(r'setting', r'gcsEngineID', r''),
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
    url = re.compile(r'^(https?://|www\.)[\w.-]+/.*$', re.IGNORECASE)
    if ((len(argv) == 2) and (url.match(argv[-1]))): lyrics = omnilyrics.fetchLyricsFrom(argv[-1])
    elif (len(argv) == 4): lyrics = omnilyrics.fetchLyrics(argv[-3], argv[-2], argv[-1])
    elif (len(argv) == 3): lyrics = omnilyrics.fetchLyrics(argv[-2], argv[-1], r'und')
    else: print("Usage: python3 '" + argv[0] + "' ARTIST TITLE [LANGUAGE]")
    if (lyrics): print(omnilyrics.lyricsMadeTidy(lyrics))
