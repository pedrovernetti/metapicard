
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
# Description: MusicBrainz Picard plugin to purge encoding-related and software-specific tags
#
# #  In order to have this plugin working (if it is currently not), place it at:
#    ~/.config/MusicBrainz/Picard/plugins
# =============================================================================================

import re



PLUGIN_NAME = 'Origins Oblivion'
PLUGIN_AUTHOR = 'Pedro Vernetti G.'
PLUGIN_DESCRIPTION = 'Purges most/all encoding-related and software-specific tags.'
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
from picard.ui.itemviews import BaseAction, register_file_action, register_track_action
from picard.ui.options import OptionsPage, register_options_page



class OriginsOblivion( BaseAction ):

    NAME = "Purge Encoding/Software-Specific Tags"

    _defaultTargets = { r'encodersettings', r'encodedby', r'ripped', r'rippedby', r'settings',
                        r'software', r'encoder', r'encodingparams', r'compatiblebrands',
                        r'majorbrand', r'minorversion', r'ver', r'tlen', r'musicbrainztrmid',
                        r'originalfilename', r'encodingtime', r'length', r'tsse', r'ienc',
                        r'generatedby', r'too', r'tenc', r'encoder', r'encodingparameters',
                        r'encoderparams', r'encoderparameters', r'codec', r'codecparams', r'tdly',
                        r'codecparameters', r'codecsettings', r'encodingsettings', r'tdtg', r'tden',
                        r'priv', r'itunnorm', r'tool', r'toolname', r'encodingtool', r'createdwith',
                        r'encodedwith', r'commentitunnorm', r'cddb', r'cddb1', r'taggingtime',
                        r'taggingdate', r'tagdate', r'rippingtool', r'ripdate', r'rippingdate',
                        r'cdtoc', r'commentcdtoc', r'id3v2privhttpwwwcdtagcom', r'cdtag',
                        r'privhttpwwwcdtagcom', r'httpwwwcdtagcom', r'wwwcdtagcom', r'cdtagcom',
                        r'toolver', r'toolversion', r'encoderversion', r'codecversion', r'ripper',
                        r'ripperversion', r'rippersoftware', r'ripperver', r'codecver', r'encoderver',
                        r'softwareversion', r'softwarever', r'encodingtoolversion', r'enctool',
                        r'enctoolversion', r'enctoolver', r'encodingtoolver', r'encodingsoftwarever',
                        r'encodingsoftwareversion', r'cddcids', r'cddbid', r'encodinghistory',
                        r'codinghistory', r'originator', r'origreference', r'origtime',
                        r'timereference', r'origdate', }

    _mbidTargets =    { r'musicbrainz_workid', r'musicbrainz_discid', r'musicbrainz_releasegroupid',
                        r'musicbrainz_albumartistid', r'musicbrainz_recordingid',
                        r'musicbrainz_originalalbumid', r'musicbrainz_originalartistid',
                        r'musicbrainz_artistid', }

    _iTunesTargets =  { r'gapless', r'itunsmpb', r'itunpgap', r'itunnorm', r'compilation', r'cpil',
                        r'iscompilation', r'tcmp', }

    _lastfmTargets =  { r'grouping', r'albumgrouping', r'albumgenre', }

    _knownSoftware =  r'exactaudiocopy|easy\W*cd\W*da|eac\W*flac|audiograbber|vsdc|'
    _knownComments =  _knownSoftware + r'visit\W|download|((https?://)?www\.[\w-]+|https?://[\w.-]+)\.[a-zA-Z]{2,3}'
    _commentTargets = re.compile(r'^([ 0-9A-F]+|\W*(ripped|encoded|' + _knownComments + ').*)$', re.IGNORECASE)

    def __init__( self ):
        super().__init__()

    def process( self, album, metadata, track, release ):
        toBeDeleted = []
        for key in metadata:
            normkey = re.sub(r'[^\w_]', r'', re.sub(r'[\s:/_-]+', r'_', key.casefold()))
            normkey = re.sub(r'^\W*(txxx\W*)?(.+)\W$', r'\2', normkey)
            if ((config.setting[r'purgeMBIDs'] and (normkey in self._mbidTargets)) or
                (config.setting[r'purgeiTunes'] and normkey.startswith(r'itun')) or
                (config.setting[r'purgeMusicIP'] and normkey.startswith(r'musicip')) or
                (config.setting[r'purgeLastFM'] and re.match(r'^\W*last\W?fm', normkey)) or
                (config.setting[r'purgeAcoustID'] and re.match(r'^\W*acoust\W?id', normkey)) or
                (re.match(r'^comment', normkey) and self._commentTargets.match(metadata[key]))):
                toBeDeleted += [key]
            normkey = re.sub(r'^\W*(wm|((com\W*)?apple\W*)?itunes|lastfm)\W*', r'', normkey)
            normkey = re.sub(r'[_~]', r'', normkey)
            if (normkey in self._defaultTargets):
                toBeDeleted += [key]
            else:
                if ((config.setting[r'purgeiTunes'] and (normkey in self._iTunesTargets)) or
                    (config.setting[r'purgeMusicIP'] and (r'musicip' in normkey)) or
                    (config.setting[r'purgeLastFM'] and ((r'lastfm' in normkey) or (normkey in self._lastfmTargets))) or
                    (config.setting[r'purgeAcoustID'] and (r'acoustid' in normkey))):
                    toBeDeleted += [key]
        for tagName in toBeDeleted: metadata.pop(tagName, None)

    def processFile( self, track, file ):
        self.process(None, file.metadata, track, None)

    def processFileOnLoad( self, file ):
        self.process(None, file.metadata, None, None)

    def callback( self, objs ):
        for obj in objs:
            if (isinstance(obj, Track)):
                for f in obj.linked_files: self.process(None, f.metadata, obj, None)
            elif (isinstance(obj, File)):
                self.process(None, obj.metadata, None, None)



class OriginsOblivionOptionsPage( OptionsPage ):

    NAME = PLUGIN_NAME.casefold()
    TITLE = r'Software-Specific Tags'
    PARENT = r'tags' # r'plugins' ?

    options = [ BoolOption(r'setting', r'purgeMBIDs', False),
                BoolOption(r'setting', r'purgeiTunes', True),
                BoolOption(r'setting', r'purgeLastFM', True),
                BoolOption(r'setting', r'purgeMusicIP', True),
                BoolOption(r'setting', r'purgeAcoustID', False) ]

    def __init__( self, parent=None ):
        super().__init__(parent)
        self.box = QtWidgets.QVBoxLayout(self)
        self.purgeMBIDs = QtWidgets.QCheckBox(self)
        self.purgeMBIDs.setCheckable(True)
        self.purgeMBIDs.setChecked(False)
        self.purgeMBIDs.setText(r'Purge MBIDs (release and track IDs not included)')
        self.box.addWidget(self.purgeMBIDs)
        self.purgeiTunes = QtWidgets.QCheckBox(self)
        self.purgeiTunes.setCheckable(True)
        self.purgeiTunes.setChecked(True)
        self.purgeiTunes.setText(r'Purge iTunes tags')
        self.box.addWidget(self.purgeiTunes)
        self.purgeLastFM = QtWidgets.QCheckBox(self)
        self.purgeLastFM.setCheckable(True)
        self.purgeLastFM.setChecked(True)
        self.purgeLastFM.setText(r'Purge Last.fm tags')
        self.box.addWidget(self.purgeLastFM)
        self.purgeMusicIP = QtWidgets.QCheckBox(self)
        self.purgeMusicIP.setCheckable(True)
        self.purgeMusicIP.setChecked(True)
        self.purgeMusicIP.setText(r'Purge MusicIP tags')
        self.box.addWidget(self.purgeMusicIP)
        self.purgeAcoustID = QtWidgets.QCheckBox(self)
        self.purgeAcoustID.setCheckable(True)
        self.purgeAcoustID.setChecked(False)
        self.purgeAcoustID.setText(r'Purge AcoustID tags')
        self.box.addWidget(self.purgeAcoustID)
        self.spacer = QtWidgets.QSpacerItem(0, 0, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding)
        self.box.addItem(self.spacer)

    def load( self ):
        self.purgeMBIDs.setChecked(config.setting[r'purgeMBIDs'])
        self.purgeiTunes.setChecked(config.setting[r'purgeiTunes'])
        self.purgeLastFM.setChecked(config.setting[r'purgeLastFM'])
        self.purgeMusicIP.setChecked(config.setting[r'purgeMusicIP'])
        self.purgeAcoustID.setChecked(config.setting[r'purgeAcoustID'])

    def save( self ):
        config.setting[r'purgeMBIDs'] = self.purgeMBIDs.isChecked()
        config.setting[r'purgeiTunes'] = self.purgeiTunes.isChecked()
        config.setting[r'purgeLastFM'] = self.purgeLastFM.isChecked()
        config.setting[r'purgeMusicIP'] = self.purgeMusicIP.isChecked()
        config.setting[r'purgeAcoustID'] = self.purgeAcoustID.isChecked()



register_file_action(OriginsOblivion())
register_file_post_addition_to_track_processor(OriginsOblivion().processFile, priority=PluginPriority.LOW)
register_file_post_load_processor(OriginsOblivion().processFileOnLoad)
# register_track_action(OriginsOblivion())
# register_track_metadata_processor(OriginsOblivion().process)
register_options_page(OriginsOblivionOptionsPage)
