import requests as rq
import time
import os
import argparse
import sys
from tqdm import tqdm

sys.path.insert(1, os.path.join(sys.path[0], '..'))

def collect_data_wayback(website_url,
                         output_dir,
                         start_date,
                         end_date,
                         resume_key='',
                         max_count=1000,
                         chunk_size=100,
                         sleep=3,
                         retries=5):
    '''
    Collect all urls matching a specific domain on the Wayback machine.
    All archived urls between a specified start date and end date are returned in alphabetical order.
    It is important to not overload the API by keeping the chunk_size parameter reasonably low, 
    and waiting for a few seconds between each API call.
    Params:
        website_url (str): the url domain. All urls matching that domain will be searched on the Wayback machine.
        output_dir (str): the path to the file where the retrieved urls are stored.
        start_date (int): results archived from that date will be returned. Format: YYYYMMDD
        end_date (int): results archived up to that date will be returned. Format: YYYYMMDD
        resume_key (str): if not all urls have been returned in the previous iteration, the resume key allows to start from the last url retrieved.
        max_count (int): the maximum number of results to be returned.
        chunk_size (int): the number of results to return per batch.
        sleep (int): waiting time between API calls.
        retries (int): number of retry attempts for failed API calls.
    '''
    if 'http://' in website_url:
        website_url = website_url.replace('http://', '')
    if 'https://' in website_url:
        website_url = website_url.replace('https://', '')
    
    if chunk_size > max_count:
        raise ValueError('Chunk size needs to be smaller than max count.')
    
    unique_articles_set = set()
    url_list = []
    url_template = 'http://web.archive.org/cdx/search/cdx?url=https://www.{domain}&collapse=urlkey&filter=!statuscode:404&showResumeKey=true&matchType=prefix&from={start}&to={end}&limit={chunk}&output=json'
    
    url = url_template.format(domain=website_url, start=start_date, end=end_date, chunk=chunk_size)
    if resume_key:
        url += '&resumeKey=' + resume_key
    
    its = max_count // chunk_size
    progress_bar = tqdm(total=its)
    
    for _ in range(its):
        for attempt in range(retries):
            try:
                result = rq.get(url)
                result.raise_for_status()
                parse_url = result.json()

                if len(parse_url) < 2:
                    print("No more data to fetch.")
                    progress_bar.close()
                    return url_list
                
                # Extracting new resume_key
                new_resume_key = parse_url[-1][0] if parse_url[-1][0] != resume_key else ''
                if not new_resume_key:
                    print("No progress detected with resume key. Exiting loop.")
                    progress_bar.close()
                    return url_list
                
                resume_key = new_resume_key
                for i in range(1, len(parse_url) - 2):
                    orig_url = parse_url[i][2]
                    if parse_url[i][4] != '200':
                        continue
                    if orig_url not in unique_articles_set:
                        url_list.append(orig_url)
                        unique_articles_set.add(orig_url)
                
                # Update URL for the next iteration
                url = url_template.format(domain=website_url, start=start_date, end=end_date, chunk=chunk_size) + '&resumeKey=' + resume_key
                time.sleep(sleep)
                break
            except (rq.RequestException, ValueError) as e:
                if attempt < retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                else:
                    print(f"Failed to fetch data after {retries} attempts. Error: {e}")
                    progress_bar.close()
                    return url_list

        progress_bar.update(1)

    progress_bar.close()
    print('urls count', len(url_list))
    print('Collected %s of the initial number of requested urls' % (round(len(url_list) / max_count, 2)))
    return url_list

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Download articles and images from the Wayback machine.')
    parser.add_argument('--url_domain', type=str, default='factly.in/', 
                        help='The domain to query on the Wayback Machine API. factly.in/, 211check.org/, or pesacheck.org/')
    parser.add_argument('--file_path', type=str, default='dataset/url/factly.txt',
                        help='Path to the file that stores the URLs')
    parser.add_argument('--start_date', type=int, default=20190101,
                        help='Start date for the collection of URLs.')
    parser.add_argument('--end_date', type=int, default=20231231,
                        help='End date for the collection of URLs.')
    parser.add_argument('--max_count', type=int, default=20000,
                        help='Maximum number of URLs to collect.')
    parser.add_argument('--chunk_size', type=int, default=4000,
                        help='Size of each chunk to query the Wayback Machine API.')
    parser.add_argument('--sleep', type=int, default=5,
                        help='Waiting time between two calls of the Wayback machine API.')

    args = parser.parse_args()

    collect_data_wayback(args.url_domain,
                         args.file_path,
                         start_date=args.start_date,
                         end_date=args.end_date,
                         max_count=args.max_count,
                         chunk_size=args.chunk_size,
                         sleep=args.sleep)
