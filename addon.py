# -*- coding: utf-8 -*-

import sys
from urllib.parse import parse_qsl
import json

from resources.lib.kodihelper import KodiHelper

base_url = sys.argv[0]
handle = int(sys.argv[1])
helper = KodiHelper(base_url, handle)

def list_main_pages():
    pages = helper.c.get_page(page_type='/tree')

    for page in pages:
        params = {
            'action': 'list_categories_or_videos',
            'main_path': page['path'],
            'subs': json.dumps(page['subs'])
        }

        art = {
            'thumb': page['image']
        }

        helper.add_item(page['title'], params=params, art=art)

    helper.add_item(helper.language(30011), params={'action': 'list_page', 'dataurl': helper.c.config['dynamicMbApiUrl'] + '/favorites'})
    helper.add_item(helper.language(30007), params={'action': 'search'})
    helper.eod()

def list_categories_or_videos(main_path, subs):
    subc = json.loads(subs)
    # If there is more than one subcategory use list_categories
    if len(subc) > 1:
        list_categories(subs=subs)
    else:
        # If there is only one subcategory go to video listing
        if len(subc) == 1:
            subcat = helper.c.get_path_dataurl(subc[0]['path'])
            if subcat['type'] == 'curated':
                list_featured_categories(dataurl=subcat['dataUrl'])
            else:
                list_page(dataurl=subcat['dataUrl'])
        # If there is no subcategories use main path
        else:
            category = helper.c.get_path_dataurl(main_path)
            if category['type'] == 'curated':
                list_featured_categories(dataurl=category['dataUrl'])
            else:
                list_page(dataurl=category['dataUrl'])

#List genre categories (documentaries, horror etc)
def list_categories(subs):
    for sub in json.loads(subs):
        title = sub['title']

        params = {
            'action': 'list_category_content',
            'path': sub['path']
        }

        helper.add_item(title, params=params)

    helper.eod()

# Poiminnat
def list_featured_categories(dataurl):
    categories = helper.c.parse_page(dataurl=dataurl)
    for i in categories:
        if i.get('title'):
            if 'items' in i.keys():
                # Use larger list of category contents if available
                if 'target' in i.keys() and i['component'] == 'default':
                    title = i['title'].encode('utf-8')
                    params = {
                        'action': 'list_page_target',
                        'target': i['target']['path']
                    }
                else:
                    title = i['title'].encode('utf-8')
                    params = {
                        'action': 'list_page_with_page_data',
                        'page_data': json.dumps(i['items'])
                    }
                helper.add_item(title, params)

            # Lajit in sport category
            if 'targets' in i.keys():
                title = i['title'].encode('utf-8')
                params = {
                    'action': 'list_category_links',
                    'targets': json.dumps(i['targets'])
                }
                helper.add_item(title, params)
    helper.eod()

#List sport category Lajit content (Formula 1, golf etc)
def list_category_links(targets):
    targets = json.loads(targets)

    for target in targets:
        title = target['title'].encode('utf-8')
        url = helper.c.config['dynamicMbApiUrl'] + '/{0}/assets?size=250'.format(target['path'])
        params = {
            'action': 'list_page',
            'dataurl': url
        }
        helper.add_item(title, params)

    helper.eod()

def list_page(dataurl=None, page_data=None, target=None, search_query=None):
    if dataurl:
        page_dict = helper.c.parse_page(dataurl=dataurl)
    elif page_data:
        page_dict = json.loads(page_data)
    elif target:
        page_dict = helper.c.get_target_path(target)
    elif search_query:
        page_dict = helper.c.get_search_data(search_query)

    # if not page_dict:
    #    return False
    # helper.log(page_dict)

    for i in page_dict:
        # Favorites and featured
        # List movies from poiminnat and favorites and sport(Live formula, live sport)
        if i.get('asset'):
            if i['asset']['type'] == 'sport':
                list_event(i['asset'])
            else:
                list_movie(i['asset'])
        # List tvshows when coming from poiminnat -> sub category and favorites
        if i.get('category'):
            list_tvshow(i['category'])

        # Regular
        elif i.get('type') == 'movie':
            list_movie(i)
        elif i.get('type') == 'series':
            # If seasons in data
            if i.get('groups'):
                list_tvshow(i)
            # If season id in data = list_episode
            elif i.get('categoryId'):
                list_episode(i)
            else:
                list_season(i)

        # F1 and sport categories
        elif i.get('type') == 'sport':
            # List folders
            if 'groups' in i.keys():
                list_season(i)
            else:
                list_event(i)

        elif i.get('channel'):
            list_channel(i)

    helper.eod()

def coloring(text, meaning):
    """Return the text wrapped in appropriate color markup."""
    if meaning == 'live':
        color = 'FF03F12F'
    elif meaning == 'upcoming':
        color = 'FFF16C00'

    colored_text = '[COLOR=%s]%s[/COLOR]' % (color, text)

    return colored_text

def list_tvshow(tvshow):
    # If program name is number for example 112
    if isinstance(tvshow['title'], int):
        title = str(tvshow['title'])
    else:
        title = tvshow['title'].encode('utf-8')

    params = {
        'action': 'list_page_with_page_data',
        'page_data': json.dumps(tvshow['groups'])
    }

    info = {
        'mediatype': 'tvshow',
        'title': title,
        'tvshowtitle': title,
        'plot': tvshow.get('description')
    }

    landscape_image = tvshow['images']['landscape'][-1]['url'] if tvshow['images'].get('landscape') else None
    poster_image = tvshow['images']['portrait'][-1]['url'] if tvshow['images'].get('portrait') else None

    art = {
        'fanart': landscape_image,
        'thumb': landscape_image,
        'cover': landscape_image,
        'poster': poster_image
        }

    helper.add_item(title, params, info=info, art=art)

def list_season(season):
    title = season['title'].encode('utf-8')
    url = helper.c.config['dynamicMbApiUrl'] + '/category/{0}/assets?size=250'.format(season['id'])
    params = {
        'action': 'list_page',
        'dataurl': url
    }

    info = {
        'mediatype': 'season',
        'plot': title
    }

    landscape_image = season['images']['landscape'][-1]['url'] if season['images'].get('landscape') else None
    poster_image = season['images']['portrait'][-1]['url'] if season['images'].get('portrait') else None

    art = {
        'fanart': landscape_image,
        'thumb': landscape_image,
        'cover': landscape_image,
        'poster': poster_image
    }

    helper.add_item(title, params, info=info, art=art)

def list_episode(i):
    params = {
        'action': 'play',
        'video_id': i['id']
    }

    landscape_image = i['images']['landscape'][-1]['url'] if i['images'].get('landscape') else None
    poster_image = i['images']['portrait'][-1]['url'] if i['images'].get('portrait') else None

    if i.get('actors'):
        if ', ' in i.get('actors'):
            actors = i.get('actors').split(', ')
        else:
            actors = [i['actors']]
    else:
        actors = []

    video_info = {
        'mediatype': 'episode',
        'title': i.get('subtitle'),
        'tvshowtitle': i.get('title'),
        'season': i.get('season'),
        'episode': i.get('episode'),
        'plot': i.get('description'),
        'cast': actors,
        'director': i.get('director'),
        'duration': i.get('duration'),
        'genre': ', '.join(i['genres']) if i.get('genres') else None
    }

    art = {
        'fanart': landscape_image,
        'thumb': landscape_image,
        'cover': landscape_image,
        'poster': poster_image
    }

    helper.add_item(i.get('subtitle'), params=params, info=video_info, art=art, content='episodes', playable=True)

def list_event(i):
    if helper.c.parse_datetime(event_date=i['liveBroadcastTime']) > helper.c.get_current_time(utc=True):
        event_status = 'upcoming'
        params = {'action': 'noop'}
        playable = False
    else:
        if helper.get_setting('50fps') and i.get('50fps') and i.get('live'):
            video_id = i['50fps']
        else:
            video_id = i['id']

        event_status = 'live'
        params = {
            'action': 'play',
            'video_id': video_id
        }
        playable = True

    list_title = '[B]{0}:[/B] {1}'.format(coloring(helper.c.aslocaltimestr(i['liveBroadcastTime']), event_status), i['subtitle'].encode('utf-8'))

    landscape_image = i['images']['landscape'][-1]['url'] if i['images'].get('landscape') else None
    poster_image = i['images']['portrait'][-1]['url'] if i['images'].get('portrait') else None

    video_info = {
        'mediatype': 'video',
        'title': i.get('subtitle'),
        'tvshowtitle': i.get('title'),
        'plot': i.get('description'),
        'duration': i.get('duration')
    }

    art = {
        'fanart': landscape_image,
        'thumb': landscape_image,
        'cover': landscape_image,
        'poster': poster_image
    }

    helper.add_item(list_title, params=params, info=video_info, art=art, content='videos', playable=playable)

def list_channel(i):
    params = {
        'action': 'play',
        'video_id': i['channel']['id']
    }

    program_info = {
        'mediatype': 'video',
        'title': i['epg'][0]['title'],
        'plot': i['epg'][0].get('description')
    }

    landscape_image = i['epg'][0]['images']['landscape'][-1]['url'] if i['epg'][0].get('images') else None

    channel_art = {
        'fanart': landscape_image,
        'thumb': landscape_image,
        'cover': landscape_image,
        'icon': i['channel']['images']['landscape'][-1]['url'] if i['channel']['images'].get('landscape') else None
    }

    channel_colored = coloring(i['channel']['title'], 'live').encode('utf-8')
    time_colored = coloring(helper.c.parse_datetime(epg_date=i['epg'][0]['epgLiveBroadcastTime']).strftime('%d.%m.%Y %H:%M'), 'live')
    program_title = i['epg'][0]['title'].encode('utf-8')
    list_title = '[B]{0} {1}[/B]: {2}'.format(channel_colored, time_colored, program_title)

    helper.add_item(list_title, params=params, info=program_info, art=channel_art, content='episodes', playable=True)

def list_movie(i):
    params = {
        'action': 'play',
        'video_id': i['id']
    }

    landscape_image = i['images']['landscape'][-1]['url'] if i['images'].get('landscape') else None
    poster_image = i['images']['portrait'][-1]['url'] if i['images'].get('portrait') else None

    if i.get('actors'):
        if ', ' in i.get('actors'):
            actors = i.get('actors').split(', ')
        else:
            actors = [i['actors']]
    else:
        actors = []

    title = i.get('title')
    content = 'movies'
    video_info = {
        'mediatype': 'movie',
        'title': i.get('title'),
        'plot': i.get('description'),
        'cast': actors,
        'country': i.get('productionCountries'),
        'mpaa': i.get('parentalRating'),
        'imdbnumber': i.get('imdbId') if i.get('imdbId') else None,
        'director': i.get('director'),
        'duration': i.get('duration'),
        'year': i.get('productionYear'),
        'genre': ', '.join(i['genres']) if i.get('genres') else None
    }

    art = {
        'fanart': landscape_image,
        'thumb': landscape_image,
        'cover': landscape_image,
        'poster': poster_image
    }

    helper.add_item(title, params=params, info=video_info, art=art, content=content, playable=True)

def search():
    search_query = helper.get_user_input(helper.language(30007))
    if search_query:
        list_page(search_query=search_query)
    else:
        helper.log('No search query provided.')
        return False

def router(paramstring):
    """
    Router function that calls other functions
    depending on the provided paramstring
    :param paramstring: URL encoded plugin paramstring
    :type paramstring: str
    """
    # Parse a URL-encoded paramstring to the dictionary of
    # {<parameter>: <value>} elements
    params = dict(parse_qsl(paramstring))
    # Check the parameters passed to the plugin
    if 'setting' in params:
        if params['setting'] == 'reset_credentials':
            helper.reset_credentials()
    elif 'action' in params:
        if helper.check_for_prerequisites():
            if params['action'] == 'list_categories_or_videos':
                list_categories_or_videos(main_path=params['main_path'], subs=params['subs'])
            elif params['action'] == 'list_category_content':
                subcat = helper.c.get_path_dataurl(params['path'])
                # Poiminnat
                if subcat['type'] == 'curated':
                    list_featured_categories(dataurl=subcat['dataUrl'])
                else:
                    list_page(dataurl=subcat['dataUrl'])
            elif params['action'] == 'list_page':
                list_page(dataurl=params['dataurl'])
            elif params['action'] == 'list_page_target':
                #list_page(dataurl=helper.c.get_target_path(params['target']))
                list_page(target=params['target'])
            elif params['action'] == 'list_page_with_page_data':
                list_page(page_data=params['page_data'])
            elif params['action'] == 'list_category_links':
                list_category_links(targets=params['targets'])
            elif params['action'] == 'play':
                # Play a video from a provided URL.
                helper.play_item(params['video_id'])
            elif params['action'] == 'search':
                search()
    else:
        if helper.check_for_prerequisites():
            try:
                helper.login_process() # Have to trigger login process every time to get new cookie
                # If the plugin is called from Kodi UI without any parameters,
                # display the list of video categories
                list_main_pages()
            except helper.c.CMoreError as error:
                if error.value == 'AUTHENTICATION_FAILED':
                    helper.dialog('ok', helper.language(30006), helper.language(30012))

if __name__ == '__main__':
    # Call the router function and pass the plugin call parameters to it.
    # We use string slicing to trim the leading '?' from the plugin call paramstring
    router(sys.argv[2][1:])
