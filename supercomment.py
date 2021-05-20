
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
# Name: SuperComment
# Description: MusicBrainz Picard plugin to merge all/most release info into the comment tag.
#
# #  In order to have this plugin working (if it is currently not), place it at:
#    ~/.config/MusicBrainz/Picard/plugins
# =============================================================================================

import re



PLUGIN_NAME = 'SuperComment'
PLUGIN_AUTHOR = 'Pedro Vernetti G.'
PLUGIN_DESCRIPTION = 'Merge most/all release-specific information into the comment tag.'
PLUGIN_VERSION = '0.1'
PLUGIN_API_VERSIONS = ['2.0', '2.1', '2.2', '2.3', '2.4', '2.5', '2.6']
PLUGIN_LICENSE = 'GPLv3'
PLUGIN_LICENSE_URL = 'https://www.gnu.org/licenses/gpl-3.0.en.html'

from PyQt5 import QtWidgets
from picard.config import BoolOption
from picard import config, log
from picard.file import File
from picard.metadata import register_track_metadata_processor
from picard.track import Track
from picard.ui.itemviews import BaseAction, register_file_action, register_track_action
from picard.ui.options import OptionsPage, register_options_page



class SuperComment( BaseAction ):

    NAME = "Merge Release Information into Comment"

    _trueSubkinds = {r'compilation', r'live', r'remix', r'spokenword', r'soundtrack'}
    _kindSubkinds = {r'mixtape', r'audiobook', r'interview', r'audio drama'}

    _countryNames = { r'AF': r'Afghanistan', r'AX': r'Åland Islands', r'AL': r'Albania',
                      r'DZ': r'Algeria', r'AS': r'American Samoa', r'AD': r'Andorra',
                      r'AO': r'Angola', r'AI': r'Anguilla', r'AQ': r'Antarctica',
                      r'AG': r'Antigua and Barbuda', r'AR': r'Argentina', r'AM': r'Armenia',
                      r'AW': r'Aruba', r'AU': r'Australia', r'AT': r'Austria', r'AZ': r'Azerbaijan',
                      r'BS': r'Bahamas', r'BH': r'Bahrain', r'BD': r'Bangladesh', r'BB': r'Barbados',
                      r'BY': r'Belarus', r'BE': r'Belgium', r'BZ': r'Belize', r'BJ': r'Benin',
                      r'BM': r'Bermuda', r'BT': r'Bhutan', r'BO': r'Bolivia',
                      r'BA': r'Bosnia and Herzegovina', r'BW': r'Botswana', r'BV': r'Bouvet Island',
                      r'BR': r'Brazil', r'IO': r'British Indian Ocean Territory',
                      r'BN': r'Brunei Darussalam', r'BG': r'Bulgaria', r'BF': r'Burkina Faso',
                      r'BI': r'Burundi', r'KH': r'Cambodia', r'CM': r'Cameroon', r'CA': r'Canada',
                      r'CV': r'Cape Verde', r'KY': r'Cayman Islands', r'CF': r'Central African Republic',
                      r'TD': r'Chad', r'CL': r'Chile', r'CN': r'China', r'CX': r'Christmas Island',
                      r'CC': r'Cocos (Keeling) Islands', r'CO': r'Colombia', r'KM': r'Comoros',
                      r'CG': r'Congo', r'CD': r'DRC', r'CK': r'Cook Islands', r'CR': r'Costa Rica',
                      r'CI': "Cote d'Ivoire", r'HR': r'Croatia', r'CU': r'Cuba', r'CY': r'Cyprus',
                      r'XC': r'Czechoslovakia', r'CZ': r'Czech Republic', r'DK': r'Denmark',
                      r'DJ': r'Djibouti', r'DM': r'Dominica', r'DO': r'Dominican Republic',
                      r'XG': r'East Germany', r'EC': r'Ecuador', r'EG': r'Egypt', r'SV': r'El Salvador',
                      r'GQ': r'Equatorial Guinea', r'ER': r'Eritrea', r'EE': r'Estonia',
                      r'ET': r'Ethiopia', r'XE': r'Europe', r'FK': r'Falkland Islands',
                      r'FO': r'Faroe Islands', r'FJ': r'Fiji', r'FI': r'Finland', r'FR': r'France',
                      r'GF': r'French Guiana', r'PF': r'French Polynesia', r'TF': r'French Southern Territories',
                      r'GA': r'Gabon', r'GM': r'Gambia', r'GE': r'Georgia', r'DE': r'Germany',
                      r'GH': r'Ghana', r'GI': r'Gibraltar', r'GR': r'Greece', r'GL': r'Greenland',
                      r'GD': r'Grenada', r'GP': r'Guadeloupe', r'GU': r'Guam', r'GT': r'Guatemala',
                      r'GG': r'Guernsey', r'GN': r'Guinea', r'GW': r'Guinea-Bissau', r'GY': r'Guyana',
                      r'HT': r'Haiti', r'HM': r'Heard and McDonald Islands', r'HN': r'Honduras',
                      r'HK': r'Hong Kong', r'HU': r'Hungary', r'IS': r'Iceland', r'IN': r'India',
                      r'ID': r'Indonesia', r'IR': r'Iran', r'IQ': r'Iraq', r'IE': r'Ireland',
                      r'IM': r'Isle of Man', r'IL': r'Israel', r'IT': r'Italy', r'JM': r'Jamaica',
                      r'JP': r'Japan', r'JE': r'Jersey', r'JO': r'Jordan', r'KZ': r'Kazakhstan',
                      r'KE': r'Kenya', r'KI': r'Kiribati', r'KP': r'North Korea', r'KR': r'South Korea',
                      r'KW': r'Kuwait', r'KG': r'Kyrgyzstan', r'LA': r'Lao', r'LV': r'Latvia',
                      r'LB': r'Lebanon', r'LS': r'Lesotho', r'LR': r'Liberia', r'LY': r'Libya',
                      r'LI': r'Liechtenstein', r'LT': r'Lithuania', r'LU': r'Luxembourg',
                      r'MO': r'Macau', r'MK': r'Yugoslav Republic of Macedonia', r'MG': r'Madagascar',
                      r'MW': r'Malawi', r'MY': r'Malaysia', r'MV': r'Maldives', r'ML': r'Mali',
                      r'MT': r'Malta', r'MH': r'Marshall Islands', r'MQ': r'Martinique',
                      r'MR': r'Mauritania', r'MU': r'Mauritius', r'YT': r'Mayotte', r'MX': r'Mexico',
                      r'FM': r'Federated States of Micronesia', r'MD': r'Moldova', r'MC': r'Monaco',
                      r'MN': r'Mongolia', r'ME': r'Montenegro', r'MS': r'Montserrat', r'MA': r'Morocco',
                      r'MZ': r'Mozambique', r'MM': r'Myanmar', r'NA': r'Namibia', r'NR': r'Nauru',
                      r'NP': r'Nepal', r'NL': r'Netherlands', r'AN': r'Netherlands Antilles',
                      r'NC': r'New Caledonia', r'NZ': r'New Zealand', r'NI': r'Nicaragua',
                      r'NE': r'Niger', r'NG': r'Nigeria', r'NU': r'Niue', r'NF': r'Norfolk Island',
                      r'MP': r'Northern Mariana Islands', r'NO': r'Norway', r'OM': r'Oman',
                      r'PK': r'Pakistan', r'PW': r'Palau', r'PS': r'Palestine', r'PA': r'Panama',
                      r'PG': r'Papua New Guinea', r'PY': r'Paraguay', r'PE': r'Peru',
                      r'PH': r'Philippines', r'PN': r'Pitcairn', r'PL': r'Poland', r'PT': r'Portugal',
                      r'PR': r'Puerto Rico', r'QA': r'Qatar', r'RE': r'Reunion', r'RO': r'Romania',
                      r'RU': r'Russia', r'RW': r'Rwanda', r'BL': r'Saint Barthélemy',
                      r'SH': r'Saint Helena', r'KN': r'Saint Kitts and Nevis', r'LC': r'Saint Lucia',
                      r'MF': r'Saint Martin', r'PM': r'Saint Pierre and Miquelon',
                      r'VC': r'Saint Vincent and The Grenadines', r'WS': r'Samoa', r'SM': r'San Marino',
                      r'ST': r'São Tome and Principe', r'SA': r'Saudi Arabia', r'SN': r'Senegal',
                      r'RS': r'Serbia', r'CS': r'Serbia and Montenegro', r'SC': r'Seychelles',
                      r'SL': r'Sierra Leone', r'SG': r'Singapore', r'SK': r'Slovakia', r'SI': r'Slovenia',
                      r'SB': r'Solomon Islands', r'SO': r'Somalia', r'ZA': r'South Africa',
                      r'GS': r'South Georgia and South Sandwich Islands', r'SU': r'URSS',
                      r'ES': r'Spain', r'LK': r'Sri Lanka', r'SD': r'Sudan', r'SR': r'Suriname',
                      r'SJ': r'Svalbard and Jan Mayen', r'SZ': r'Swaziland', r'SE': r'Sweden',
                      r'CH': r'Switzerland', r'SY': r'Syria', r'TW': r'Taiwan', r'TJ': r'Tajikistan',
                      r'TZ': r'Tanzania', r'TH': r'Thailand', r'TL': r'East Timor', r'TG': r'Togo',
                      r'TK': r'Tokelau', r'TO': r'Tonga', r'TT': r'Trinidad and Tobago',
                      r'TN': r'Tunisia', r'TR': r'Turkey', r'TM': r'Turkmenistan', r'TC': r'Turks and Caicos',
                      r'TV': r'Tuvalu', r'UG': r'Uganda', r'UA': r'Ukraine', r'AE': r'UAE',
                      r'GB': r'United Kingdom', r'US': r'USA', r'UM': r'USA Minor Outlying Islands',
                      r'XU': r'?', r'UY': r'Uruguay', r'UZ': r'Uzbekistan', r'VU': r'Vanuatu',
                      r'VA': r'Vatican', r'VE': r'Venezuela', r'VN': r'Vietnam',
                      r'VG': r'British Virgin Islands', r'VI': r'USA Virgin Islands',
                      r'WF': r'Wallis and Futuna', r'EH': r'Western Sahara', r'XW': r'Worldwide',
                      r'YE': r'Yemen', r'YU': r'Yugoslavia', r'ZM': r'Zambia', r'ZW': r'Zimbabwe', }

    def __init__( self ):
        super().__init__()

    def _company( self, metadata ):
        company = metadata.get(r'label', metadata.get(r'company', r'')).strip()
        if (not company): company = metadata.get(r'organization', r'').strip()
        if (not company): company = metadata.get(r'publisher', r'?').strip()
        metadata.pop(r'label', None)
        metadata.pop(r'labelcode', None)
        metadata.pop(r'company', None)
        metadata.pop(r'organization', None)
        metadata.pop(r'publisher', None)
        independent = r'^\s*\[?(no(t\s*on)?\s*label|ind(ependente?|ie)|self[\s_-]*released)\]?\s*$'
        independent = re.compile(independent)
        catalogNumber = metadata.get(r'catalognumber', r'').strip()
        metadata.pop(r'catalognumber', None)
        if (independent.match(company.casefold())): return r'independent;'
        albumartist = metadata.get(r'albumartist', metadata.get(r'~albumartists', r''))
        if (re.sub(r'[\s_,.-]', r'', company) == re.sub(r'[\s_,.-]', r'', albumartist)):
            return r'independent'
        if (len(catalogNumber)): return (company + r' (' + catalogNumber + r');')
        else: return (company + r';')

    def _formatWithInches( self, x ):
        inches = x.group(2)
        if (not inches): inches = r''
        if (len(inches)): inches = inches.replace(r',', r'.') + r'"'
        what = x.group(4)
        if (r'floppy' in what): what = r'floppy disk'
        elif (r'flexi' in what): what = r'flexi disc'
        elif (r'laser' in what): what = r'LaserDisc'
        return (inches + r' ' + what)

    def _formatDVD( self, x ):
        hd = x.group(1)
        if (not hd): hd = r''
        av = x.group(3)
        if (not av): av = r''
        if (av == r'plus'): return r'DVDplus'
        return ((r'HD-' if (len(hd)) else r'') + r'DVD' + ((r'-' + av[0].upper()) if (len(av)) else r''))

    def _formatBluRay( self, x ):
        what = r'Blu-Ray'
        if (not x.group(2)): return what
        else: return (what + r'-R')

    def _formatCD( self, x ):
        prefix = x.group(1)
        if (not prefix): prefix = r''
        suffix = x.group(2)
        if (not suffix): suffix = r''
        suffix = r'' if (not suffix) else suffix[-1].upper()
        suffix = r'+G' if (suffix == r'G') else (r'-R' if (suffix == r'R') else suffix)
        if (not prefix): return (r'CD' + suffix)
        if (r'copy' in prefix): return (r'copy control CD' + suffix)
        elif (prefix.startswith(r'blu')): return (r'Blu-spec CD' + suffix)
        elif (prefix == r'dts'): return (r'DTS CD' + suffix)
        elif (prefix == r'shm'): return (r'SHM-CD' + suffix)
        elif (prefix.endswith(r'v')): return (prefix.upper() + r'CD' + suffix)
        elif (prefix.startswith(r'h')): return (prefix.upper() + r'CD' + suffix)
        else: return (re.sub(r'[ -]*', r'', prefix) + r' CD' + suffix)

    def _formatOther( self, x ):
        justUpper = {r'ced', r'dat', r'dcc', r'umd', r'vhd', r'vhs', r'sacd'}
        mapping = { r'playtape':r'PlayTape', r'betamax':r'Betamax', r'playbutton':r'Playbutton',
                    r'hipac':r'HiPac', r'reeltoreel':r'reel-to-reel', r'tefifon':r'Tefifon',
                    r'slotmusic':r'slotMusic', r'elcaset':r'Elcaset', r'edison':r'Edison disc' }
        what = re.sub(r'[ -]+', r'', x.group(1))
        if (what in justUpper): return what.upper()
        if (what in mapping): return mapping[what]
        if (what.startswith(r'vinyldis')): return r'VinylDisc'
        if (what.startswith(r'sd')): return r'SD card'
        if (what.startswith(r'usb')): return r'USB flash drive'
        if (what.startswith(r'dual')): return r'DualDisc'
        if (what.startswith(r'mini')): return r'MiniDisc'
        if (what.startswith(r'shm')): return r'SHM-SACD'
        if (what.startswith(r'hybr')): return r'hybrid SACD'
        if (what.startswith(r'zip')): return r'zip disk'
        if (what.startswith(r'path')): return r'Pathé disc'
        return what

    def _format( self, what ):
        if ((r'other' in what) or (not what)): return r''
        if (r'digital' in what): return r'digital'
        what = re.sub(r'[\s_]+', r' ', re.sub(r'[\s_]*\([^)]\)', r'', what))
        vinyl = re.compile(r'(([0-9,.]+)(''|")[\s-]*)?(vinyl|shellac|flexi[\s-]*dis[ck]|floppy|laser[ -]?dis[ck])')
        if (vinyl.match(what)): return vinyl.sub(self._formatWithInches, what)
        cassette = re.compile(r'.*(micro)?[ -]*cassette.*')
        if (cassette.match(what)): return cassette.sub(r'\1cassette', what)
        dvd = re.compile(r'(hd[ -]*)?dvd([ -]?(audio|video|plus))?')
        if (dvd.match(what)): return dvd.sub(self._formatDVD, what)
        bluray = re.compile(r'.*(blu[ -]*ray)([ -]*r)?.*')
        if (bluray.match(what)): return bluray.sub(self._formatBluRay, what)
        what = re.sub(r'compact( |-*)dis[ck]', r'cd', what)
        cd = re.compile(r'(8 ?cm|blu[ -]*spec|copy[ -]*control|data|dts|enhanced|s?v|h[dq]|shm)?[ -]*cd(\+?g|-?r|v)?')
        if (cd.match(what)): return cd.sub(self._formatCD, what)
        other = r'.*(betamax|cartridge|(music|sd)[ -]*card|path.[ -]*disc|piano[ -]*roll|'
        other += r'wax cylinder|wire recording|([48][ -]*|multi)tracks[ -]*record(ing)?|vinyldis[ck]|'
        other += r'playbutton|(dual|mini)[ -]*dis[ck]|zip[ -]*dis[ck]|playtape|hipac|tefifon|'
        other += r'elcaset|edison|(shm[ -]*)?sacd|hybrid[ -]*sacd|reel[ -]*to[ -]*reel|slotmusic|'
        other = re.compile(other + r'usb[ -]+|ced|dat|dcc|umd|vh[ds]|gramophone[ -]record(ing)?).*')
        if (other.match(what)): return other.sub(self._formatOther, what)
        return r''

    def _appendReleaseTypeToAlbum( self, metadata, kind, subkind ):
        album = metadata.get(r'album', metadata.get(r'~releasegroup', r''))
        album = re.sub(r'\s+', r' ', re.sub(r'\W*(demo|single|mixtape|ep)\W*$', r'', album)).strip()
        normalizedAlbum = r' ' + album.casefold() + r' '
        if (not album): return
        print(album, r'[' + kind + r']', r'(' + subkind + r')')
        if (((subkind == r'demo') or (kind == r'demo')) and (not re.match(r'\Wdemo\W* ', normalizedAlbum))):
            album += r' (demo)'
        elif ((kind == r'single') and (not re.match(r'\Wsingle\W*$', normalizedAlbum))):
            album += r' (single)'
        elif ((kind == r'ep') and (not re.match(r'\Wep\W*$', normalizedAlbum))):
            album += r' EP'
        elif ((subkind == r'mixtape') and (not re.match(r'\Wmixtape\W', normalizedAlbum))):
            album += r' Mixtape'
        else:
            return
        metadata[r'album'] = album

    def _what( self, metadata ):
        what = self._format(metadata.get(r'media', r'').casefold().strip())
        metadata.pop(r'media', None)
        status = metadata.get(r'releasestatus', r'').casefold()
        metadata.pop(r'releasestatus', None)
        if (r'promo' in status): what += r' promo'
        elif (r'bootleg' in status): what += r' bootleg'
        kind = metadata.get(r'releasetype', metadata.get(r'~primaryreleasetype', r'')).strip().casefold()
        metadata.pop(r'releasetype', None)
        metadata.pop(r'~primaryreleasetype', None)
        subkind = metadata.get(r'~secondaryreleasetype', r'').strip().casefold()
        metadata.pop(r'~secondaryreleasetype', None)
        if ((not subkind) and (metadata.get(r'compilation', None) == r'1')): subkind = r'compilation'
        elif ((subkind == r'street') or (r'mixtape' in subkind)): subkind = r'mixtape'
        elif (r'spoken' in subkind): subkind = r'spokenword'
        metadata.pop(r'compilation', None)
        if (config.setting[r'appendReleaseTypeToAlbum']):
            self._appendReleaseTypeToAlbum(metadata, kind, subkind)
        if ((subkind == r'demo') or (kind == r'demo')):
            what += r' demo'
        else:
            if (kind == r'ep'): what += r' EP'
            elif (kind == r'other'): what += r' release'
            else: what += (r' ' + kind)
            if (subkind in self._trueSubkinds): kind = r' ' + subkind + kind
            elif (subkind in self._kindSubkinds): kind = r' ' + subkind
            elif (re.match(r'dj.*mix', subkind)): kind = r' DJ mix'
        djmixer = metadata.get(r'djmixer', r'')
        if (len(djmixer) and (not metadata[r'albumartist'])): metadata[r'albumartist'] = djmixer
        metadata.pop(r'djmixer', None)
        if (what[0] != r' '): what = r' ' + what
        return (r' ?;' if (re.match(r'^\s*$', what)) else (what + r'; '))

    def _whereAndWhen( self, metadata ):
        when = metadata.get(r'date', r'')
        originalYear = metadata.get(r'originalyear', metadata.get(r'originaldate', None))
        if (not originalYear): originalYear = metadata.get(r'~recording_firstreleasedate', None)
        if (not originalYear): originalYear = metadata.get(r'~releasegroup_firstreleasedate', when)
        if (len(originalYear)): metadata[r'date'] = originalYear[:4]
        metadata.pop(r'originalyear', None)
        metadata.pop(r'originaldate', None)
        metadata.pop(r'Original Year', None)
        metadata.pop(r'~recording_firstreleasedate', None)
        metadata.pop(r'~releasegroup_firstreleasedate', None)
        where = metadata.get(r'releasecountry', metadata.get(r'~releasecountries', r'')).strip()
        metadata.pop(r'releasecountry', None)
        metadata.pop(r'~releasecountries', None)
        if (len(where) == 2): where = self._countryNames[where.upper()]
        if (when and where): return (r' ' + where + r' - ' + when + r';')
        elif (len(when)): return (r' ? - ' + when + r';')
        elif (len(where)): return  (r' ' + where + r' - ?;')
        else: return r' ?;'

    def process( self, album, metadata, track, release ):
        comment = self._company(metadata)
        comment += self._what(metadata)
        comment += self._whereAndWhen(metadata)
        metadata.pop(r'script', None)
        metadata.pop(r'license', None)
        metadata.pop(r'copyright', None)
        if (config.setting[r'includeBarcode']):
            barcode = metadata.get(r'barcode', r'')
            if (len(barcode)): comment += (r' barcode: ' + re.sub(r'[^0-9]', r'', barcode) + r',')
        metadata.pop(r'barcode', None)
        # isrc = metadata.get(r'isrc', r'')
        # if (len(isrc)): comment += (r' ISRC: ' + re.sub(r'[^0-9]', r'', isrc) + r',')
        metadata.pop(r'isrc', None)
        metadata.pop(r'asin', None)
        metadata.pop(r'discid', None)
        metadata.pop(r'musicip_puid', None)
        metadata.pop(r'musicbrainz_albumid', None)
        metadata.pop(r'musicbrainz_originalalbumid', None)
        metadata.pop(r'musicbrainz_releasegroupid', None)
        metadata.pop(r'musicbrainz_recordingid', None)
        metadata.pop(r'musicbrainz_albumartistid', None)
        metadata.pop(r'musicbrainz_discid', None)
        metadata.pop(r'comment:', None)
        metadata.pop(r'Comment', None)
        metadata.pop(r'Comment:', None)
        metadata[r'comment'] = re.sub(r'[,;]$', r'', re.sub(r'\s+', r' ', comment.strip()))

    def callback( self, objs ):
        for obj in objs:
            if isinstance(obj, Track):
                for f in obj.linked_files: self.process(None, f.metadata, None, None)
            elif isinstance(obj, File):
                self.process(None, obj.metadata, None, None)



class SuperCommentOptionsPage( OptionsPage ):

    NAME = PLUGIN_NAME.casefold()
    TITLE = PLUGIN_NAME
    PARENT = r'tags'

    options = [BoolOption(r'setting', r'appendReleaseTypeToAlbum', True),
               BoolOption(r'setting', r'includeBarcode', True)]

    def __init__( self, parent=None ):
        super().__init__(parent)
        self.box = QtWidgets.QVBoxLayout(self)
        self.appendReleaseTypeToAlbum = QtWidgets.QCheckBox(self)
        self.appendReleaseTypeToAlbum.setCheckable(True)
        self.appendReleaseTypeToAlbum.setChecked(True)
        self.appendReleaseTypeToAlbum.setText(r'Add relevant release type info. to album title before moving it to comment')
        self.box.addWidget(self.appendReleaseTypeToAlbum)
        self.includeBarcode = QtWidgets.QCheckBox(self)
        self.includeBarcode.setCheckable(True)
        self.includeBarcode.setChecked(True)
        self.includeBarcode.setText(r'Include barcode into the generated comment (when available)')
        self.box.addWidget(self.includeBarcode)
        self.spacer = QtWidgets.QSpacerItem(0, 0, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding)
        self.box.addItem(self.spacer)

    def load( self ):
        self.appendReleaseTypeToAlbum.setChecked(config.setting[r'appendReleaseTypeToAlbum'])
        self.includeBarcode.setChecked(config.setting[r'includeBarcode'])

    def save( self ):
        config.setting[r'appendReleaseTypeToAlbum'] = self.appendReleaseTypeToAlbum.isChecked()
        config.setting[r'includeBarcode'] = self.includeBarcode.isChecked()



register_file_action(SuperComment())
# register_track_action(SuperComment())
register_track_metadata_processor(SuperComment().process)
register_options_page(SuperCommentOptionsPage)
