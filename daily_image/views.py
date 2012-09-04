from daily_image.models import *
from django.shortcuts import render_to_response
from django.template import RequestContext
from django.utils import simplejson
from django.http import HttpResponse
from django.db.models import Q
from django.shortcuts import redirect
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
import datetime, time, cgi, re


def search(request):
    query = request.GET.get('q', None)
    page_range = None
    if query:
        entry_query = get_query(query, ['title', 'caption',])
        results_list = Image.objects.filter(pub_date__isnull=False).filter(entry_query).distinct().order_by('-pub_order')
        paginator = Paginator(results_list, 25) 

        page = request.GET.get('page','')

        try:
            results = paginator.page(page)
            page_range = range(1,paginator.num_pages+1)
        except PageNotAnInteger:
            # If page is not an integer, deliver first page.
            results = paginator.page(1)
            page_range = range(1,paginator.num_pages+1)
        except EmptyPage:
            # If page is out of range (e.g. 9999), deliver last page of results.
            results = paginator.page(paginator.num_pages)
            page_range = range(1,paginator.num_pages+1)

    else:
        results = []

    return render_to_response("search.html", {
        "results": results,
        "query": query, 
        "page_range": page_range,
    }, context_instance=RequestContext(request))


def today(request):
    date = datetime.datetime.today()
    str_date = datetime.datetime.strftime(date,'%F')
    return redirect('/' + str_date)

def dailyImage(request,date=None):
    today = datetime.datetime.today()
    earliest = Image.pub_dates.earliest()

    if date is None:
        date = datetime.datetime.strftime(today,'%F')
    else:
        try: 
	    date = datetime.datetime(*(time.strptime(date, '%Y-%m-%d')[0:6]))
        except:
            msg = "invalid date"
            date = today

    # if date is in the future reset date to today        
    if date > today:
        date = today
        msg = '*** No peeking into the future! ***'

    # if date is too far into the past reset to today
    if date < earliest:
        date = earliest
        msg = "*** This is the earliest available image ***"
    
    # get the prev and next dates as strings
    prev = date - datetime.timedelta(days=1)
    if prev < earliest:
        prev = None
    else:
        prev = datetime.datetime.strftime(prev,'%F')
    next = date + datetime.timedelta(days=1)
    if next > today:
        next = None
    else: 
        next = datetime.datetime.strftime(next,'%F')

    image = ImageForDate(date, today)
    str_date = datetime.datetime.strftime(date,'%F')         

    # just before we pass it back, turn it into a date objects (a date with no time)
    date = datetime.date.fromordinal(date.toordinal())

    try:
        caption_short = re.search("<p>(.*?)</p>", image.caption, re.DOTALL | re.UNICODE).group(1).strip()
    except:
        caption_short = image.caption
    
    if request.GET.get('fmt') == 'json':
        # partial caption :
        json = {'name':image.name, 'more_info':image.more_info,'title':image.title,'caption':caption_short, 'jpg':image.jpg, 'str_date':str_date }
        # full caption:
        #json = {'name':image.name, 'more_info':image.more_info,'title':image.title,'caption':image.ca$
        return HttpResponse(simplejson.dumps(json),  mimetype='application/json')
    
    if not image:
        raise Http404
    return render_to_response('daily_image.html',locals(), context_instance=RequestContext(request))             
                 
         
# takes date as date object, returns query object
# if no date is set for date find next image to publish
def ImageForDate(date = datetime.datetime.today(), today = datetime.datetime.today()):
    
    earliest = Image.pub_dates.earliest()
    
    # don't go setting image for the past.. 
    if date < earliest:
        date = today
        
    # see if an image has already been set this day    
    try:
        image = Image.objects.get(pub_date=date)
    except:
        # an image for today hasn't been set, find next image to publish:
        image = Image.objects.filter(pub_date=None).order_by('pub_order')[0]
        # and set its pub_date to this day
        Image.objects.filter(name=image.name).update(pub_date=date)
        
    return image     
    
 
# takes an image object
def getTweet(image):
    tweet_text = ''.join(html2safehtml(image.caption.split('.')[0], valid_tags=()).split("\n")).strip()
    tweet_text = tweet_text.strip(',')

    sample_url = 'http://is.gd/ggapu'
    # the tweet text can be 140 minus the url and title length 
    # and spaces after each 
    tweet = image.title.strip() + ': ' + tweet_text.strip()
    tweet_length = len(tweet) + 1 + len(sample_url)

    if (tweet_length > 140):
        # this tweet will be to long so need to trim it.

        # this is how long the tweet can be: 
        max_length = 140-3 # since we are trimming make room for 2 ellipses: .. 
        while (tweet_length > max_length):
            tweet_arr = tweet.split(' ')
            tweet_arr.pop()
            tweet = ' '.join(tweet_arr).strip(' ') # pop off the last word
            tweet = tweet.strip(',') 
            tweet_length = len(tweet) + 1 + len(sample_url)

        tweet = tweet + '..'
    
    return tweet



"""
next are via http://julienphalip.com/post/2825034077/adding-search-to-a-django-site-in-a-snap
"""
def normalize_query(query_string,
                    findterms=re.compile(r'"([^"]+)"|(\S+)').findall,
                    normspace=re.compile(r'\s{2,}').sub):
    ''' Splits the query string in invidual keywords, getting rid of unecessary spaces
        and grouping quoted words together.
        Example:
        
        >>> normalize_query('  some random  words "with   quotes  " and   spaces')
        ['some', 'random', 'words', 'with quotes', 'and', 'spaces']
    
    '''
    return [normspace(' ', (t[0] or t[1]).strip()) for t in findterms(query_string)] 

def get_query(query_string, search_fields):
    ''' Returns a query, that is a combination of Q objects. That combination
        aims to search keywords within a model by testing the given search fields.
    
    '''
    query = None # Query to search for every search term        
    terms = normalize_query(query_string)

    for term in terms:
        or_query = None # Query to search for a given term in each field
        for field_name in search_fields:
            q = Q(**{"%s__icontains" % field_name: term})
            if or_query is None:
                or_query = q
            else:
                or_query = or_query | q
        if query is None:
            query = or_query
        else:
            query = query & or_query
    return query
