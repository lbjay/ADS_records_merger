# Copyright (C) 2011, The SAO/NASA Astrophysics Data System
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
Pipeline timestamp manager.

This module is responsible for comparing the records in ADS and the records in
Invenio. Its only public method is get_record_status() which returns 3 sets of
bibcodes:
    * the bibcodes not yet added to Invenio.
    * the bibcodes of the records that have been modified.
    * the bibcodes of the records that have been deleted in ADS.
"""

import ads

from invenio.dbquery import run_sql

from pipeline_settings import BIBCODES_AST, BIBCODES_PHY, BIBCODES_GEN, BIBCODES_PRE
from pipeline_log_functions import msg as printmsg
from pipeline_settings import VERBOSE

# Timestamps ordered by increasing order of importance.
TIMESTAMP_FILES_HIERARCHY = [
        BIBCODES_GEN,
        BIBCODES_PRE,
        BIBCODES_PHY,
        BIBCODES_AST,
        ]

def get_records_status(verbose=VERBOSE):
    """
    Return 3 sets of bibcodes:
    * bibcodes added are bibcodes that are in ADS and not in Invenio.
    * bibcodes modified are bibcodes that are both in ADS and in Invenio and
      that have been modified since the last update.
    * bibcodes deleted are bibcodes that are in Invenio but not in ADS.
    """
    records_added = []
    records_modified = []
    records_deleted = []

    printmsg('Getting ADS timestamps.', verbose)
    ads_timestamps = _get_ads_timestamps()
    printmsg('Getting ADS bibcodes.', verbose)
    ads_bibcodes = set(ads_timestamps.keys())
    printmsg('Getting Invenio timestamps.', verbose)
    invenio_timestamps = _get_invenio_timestamps()
    printmsg('Getting Invenio bibcodes.', verbose)
    invenio_bibcodes = set(invenio_timestamps.keys())

    printmsg('Deducting the added records.', verbose)
    records_added = ads_bibcodes - invenio_bibcodes
    printmsg('    %d records to add.' % len(records_added), verbose)
    printmsg('Deducting the deleted records.', verbose)
    records_deleted = invenio_bibcodes - ads_bibcodes
    printmsg('    %d records to delete.' % len(records_deleted), verbose)

    records_to_check = invenio_bibcodes - records_deleted
    printmsg('Checking timestamps for %d records.' %
            len(records_to_check), verbose)

    for bibcode in records_to_check:
        # ADS timestamp in the file has tabs as separators where the XML has
        # colons.
        ads_timestamp = ads_timestamps[bibcode]
        invenio_timestamp = invenio_timestamps[bibcode]

        if invenio_timestamp != ads_timestamp:
            records_modified.append(bibcode)

    printmsg('    %d records to modify.\n' % len(records_modified), verbose)
    printmsg('Done.', verbose)

    return records_added, records_modified, records_deleted

def _get_invenio_timestamps():
    """
    Returns a set of timestamps found in Invenio.
    """
    # First get the list of deleted records, i.e. records which have DELETED in 980__c.
    query = "SELECT DISTINCT(b97.value) FROM bib97x AS b97, bibrec_bib97x AS bb97, bib98x AS b98, bibrec_bib98x AS bb98 " \
            "WHERE b98.tag='980__c' AND b98.value='DELETED' AND b98.id=bb98.id_bibxxx AND " \
            "b97.id=bb97.id_bibxxx AND b97.tag='970__a' AND " \
            "bb98.id_bibrec=bb97.id_bibrec"
    deleted_bibcodes = [line[0] for line in run_sql(query)]

    # Then get all the timestamps.
    query = "SELECT b97.value, b99.value FROM bib99x AS b99, " \
            "bibrec_bib99x AS bb99, bib97x AS b97, bibrec_bib97x AS bb97 " \
            "WHERE b99.tag='995__a' AND b99.id=bb99.id_bibxxx AND " \
            "b97.id=bb97.id_bibxxx AND bb97.id_bibrec=bb99.id_bibrec"

    # Finally, return only the records that are not deleted.
    timestamps = {}
    for bibcode, timestamp in run_sql(query):
        if bibcode not in deleted_bibcodes:
            timestamps[bibcode] = timestamp

    return timestamps

def _get_ads_timestamps():
    """
    Merges the timestamp files according to the importance of the database
    in ADS.

    Returns a dictionary with the bibcodes as keys and the timestamps as values.
    """
    timestamps = {}
    for filename in TIMESTAMP_FILES_HIERARCHY:
        db_timestamps = _read_timestamp_file(filename)
        timestamps.update(db_timestamps)

    # Now let's remove the timestamps of published eprints as they don't appear
    # as such in Invenio.
    published_eprints = [line.strip().split('\t', 1)[1]
                         for line in open(ads.pub2arx)]
    for bibcode in published_eprints:
        try:
            del timestamps[bibcode]
        except:
            pass

    return timestamps

def _read_timestamp_file(filename):
    """
    Reads a timestamp file and returns a dictionary with the bibcodes as keys
    and the timestamps as values.
    """
    fdesc = open(filename)
    timestamps = {}
    for line in fdesc:
        bibcode, timestamp = line[:-1].split('\t', 1)
        timestamps[bibcode] = timestamp
    fdesc.close()

    return timestamps
