
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
# Name: Origins Oblivion
# Description: MusicBrainz Picard plugin to automatically move non-standard tags' values to
#              their equivalent standard tags
#
# #  In order to have this plugin working (if it is currently not), place it at:
#    ~/.config/MusicBrainz/Picard/plugins
# =============================================================================================

import re



PLUGIN_NAME = 'AutoMapper'
PLUGIN_AUTHOR = 'Pedro Vernetti G.'
PLUGIN_DESCRIPTION = 'Automatically moves content from non-standard tags to their standard equivalents.'
PLUGIN_VERSION = '0.1'
PLUGIN_API_VERSIONS = ['2.0', '2.1', '2.2', '2.3', '2.4', '2.5', '2.6']
PLUGIN_LICENSE = 'GPLv3'
PLUGIN_LICENSE_URL = 'https://www.gnu.org/licenses/gpl-3.0.en.html'

from PyQt5 import QtWidgets
from picard.config import BoolOption
from picard import config, log
from picard.file import File, register_file_post_addition_to_track_processor, register_file_post_load_processor
from picard.metadata import register_track_metadata_processor
from picard.plugin import PluginPriority
from picard.track import Track
from picard.ui.options import OptionsPage, register_options_page



class AutoMapper():

    _standardKeys = { r'writer', r'work', r'website', r'titlesort', r'title', r'tracknumber',
                      r'totaltracks', r'totaldiscs', r'subtitle', r'showmovement', r'showsort',
                      r'show', r'script', r'replaygain_track_range', r'replaygain_track_peak',
                      r'replaygain_track_gain', r'replaygain_reference_loudness', r'mixer',
                      r'replaygain_album_range', r'replaygain_album_peak', r'replaygain_album_gain',
                      r'remixer', r'releasetype', r'releasestatus', r'date', r'releasecountry',
                      r'label', r'_rating', r'producer', r'podcasturl', r'podcast', r'originalyear',
                      r'originaldate', r'originalfilename', r'originalartist', r'originalalbum',
                      r'musicip_puid', r'musicip_fingerprint', r'musicbrainz_workid', r'mood',
                      r'musicbrainz_trmid', r'musicbrainz_trackid', r'musicbrainz_albumid',
                      r'musicbrainz_releasegroupid', r'musicbrainz_albumartistid', r'movement',
                      r'musicbrainz_recordingid', r'musicbrainz_originalalbumid', r'movementnumber',
                      r'musicbrainz_originalartistid', r'musicbrainz_discid', r'musicbrainz_artistid',
                      r'movementtotal', r'djmixer', r'media', r'lyricist', r'license', r'language',
                      r'isrc', r'key', r'grouping', r'genre', r'gapless', r'engineer', r'encodedby',
                      r'encodersettings', r'discsubtitle', r'discnumber', r'director', r'copyright',
                      r'conductor', r'composersort', r'composer', r'compilation', r'catalognumber',
                      r'bpm', r'barcode', r'asin', r'artists', r'artistsort', r'artist', r'arranger',
                      r'albumsort', r'albumartistsort', r'albumartist', r'album', r'acoustid_id',
                      r'acoustid_fingerprint', r'lyrics', r'discid', }

    _mapping = { r'iwri': r'writer', r'wrk': r'work', r'woar': r'website', r'url': r'website',
                 r'authorurl': r'website', r'weblink': r'website', r'homepage': r'website',
                 r'titlesortorder': r'titlesort', r'sonm': r'titlesort', r'tsot': r'titlesort',
                 r'tit2': r'title', r'nam': r'title', r'inam': r'title', r'scale': r'key',
                 r'tracktotal': r'totaltracks', r'tracks': r'totaltracks', r'discs': r'totaldiscs',
                 r'totaldisks': r'totaldiscs', r'disks': r'totaldiscs', r'disctotal': r'totaldiscs',
                 r'disktotal': r'totaldiscs', r'tit3': r'subtitle', r'shwm': r'showmovement',
                 r'sosn': r'showsort', r'tvsh': r'show', r'tvshow': r'show', r'tpe4': r'remixer',
                 r'tvshowsort': r'showsort', r'modifiedby': r'remixer', r'remixartist': r'remixer',
                 r'remixedby': r'remixer', r'mixartist': r'remixer', r'albumtype': r'releasetype',
                 r'musicbrainzalbumtype': r'releasetype', r'musicbrainzreleasetype': r'releasetype',
                 r'albumstatus': r'releasestatus', r'musicbrainzalbumstatus': r'releasestatus',
                 r'musicbrainzreleasestatus': r'releasestatus', r'country': r'releasecountry',
                 r'albumreleasecountry': r'releasecountry', r'albumcountry': r'releasecountry',
                 r'musicbrainzalbumreleasecountry': r'releasecountry', r'icnt': r'releasecountry',
                 r'publisher': r'label', r'tpub': r'label', r'distributedby': r'label',
                 r'distributor': r'label', r'corporation': r'label', r'organization': r'label',
                 r'company': r'label', r'recordlabel': r'label', r'recordcompany': r'label',
                 r'rating': r'_rating', r'shareduserrating': r'_rating', r'userrating': r'_rating',
                 r'popm': r'_rating', r'popularity': r'rating', r'score': r'_rating',
                 r'ipro': r'producer', r'tiplproducer': r'producer', r'iplsproducer': r'producer',
                 r'producedby': r'producer', r'writtenby': r'writer', r'purl': r'podcasturl',
                 r'podcastlink': r'podcasturl', r'podcastwebsite': r'podcasturl', r'icmt': r'comment',
                 r'podcasthomepage': r'podcasturl', r'podcasthome': r'podcasturl',
                 r'pcst': r'podcast', r'podcastname': r'podcast', r'podcasttitle': r'podcast',
                 r'tofn': r'originalfilename', r'originalfile': r'originalfilename',
                 r'originalfilepath': r'originalfilename', r'originalpath': r'originalfilename',
                 r'tope': r'originalartist', r'originalperformer': r'originalartist',
                 r'originalalbumtitle': r'originalalbum', r'originalalbumname': r'originalalbum',
                 r'toal': r'originalalbum', r'mvi': r'movementnumber', r'mvc': r'movementtotal',
                 r'movementnum': r'movementnumber', r'totalmovements': r'movementtotal',
                 r'totalmovement': r'movementtotal', r'movements': r'movementtotal',
                 r'movementcount': r'movementtotal', r'trackcount': r'totaltracks',
                 r'disccount': r'totaldiscs', r'diskcount': r'totaldiscs', r'mvnm': r'movement',
                 r'movementname': r'movement', r'movementtitle': r'movement', r'mvn': r'movement',
                 r'tmoo': r'mood', r'mixedby': r'mixer', r'tiplmix': r'mixer', r'dj': r'djmixer',
                 r'iplsmix': r'mixer', r'tipldjmix': r'djmixer', r'iplsdjmix': r'djmixer',
                 r'tmed': r'media', r'imed': r'media', r'releaseformat': r'media',
                 r'albumformat': r'media', r'physicalformat': r'media', r'medium': r'media',
                 r'physicalmedium': r'media', r'releasemedia': r'media', r'releaseformat': r'media',
                 r'releasemedium': r'media', r'lyr': r'lyrics', r'lyrist': r'lyricist',
                 r'lyricsartist': r'lyricist', r'wcop': r'license', r'licenseurl': r'license',
                 r'ilng': r'language', r'tlan': r'language', r'lang': r'language', r'tsrc': r'isrc',
                 r'initialkey': r'key', r'tkey': r'key', r'songkey': r'key', r'grp': r'grouping',
                 r'grp1': r'grouping', r'tit1grp1': r'grouping', r'groupdescription': r'grouping',
                 r'contentgroupdescription': r'grouping', r'contentgroup': r'grouping',
                 r'group': r'grouping', r'ignr': r'genre', r'commdescription': r'comment',
                 r'songgenre': r'genre', r'gen': r'genre', r'tcon': r'genre', r'category': r'genre',
                 r'musicgenre': r'genre', r'musiccategory': r'genre', r'pgap': r'gapless',
                 r'itunpgap': r'gapless', r'ieng': r'engineer', r'tiplengineer': r'engineer',
                 r'iplsengineer': r'engineer', r'recordingengineer': r'engineer',
                 r'audioengineer': r'engineer', r'soundengineer': r'engineer', r'tbpm': r'bpm',
                 r'tsse': r'encodersettings', r'encodingsettings': r'encodersettings',
                 r'codecsettings': r'encodersettings', r'encodingparams': r'encodersettings',
                 r'encodingparameters': r'encodersettings', r'encoderparams': r'encodersettings',
                 r'encoderparameters': r'encodersettings', r'codecparams': r'encodersettings',
                 r'encoderparameters': r'encodersettings', r'software': r'encodedby',
                 r'encoder': r'encodedby', r'tenc': r'encodedby', r'too': r'encodedby',
                 r'ienc': r'encodedby', r'source': r'encodedby', r'ripped': r'encodedby',
                 r'rippedby': r'encodedby', r'generatedby': r'encodedby', r'tsst': r'discsubtitle',
                 r'disksubtitle': r'discsubtitle', r'disks': r'totaldiscs', r'dir': r'director',
                 r'disktitle': r'discsubtitle', r'disctitle': r'discsubtitle', r'tpe3': r'conductor',
                 r'setsubtitle': r'discsubtitle', r'settitle': r'discsubtitle', r'imus': r'composer',
                 r'directedby': r'director', r'copyrights': r'copyright', r'copy': r'copyright',
                 r'tcop': r'copyright', r'cprt': r'copyright', r'icop': r'copyright',
                 r'conductedby': r'conductor', r'conduction': r'conductor', r'soco': r'composersort',
                 r'tsoc': r'composersort', r'composersortorder': r'composersort', r'wrt': r'composer',
                 r'tcom': r'composer', r'iscompilation': r'compilation', r'cpil': r'compilation',
                 r'tcmp': r'compilation', r'catalogno': r'catalognumber', r'tempo': r'bpm',
                 r'catalogn': r'catalognumber', r'beatsperminute': r'bpm', r'tmpo': r'bpm',
                 r'artistslist': r'artists', r'tsop': r'artistsort', r'soar': r'artistsort',
                 r'artistsortorder': r'artistsort', r'iart': r'artist', r'tpe1': r'artist',
                 r'arrangedby': r'arranger', r'tiplarranger': r'arranger', r'tsoa': r'albumsort',
                 r'iplsarranger': r'arranger', r'soal': r'albumsort', r'albumsortorder': r'albumsort',
                 r'albumartistsortorder': r'albumartistsort', r'soaa': r'albumartistsort',
                 r'tso2': r'albumartistsort', r'aart': r'albumartist', r'tpe2': r'albumartist',
                 r'albumartist': r'albumartist', r'iprd': r'album', r'albumtitle': r'album',
                 r'albumname': r'album', r'alb': r'album', r'talb': r'album', r'set': r'album',
                 r'settitle': r'album', r'setname': r'album', r'release': r'album',
                 r'releasename': r'album', r'releasetitle': r'album', r'comment': r'comment',
                 r'cmt': r'comment', r'description': r'comment', r'info': r'comment',
                 r'note': r'comment', r'annotation': r'comment', r'comm': r'comment',
                 r'uslt': r'lyrics', r'usltlyrics': r'lyrics', r'usltdescription': r'lyrics',
                 r'usltlanguage': r'language', r'usltlang': r'language', r'mixdj': r'djmixer',
                 r'originalreleaseyear': r'originalyear', r'tory': r'originalyear',
                 r'tdor': r'originaldate', r'originalreleasedate': r'originaldate',
                 r'year': r'date', r'releaseyear': r'date', r'releasedate': r'date',
                 r'day': r'date', r'releaseday': r'date', r'releasetime': r'date',
                 r'datetime': r'date', r'icrd': 'date', r'tdrc': r'date', r'tyer': r'date',
                 r'musicmagicfingerprint': r'musicip_fingerprint', r'art': r'artist',
                 r'musicipfingerprint': r'musicip_fingerprint', r'fingerprint': r'musicip_fingerprint',
                 r'musicbrainzworkid': r'musicbrainz_workid', r'musicbrainztrmid': r'musicbrainz_trmid',
                 r'musicbrainzrecordingid': r'musicbrainz_recordingid', r'toly': r'lyricist',
                 r'musicbrainztrackid': r'musicbrainz_trackid', r'musicbrainzalbumid': r'musicbrainz_albumid',
                 r'musicbrainzreleasetrackid': r'musicbrainz_trackid', r'acoustid': r'acoustid_id',
                 r'musicbrainzalbumartistid': r'musicbrainz_albumartistid', r'acoustidid': r'acoustid_id',
                 r'musicbrainzoriginalartistid': r'musicbrainz_originalartistid', r'notes': r'comment',
                 r'musicbrainzdiscid': r'musicbrainz_discid', r'musicbrainzartistid': r'musicbrainz_artistid',
                 r'musicbrainzreleasegroupid': r'musicbrainz_releasegroupid', r'sourcefmt': r'media',
                 r'acoustidfingerprint': r'acoustid_fingerprint', r'commentid3v1': r'comment',
                 r'commentid3v1comment': r'comment', r'id3v1comment': r'comment', r'source': r'media',
                 r'publishingcompany': r'label', r'style': r'genre', r'id3v1genre': r'genre',
                 r'musicalstyle': r'genre', r'substyle': r'genre', r'subcategory': r'genre',
                 r'musicstyle': r'genre', r'kind': r'genre', r'musicalscene': r'genre', r'scene': r'genre',
                 r'musicscene': r'genre', r'vibe': r'mood', r'musicalvibe': r'mood', r'www': r'website',
                 r'musicvibe': r'mood', r'classification': r'_rating', r'diskid': r'discid',
                 r'origdate': r'originaldate', r'origtime': r'originaldate', r'keysignature': r'key',
                 r'keysig': r'key', r'retaildate': r'date', r'sourceid': r'discid', r'tdat': r'date',
                 r'ensemble': r'artist', r'name': r'title', r'catalog': r'catalognumber', }

    _splitfulMapping = { r'trkn':       (r'tracknumber', r'totaltracks'),
                         r'trck':       (r'tracknumber', r'totaltracks'),
                         r'track':      (r'tracknumber', r'totaltracks'),
                         r'itrk':       (r'tracknumber', r'totaltracks'),
                         r'trackno':    (r'tracknumber', r'totaltracks'),
                         r'tpos':       (r'discnumber',  r'totaldiscs'),
                         r'disc':       (r'discnumber',  r'totaldiscs'),
                         r'disk':       (r'discnumber',  r'totaldiscs'),
                         r'discno':     (r'discnumber',  r'totaldiscs'),
                         r'diskno':     (r'discnumber',  r'totaldiscs'),
                         r'partofset':  (r'discnumber',  r'totaldiscs'),
                         r'mvin':       (r'movementnumber', r'movementtotal'), }


    def __init__( self ):
        super().__init__()

    def _list( self, value ):
        if (type(value) == list): return value
        else: return [value]

    def _moveTagValue( self, value, to, metadata, toBeCreated ):
        value = re.sub(r'\s+', r' ', value.strip())
        if (not metadata.get(to, r'')):
            toBeCreated[to] = self._list(value)
        elif (value not in metadata[to]):
            if (type(metadata[to]) == list):
                metadata[to] += self._list(value)
            else:
                metadata[to] = [metadata[to]] + self._list(value)

    def _moveSplittableTag( self, value, to, metadata, toBeCreated ):
        pattern = re.compile(r'^\W*([0-9]+)(\W([0-9]+))?\W*$')
        value1 = pattern.search(value).group(1)
        value2 = pattern.search(value).group(3)
        self._moveTagValue(value1, to[0], metadata, toBeCreated)
        if (not tag2): return
        self._moveTagValue(value2, to[1], metadata, toBeCreated)

    def _mapLyrics( self, metadata, toBeDeleted ):
        foundLyrics = metadata.get(r'lyrics', r'')
        foundLyrics = [] if (not foundLyrics) else [foundLyrics]
        for key in metadata:
            if (re.match(r'^(.*\W)?lyrics\W.*$', key, flags=re.IGNORECASE)):
                if (len(metadata[key])): foundLyrics += [metadata[key]]
                toBeDeleted += [key]
        if (foundLyrics): metadata[r'lyrics'] = sorted(foundLyrics, key=len, reverse=True)[0]

    def process( self, album, metadata, track, release, f=None ):
        toBeDeleted = []
        toBeCreated = {}
        for key in metadata:
            if (key in self._standardKeys): continue
            normkey = re.sub(r'[^\w_]', r'', re.sub(r'[\s:/_-]+', r'_', key.casefold()))
            normkey = re.sub(r'^\W*(wm|txxx|((com\W*)?apple\W*)?itunes|lastfm)\W*', r'', normkey)
            if (normkey in self._standardKeys):
                toBeDeleted += [key]
                self._moveTagValue(metadata[key], normkey, metadata, toBeCreated)
            else:
                normkey = re.sub(r'[_~]', r'', normkey)
                if (normkey in self._splitfulMapping):
                    toBeDeleted += [key]
                    self._moveSplittableTag(metadata[key], key, self._splitfulMapping[normkey], metadata, toBeCreated)
                standardTag = self._mapping.get(normkey, r'')
                if ((not standardTag) and (normkey in self._standardKeys)): standardTag = normkey
                if ((len(standardTag)) and (standardTag != key)):
                    toBeDeleted += [key]
                    self._moveTagValue(metadata[key], standardTag, metadata, toBeCreated)
        self._mapLyrics(metadata, toBeDeleted)
        for tagName, value in toBeCreated.items(): metadata[tagName] = value
        if (config.setting[r'purgeUnmapped']):
            toBeDeleted = []
            for tagName in metadata:
                if (tagName not in self._standardKeys): toBeDeleted += [tagName]
        for tagName in toBeDeleted: metadata.pop(tagName, None)

    def processFile( self, track, file ):
        self.process(None, file.metadata, track, None, file)

    def processFileOnLoad( self, file ):
        self.process(None, file.metadata, None, None, file)



class AutoMapperOptionsPage( OptionsPage ):

    NAME = PLUGIN_NAME.casefold()
    TITLE = r'Non-standard Tags Mapping'
    PARENT = r'tags' # r'plugins' ?

    options = [ BoolOption(r'setting', r'purgeUnmapped', False) ]

    def __init__( self, parent=None ):
        super().__init__(parent)
        self.box = QtWidgets.QVBoxLayout(self)
        self.purgeUnmapped = QtWidgets.QCheckBox(self)
        self.purgeUnmapped.setCheckable(True)
        self.purgeUnmapped.setChecked(False)
        self.purgeUnmapped.setText(r'Purge non-standard tags left unmapped')
        self.box.addWidget(self.purgeUnmapped)
        self.spacer = QtWidgets.QSpacerItem(0, 0, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding)
        self.box.addItem(self.spacer)

    def load( self ):
        self.purgeUnmapped.setChecked(config.setting[r'purgeUnmapped'])

    def save( self ):
        config.setting[r'purgeUnmapped'] = self.purgeUnmapped.isChecked()



register_file_post_addition_to_track_processor(AutoMapper().processFile, priority=PluginPriority.HIGH)
register_file_post_load_processor(AutoMapper().processFileOnLoad, priority=110)
# register_track_metadata_processor(AutoMapper().process)
register_options_page(AutoMapperOptionsPage)
