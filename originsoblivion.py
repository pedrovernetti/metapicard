
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
# Description: MusicBrainz Picard plugin to purge encoding and software-related tags.
#
# #  In order to have this plugin working (if it is currently not), place it at:
#    ~/.config/MusicBrainz/Picard/plugins
# =============================================================================================

import re



PLUGIN_NAME = 'Origins Oblivion'
PLUGIN_AUTHOR = 'Pedro Vernetti G.'
PLUGIN_DESCRIPTION = 'Purges most/all encoding and software-related tags.'
PLUGIN_VERSION = '0.1'
PLUGIN_API_VERSIONS = ['2.0', '2.1', '2.2', '2.3', '2.4', '2.5', '2.6']
PLUGIN_LICENSE = 'GPLv3'
PLUGIN_LICENSE_URL = 'https://www.gnu.org/licenses/gpl-3.0.en.html'

from picard import log
from picard.file import File, register_file_post_addition_to_track_processor, register_file_post_load_processor
from picard.metadata import register_track_metadata_processor
from picard.track import Track
from picard.ui.itemviews import BaseAction, register_file_action, register_track_action



class OriginsOblivion( BaseAction ):

    NAME = "Purge Encoding/Software-Related Tags"

    def __init__( self ):
        super().__init__()

    def process( self, album, metadata, track, release ):
        metadata.pop(r'encodersettings', None)
        metadata.pop(r'encodedby', None)
        metadata.pop(r'encoding params', None)
        metadata.pop(r'compatible_brands', None)
        metadata.pop(r'ENCODINGTIME', None)
        metadata.pop(r'major_brand', None)
        metadata.pop(r'minor_version', None)
        metadata.pop(r'software', None)
        metadata.pop(r'source', None)
        metadata.pop(r'itunsmpb', None)
        metadata.pop(r'tbpm', None)
        metadata.pop(r'tlen', None)
        metadata.pop(r'tsrc', None)

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



register_file_action(OriginsOblivion())
register_file_post_addition_to_track_processor(OriginsOblivion().processFile)
register_file_post_load_processor(OriginsOblivion().processFileOnLoad)
# register_track_action(OriginsOblivion())
# register_track_metadata_processor(OriginsOblivion().process)
