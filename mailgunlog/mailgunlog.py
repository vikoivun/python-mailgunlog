# -*- coding: utf-8 -*-

import os
import sys
import json
import argparse
import time
from datetime import datetime, date as _date
from dateutil.relativedelta import relativedelta
from email.utils import formatdate

import requests

def logs(domain, api_key, begin=None, end=None, type=None, severity=None, verbose=False):
    url = f'https://api.eu.mailgun.net/v3/{domain}/events'

    params = {}

    if begin:
        params['begin'] = begin
    if end:
        params['end'] = end
    else:
        params['ascending'] = 'no'

    if severity:
        params['severity'] = severity

    if type == 'failed':
        params['event'] = 'failed'

    while True:
        response = requests.get(url=url, auth=('api', api_key), params=params)

        if verbose:
            print(f'# {response.request.method} {response.request.url}', file=sys.stderr)
            print(f'# STATUS CODE: {response.status_code}', file=sys.stderr)

        if not response.ok:
            raise ValueError(f'Invalid status_code: {response.status_code}')

        data = response.json()

        items = data['items']
        for record in items:
            yield record

        if items:
            url = data['paging']['next']
            # Paged URLs do not need parameters
            params = None
        else:
            # No more items
            return


def strdate_to_rfc2822(value=None, midnight=False, now=False):
    '''Convert date in format YYYY/MM/DD to RFC2822 format.
        If value is None, return current utc time.
    '''
    if midnight and now:
        raise ValueError('Choose one of "midnight" or "now"')

    strdate =  value if value else datetime.utcnow().strftime('%Y/%m/%d')
    datetimetuple = list(map(int, strdate.split('/')))
    if midnight:
        datetimetuple += (0, 0, 0)
    elif now:
        now =  datetime.utcnow()
        datetimetuple += (now.hour, now.minute, now.second)
    else:
        datetimetuple += (23, 59, 59)

    date = datetime(*datetimetuple)
    timestamp = time.mktime(date.utctimetuple())
    return date.strftime('%a, %d %b %Y %H:%M:%S -0000')


def main():
    parser = argparse.ArgumentParser(description='Retrieve Mailgun event logs.')

    parser.add_argument('-d', '--days', help='Days ago (N)',
                        dest='days',
                        type=int,
                        default=None)

    parser.add_argument('-b', '--begin', help='Begin date (YYYY/MM/DD)',
                        dest='begin',
                        default=None)

    parser.add_argument('-e', '--end', help='End date (YYYY/MM/DD)',
                        dest='end',
                        default=None)

    parser.add_argument('-j', '--json', help='Print json (original) log records',
                        dest='json',
                        action='store_true',
                        default=False)

    parser.add_argument('-v', '--verbose', help='Print debug messages on stderr',
                        dest='verbose',
                        action='store_true',
                        default=False)

    parser.add_argument('-V', '--version', help='Print version to stdout and exit',
                        dest='version',
                        action='store_true',
                        default=False)

    parser.add_argument('domain', help='Domain registered on Mailgun (or set env var MAILGUN_DOMAIN)',
                        metavar='domain',
                        type=str,
                        nargs='?',
                        default=None)

    parser.add_argument('api_key', help='Mailgun API KEY (or set env var MAILGUN_API_KEY)',
                        metavar='api_key',
                        type=str,
                        nargs='?',
                        default=None)

    args = parser.parse_args()

    if args.version:
        from . import __title__, __version__
        print('{0}-{1}'.format(__title__, __version__))
        sys.exit(0)

    jsondata = { 'logs': [] }

    # parse date interval
    if args.days:
        begin_day = _date.today() - relativedelta(days=args.days)
        begin = strdate_to_rfc2822(begin_day.strftime('%Y/%m/%d'), midnight=True)
        end = strdate_to_rfc2822()
    else:
        begin = strdate_to_rfc2822(args.begin, midnight=True) if args.begin else None
        end = strdate_to_rfc2822(args.end, now=True) if args.end else None

    if begin:
        jsondata['begin'] = begin
    if end:
        jsondata['end'] = end

    # parse api domain and credentials
    try:
        if args.domain:
          domain = args.domain
        else:
          domain = os.environ['MAILGUN_DOMAIN']
        jsondata['domain'] = domain
    except KeyError:
        print('Missing mailgun API key')
        sys.exit(1)

    try:
        if args.api_key:
          api_key = args.api_key
        else:
          api_key = os.environ['MAILGUN_API_KEY']
    except KeyError:
        print('Missing mailgun API key')
        sys.exit(1)

    if args.verbose:
        print(f'# BEGIN DATE: {begin}', file=sys.stderr)
        print(f'# END DATE: {end}', file=sys.stderr)
        sys.stderr.flush()

    # main loop
    ###########

    for log in logs(domain=domain, api_key=api_key, begin=begin, end=end, verbose=args.verbose):
        if args.json:
            jsondata['logs'].append(log)
        else:
            status = log.get('event', '').upper()
            ok = status in [ 'ACCEPTED', 'DELIVERED' ]
            line = '[%s] %s <%s>' % (datetime.utcfromtimestamp(log.get('timestamp', '')), status , log.get('recipient', ''))
            if not ok:
                line += ' (%s)' % (log.get('delivery-status', {}).get('description', '') or log.get('delivery-status', {}).get('message', ''))
            line += ': %s' % log.get('message', {}).get('headers', {}).get('subject', '')
            print(line)

    if args.json:
        print(json.dumps(jsondata, indent=3))


if __name__ == '__main__':
    main()
