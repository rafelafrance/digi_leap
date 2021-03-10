#!/usr/bin/env python
"""Load iDigBio Data."""

import argparse
import sqlite3
import textwrap
import zipfile

import pandas as pd
from tqdm import tqdm

from digi_leap.pylib.const import BATCH_SIZE, ZIP_FILE
from digi_leap.pylib.util import ended, started


def get_csv_headers(args):
    """Get the headers from the CSV file in the zipped snapshot."""
    with zipfile.ZipFile(args.zip_file) as zippy:
        with zippy.open(args.csv_file) as in_file:
            headers = in_file.readline()
    return [h.decode().strip() for h in sorted(headers.split(b','))]


def get_columns_to_drop(args, headers):
    """Get columns to drop."""
    if not getattr(args, 'keep'):
        return None
    keeps = set(args.keep)
    drops = [v for v in headers if v not in keeps]
    return drops


def get_column_renames(headers, drops):
    """Rename column names so they'll work in sqlite3."""
    drops = set(drops)
    renames = {}
    used = set()

    for head in [h for h in headers if h not in drops]:
        col = head
        suffix = 0
        while col.casefold() in used:
            suffix += 1
            col = f'{head}_{str(suffix)}'
        used.add(col.casefold())
        renames[head] = col
    return renames


def sort_columns(args, renames):
    """Put columns into --keep order."""
    return {k: renames[k] for k in args.keep} if args.keep else renames


def insert(args, renames, drops):
    """Insert data from the CSV file into an SQLite3 database."""
    with sqlite3.connect(args.database) as cxn:
        with zipfile.ZipFile(args.zip_file) as zipped:
            with zipped.open(args.csv_file) as in_file:

                reader = pd.read_csv(
                    in_file,
                    dtype=str,
                    keep_default_na=False,
                    chunksize=args.batch_size)

                if_exists = 'append' if args.append_table else 'replace'

                for df in tqdm(reader):
                    if drops:
                        df = df.drop(columns=drops)

                    for filter_ in args.filter:
                        rx, col = filter_.split('@')
                        print(rx)
                        mask = df[col].str.contains(rx, case=False, regex=True)
                        df = df.loc[mask, :]

                    df = df.rename(columns=renames)
                    df = df.reindex(columns=renames.values())

                    df.to_sql(args.table_name, cxn, if_exists=if_exists, index=False)

                    if_exists = 'append'
                    break


def load_data(args):
    """Load the data."""
    headers = get_csv_headers(args)
    drops = get_columns_to_drop(args, headers)
    renames = get_column_renames(headers, drops)
    renames = sort_columns(args, renames)

    if args.column_names:
        for key in renames.keys():
            print(key)
        return

    insert(args, renames, drops)


def parse_args():
    """Process command-line arguments."""
    description = """
        Load iDigBio Data.

        The files in the iDigBio snapshot is too big to work with easily on a laptop.
        So, we extract one CSV file from them at a time and then create a database
        table from that CSV. Later on we will sample this data several times before
        eventually deleting it.
    """
    arg_parser = argparse.ArgumentParser(
        description=textwrap.dedent(description), fromfile_prefix_chars='@')

    arg_parser.add_argument(
        '--database', '-d', required=True,
        help="""Path to the output database. This is a temporary database that
            will later be sampled and then deleted.""")

    arg_parser.add_argument(
        '--zip-file', '-z', required=True,
        help="""The zip file containing the iDigBio snapshot.""")

    default = ZIP_FILE
    arg_parser.add_argument(
        '--csv-file', '-v', default=default,
        help=f"""The --zip-file itself contains several files. This is the file we
            are extracting for data. The default is {default}.""")

    arg_parser.add_argument(
        '--column-names', '-n', action='store_true',
        help="""Dump the column names and exit.""")

    arg_parser.add_argument(
        '--table-name', '-t',
        help=f"""Write the output to this table. The default is use the same name
            as the --csv-file minus the file extension.""")

    arg_parser.add_argument(
        '--keep', '-k', action='append',
        help=f"""Columns to keep from the CSV file. You may use this argument more
            than once.""")

    arg_parser.add_argument(
        '--filter', action='append',
        help="""Records must contain this value in the given field. You may use
            this argument more than once. The format is regex@column. For example
            --filter=plant@dwc:phylum will only choose records that have 'plant'
            somewhere in the 'dwc:phylum' field and --filter=.@dwc:scientificName
            will look for a non-blank 'dwc:scientificName' field.""")

    arg_parser.add_argument(
        '--append-table', '-a', action='store_true',
        help="""Are we appending to the table or creating a new one. The default is
            to create a new table.""")

    default = BATCH_SIZE
    arg_parser.add_argument(
        '--batch-size', '-b', type=int, default=default,
        help=f"""The number of lines we read from the CSV file at a time.
            The default is {default}. This is mostly used to shorten iterations for
            debugging.""")

    args = arg_parser.parse_args()

    if not args.table_name:
        args.table_name = args.csv_file.split('.')[0]

    args.filter = args.filter if args.filter else []

    return args


if __name__ == '__main__':
    started()

    ARGS = parse_args()
    load_data(ARGS)

    ended()
