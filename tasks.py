import yt_dlp
import utils

def search_task(query, limit, noplaylist=True):
    search = {
    'extract_flat': True,
    'skip_download': True,
    'quiet': True,
    'noplaylist': noplaylist,
    }
    with yt_dlp.YoutubeDL(search) as track_search:
        result = track_search.extract_info(f"ytsearch{limit}:{query}", download=False)['entries']
        limit = min(limit, len(result))
        url, title = [], []
        debug_message = f"Got these results for search tasks for the query {query}.\n"
        for i in range(limit):
            if utils.get_link_type(result[i]['url']) not in ["video", "playlist"]:
                continue
            url.append(result[i]['url'])
            title.append(result[i]['title'])
            debug_message += f"{i + 1}. Url: {result[i]['url']}, Title: {result[i]['title']}.\n"

        print(debug_message)
        return list(zip(url, title))


def playlist_task(query):
    search = {
    'extract_flat': True,
    'skip_download': True,
    'quiet': True,
    }
    with yt_dlp.YoutubeDL(search) as track_search:
        result = track_search.extract_info(query, download=False)['entries']
        url, title = [], []
        debug_message = f"Got these results for search tasks for the query {query}.\n"
        for i in range(len(result)):
            if utils.get_link_type(result[i]['url']) not in ["video"]:
                continue
            url.append(result[i]['url'])
            title.append(result[i]['title'])
            debug_message += f"{i + 1}. Url: {result[i]['url']}, Title: {result[i]['title']}.\n"

        print(debug_message)
        return list(zip(url, title))
    

def stream_task(query):
    stream = {
    'extract_flat': False,
    'skip_download': True,
    'quiet': True,
    'noplaylist': True,
    'format': 'bestaudio/best',
    }
    
    with yt_dlp.YoutubeDL(stream) as stream_search:
        info = stream_search.extract_info(query, download=False)
        title = info['title']
        stream_url = info['url']
        
        print(f"Got result {stream_url}, {title} for the query {query} in stream task.")
        return stream_url, title