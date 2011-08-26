import twill.commands as t
from pyquery import PyQuery
import re
import urllib, urllib2
import sys

t.redirect_output("/dev/null")

class AccountBannedError(RuntimeError):
    def __init__(self, message):
        RuntimeError.__init__(self, message)

def logInToReddit(username, password):
    try:
        urllib2.urlopen("http://reddit.com/user/%s" % username).read()
    except urllib2.HTTPError as e:
        if "404" in str(e):
            raise AccountBannedError("User %s has been banned." % username)

    t.go("http://www.reddit.com/")
    t.fv(2, "user", username)
    t.fv(2, "passwd", password)
    t.submit()
    return isLoggedIn()

def isLoggedIn():
    t.go("http://reddit.com/")
    userBar = PyQuery(t.show())(".user").text()
    return not "register" in userBar
    
def changePassword(password, newpassword):
    t.go("http://www.reddit.com/prefs/update/")
    url = "http://www.reddit.com/api/update"
    pc = urllib.urlencode({
        'curpass' : password,
        'email' : '',	
        'id' : '#pref-update',
        'newpass' : newpassword,
        'renderstyle' :	'html',
        'uh' : getModHashFromCurrentPage(),
        'verpass' : newpassword})
        
    headers = {'Cookie' : 'reddit_session=' + getSessionCookie()}
    
    req = urllib2.Request(url, pc, headers)
    response = urllib2.urlopen(req).read()



'''
NameOfSubreddit -> [(Title, URL, RedditURL)]
'''
def pullSubmissions(subredditName):
    html = urllib2.urlopen("http://reddit.com/r/%s" % subredditName).read()
    storyObjects = PyQuery(html)(".entry")
    for storyObject in [storyObjects.eq(i) for i in range(len(storyObjects))]:
        title = storyObject.find("a.title").html()
        url = storyObject.find("a.title").attr.href
        redditURL = storyObject.find("a.comments").attr.href
        
        if redditURL:   # advertisement submissions have no comments page and thus the property is None (NOT TRUE ANYMORE //FIXME)
            yield (title, url, redditURL)
               
def getModHashFromCurrentPage():
    modhashRegex = re.compile("modhash: '([a-zA-z0-9]+)'")
    modHash = modhashRegex.findall(t.show())[0]
    return modHash
    
'''
RedditURL -> (StoryID, VoteHash, ModHash, SubRedditName)
'''    
def getVoteCredentials(redditURL): 
    t.go(redditURL + "/.compact")
    page = PyQuery(t.show())
    voteHash = page(".link").find(".arrow").eq(0).attr.onclick.split("\'")[1]
    storyID = page(".link").attr.class_.split("-")[1]
    modHash = getModHashFromCurrentPage()
    subredditName = redditURL.split("/")[4]

    return (storyID, voteHash, modHash, subredditName)
    
def encodeVoteCredentials(voteCredentials, voteDirection):
    return urllib.urlencode(
            {'dir'  : voteDirection, 
             'id'   : voteCredentials[0],
             'vh'   : voteCredentials[1],
             'uh'   : voteCredentials[2],
             'r'    : voteCredentials[3]})

def encodeCommentCredentials(commentID, text, modHash):
	return urllib.urlencode(
		{"text" : text,
		 "thing_id" : commentID,
		 "uh" : modHash
		})
             
def getSessionCookie():
    return t.browser.cj._cookies['.reddit.com']['/']['reddit_session'].value


'''
UserName -> [CommentID]
'''
def getUserComments(userName):
    html = urllib2.urlopen("http://reddit.com/user/%s/.compact" % userName).read()
    
    if "page not found" in html: # reddit is down
        print html
        return []
        
    PQ = PyQuery(html)
    k = PQ.find(".comment").find("input")

    return k.map(lambda i,x: x.value)

'''
CommentID, String -> SecondsTillNewComment
'''
def comment(commentID, text):
    url = "http://www.reddit.com/api/comment"
    cc = encodeCommentCredentials(commentID, text, getModHashFromCurrentPage())
    headers = {'Cookie' : 'reddit_session=' + getSessionCookie()}
 
    req = urllib2.Request(url, cc, headers)
    response = urllib2.urlopen(req).read()
    if ".error.RATELIMIT" in response:
        rateLimitRegex = re.compile("try again in ([0-9]+) (minute|second|millisecond)")
        k = rateLimitRegex.findall(response)[0]

        delay = int(k[0])
        if k[1]=='minute':
            delay *= 60
        elif k[1] == 'millisecond':
            delay = 1
        return delay
    elif ".error.NO_TEXT" in response:
        raise RuntimeError("No text in comment.")
    
    return 0


		
		
def __vote(encodedCredentials):
    url = "http://www.reddit.com/api/vote"
    vc = encodedCredentials
    headers = {'Cookie' : 'reddit_session=' + getSessionCookie()}
    
    req = urllib2.Request(url, vc, headers)
    response = urllib2.urlopen(req).read()
    
    if response != "{}": # something went wrong
        print response
    
def voteStory(redditURL, direction = 1):
    voteCredentials = getVoteCredentials(redditURL)
    
    vc = encodeVoteCredentials(voteCredentials, direction)
    __vote(vc)

    
def voteComment(commentID, direction = 1):
    t.go("http://reddit.com")
    vc = encodeVoteCredentials((commentID, '', getModHashFromCurrentPage(), ''), direction)
    __vote(vc)
    
