
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
# Name: No Bonus
# Description: MusicBrainz Picard plugin to removes things like '(bonus)' from title/album tags
#
# #  In order to have this plugin working (if it is currently not), place it at:
#    ~/.config/MusicBrainz/Picard/plugins
# =============================================================================================

import re
from functools import partial



PLUGIN_NAME = 'No Bonus'
PLUGIN_AUTHOR = 'Pedro Vernetti G.'
PLUGIN_DESCRIPTION = "Removes things like '(bonus track)' or '(deluxe)' from title and album tags."
PLUGIN_VERSION = '0.1'
PLUGIN_API_VERSIONS = ['2.0', '2.1', '2.2', '2.3', '2.4', '2.5', '2.6']
PLUGIN_LICENSE = 'GPLv3'
PLUGIN_LICENSE_URL = 'https://www.gnu.org/licenses/gpl-3.0.en.html'

from PyQt5 import QtWidgets
from picard import config, log
from picard.file import File, register_file_post_addition_to_track_processor
from picard.plugin import PluginPriority
from picard.track import Track
from picard.album import Album
from picard.ui.itemviews import BaseAction, register_file_action, register_album_action
from picard.util import thread



class NoBonus( BaseAction ):

    NAME = "Purge 'bonus'/'deluxe' infos"

    _bonus = r'(bonus|(previously\s*)?unreleased|exclusive)(\s*(track|ver(sion|\.)?|edition|release|dis[ck]))?'
    _std = r'(standard|official|studio)(\s*(track|ver(sion|\.)?|edition|release))?'
    _deluxe = r'(special|deluxe|collect(or' + "'" + '?s' + "'" + '?|ion))(\s*(version|edition|release|dis[ck]))?'
    _ext = r'extended(\s*(version|edition|release|dis[ck]))?'
    _outtake = r'(studio\s*)?outtake'

    _forTitle = r'[(\[](' + _bonus + r'|' + _std + r'|' + _deluxe + r'|' + _outtake + r')[)\]]'
    _forAlbum = r'[(\[](' + _bonus + r'|' + _std + r'|' + _deluxe + r'|' + _ext + r')[)\]]'

    _title = re.compile((r'\s+' + _forTitle + '\s*$'), re.IGNORECASE)
    _titlesort = re.compile((r'\s+' + _forAlbum + '\)\s*(, \w+\s*)?$'), re.IGNORECASE)
    _album = re.compile((r'\s+' + _forTitle + '\s*$'), re.IGNORECASE)

    _emptyPar = re.compile(r'\s*\(\)')

    def __init__( self ):
        super().__init__()

    def process( self, album, metadata, track, release ):
        title = self._title.sub(r'', metadata.get(r'title', r'')).strip()
        titlesort = self._titlesort.sub(r'', metadata.get(r'titlesort', r'')).strip()
        album = self._album.sub(r'', metadata.get(r'album', r'')).strip()
        metadata[r'title'] = self._emptyPar.sub(r'', title)
        metadata[r'titlesort'] = self._emptyPar.sub(r'', titlesort)
        metadata[r'album'] = self._emptyPar.sub(r'', album)

    def _finish( self, file, result=None, error=None ):
        pass

    def processFile( self, track, file ):
        self.process(None, file.metadata, track, None)

    def callback( self, objs ):
        for obj in objs:
            if (isinstance(obj, Track)):
                for f in obj.linked_files: self.process(None, f.metadata, obj, None)
            elif (isinstance(obj, File)):
                self.process(None, obj.metadata, None, None)



class NoBonusForAlbums( NoBonus ):

    NAME = "Purge 'bonus'/'deluxe' infos"

    def __init__( self ):
        super().__init__()

    def callback( self, objs ):
        for obj in objs:
            if (isinstance(obj, Album)):
                for track in obj.tracks:
                    for f in track.linked_files:
                        thread.run_task(partial(super().process, None, f.metadata, obj, None, True),
                                partial(super()._finish, f))



register_file_action(NoBonus())
register_file_post_addition_to_track_processor(NoBonus().processFile, priority=PluginPriority.LOW)
register_album_action(NoBonusForAlbums())
