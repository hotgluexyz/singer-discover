#!/usr/bin/env python
import os
import sys
import argparse
import json
from singer import metadata, get_logger
import tty
from prompt_toolkit.styles import Style
from PyInquirer.prompt import prompt

logger = get_logger().getChild('singer-discover')

def breadcrumb_name(breadcrumb):
    name = ".".join(breadcrumb)
    name = name.replace('properties.', '')
    name = name.replace('.items', '[]')
    return name


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', '-o', type=str, required=True)

    if sys.stdin.isatty():
        parser.add_argument('--input', '-i', type=str, required=True)

        args = parser.parse_args()

        with open(args.input) as f:
            catalog = json.load(f)

    else:

        args = parser.parse_args()

        catalog = json.loads(sys.stdin.read())

        sys.stdin = sys.stdout

    logger.info("Catalog configuration starting...")

    select_streams = {
        'type': 'checkbox',
        'message': 'Select Streams',
        'name': 'streams',
        'choices': [
            {'name': stream['stream']} for stream in catalog['streams']
        ]
    }

    style = Style.from_dict({
        'selected': '#007700',
        'question': 'bold',
    })

    selected_streams = prompt(select_streams, style=style)

    for i, stream in enumerate(catalog['streams']):

        mdata = metadata.to_map(stream['metadata'])

        if stream['stream'] not in selected_streams['streams']:
            mdata = metadata.write(
                mdata, (), 'selected', False
            )
        else:
            mdata = metadata.write(
                mdata, (), 'selected', True
            )

            fields = []

            field_reference = {}

            for breadcrumb, field in mdata.items():

                if breadcrumb != ():
                    selected, disabled = False, False
                    if metadata.get(
                            mdata, breadcrumb, 'inclusion') == 'automatic':
                        selected, disabled = True, "automatic"

                    elif metadata.get(
                            mdata, breadcrumb, 'selected-by-default'):
                        selected, disabled = True, False

                    name = breadcrumb_name(breadcrumb)

                    field_reference[name] = breadcrumb

                    fields.append({
                        'name': name,
                        'checked': selected,
                        'disabled': disabled
                    })

            # Order fields alphabetically, skip if error
            try:
                fields = sorted(fields, key=lambda field: field['name'])
            except KeyError:
                pass

            stream_options = {
                'type': 'checkbox',
                'message': 'Select fields from stream: `{}`'.format(
                    stream['stream']),
                'name': 'fields',
                'choices': fields
            }

            selections = prompt(stream_options, style=style)

            selections = [
                field_reference[n] for n in selections['fields']
                if n != "Select All"
            ]

            for breadcrumb in mdata.keys():
                if breadcrumb != ():
                    if (
                        metadata.get(
                            mdata, breadcrumb, 'inclusion') == "automatic"
                    ) or (
                        breadcrumb in selections
                    ):
                        mdata = metadata.write(
                            mdata, breadcrumb, 'selected', True)
                    else:
                        mdata = metadata.write(
                            mdata, breadcrumb, 'selected', False)

            catalog['streams'][i]['metadata'] = metadata.to_list(mdata)

    for stream in catalog["streams"]:
        for _md in stream["metadata"]:
            if not _md["breadcrumb"]:
                table_config = _md["metadata"]
                valid_replication_key = table_config.get("valid-replication-keys", None)
                forced_replication_method = table_config.get("forced-replication-method", None)

                if forced_replication_method != None:
                    if type(forced_replication_method) is dict:
                        table_config["replication-method"] = forced_replication_method["replication-method"]
                    elif type(forced_replication_method) is str:
                        table_config["replication-method"] = forced_replication_method
                elif valid_replication_key != None:
                    # If there is a valid replication key than use incremental sync.
                    table_config["replication-method"] = "INCREMENTAL"
                    table_config["replication-key"] = valid_replication_key[0]
                else:
                    table_config["replication-method"] = "FULL_TABLE"

    logger.info("Catalog configuration saved.")

    with open(args.output, 'w') as f:
        json.dump(catalog, f, indent=2)


if __name__ == '__main__':
    main()
