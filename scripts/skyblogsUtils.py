#######
# skyblogsUtils.py
# description : functions for parsing skyblogs web archives
# licence : AGPL + CECILL v3
# author : quentin lobbé - quentin.lobbe@gmail.com
#######

import sys
import datetime
import urllib.request
import json
import time

from bs4 import BeautifulSoup
from unidecode import unidecode

def stringToDate(date_str) :
	# turn a string date into a datetime object
	prefix = date_str.split('T')[0]
	date = datetime.datetime.strptime(prefix,'%Y-%m-%d')
	return date

def stringToDateAlt(date_str) :
	# turn a string date into a datetime object (alternative format)
	prefix = date_str.split(' ')[0]
	date = datetime.datetime.strptime(prefix,'%Y-%m-%d')
	return date	

def dateToString(date_obj) :
	# turn a date into a string
	date_str = date_obj.strftime("%Y-%m-%d")
	return date_str	

def diff_month(d1, d2):
	# difference between two dates in months
	return (d1.year - d2.year) * 12 + d1.month - d2.month	

def htmlToString(html_txt) :
	# get a normalized string from a wild html text
	if html_txt is not None :
		txt = html_txt.getText()
		txt = unidecode(txt)
		txt = txt.lower()
		return txt
	else :
		return ""

def getTagById(div,html_tag,css_id) :
	# get html tag by id
	html_content = div.find(html_tag, {"id":css_id})
	return html_content	

def getTagByClass(div,html_tag,css_class) :
	# get first html tag by class 
	html_content = div.find_all(html_tag, {"class":css_class})
	if len(html_content) > 0 :
		return html_content[0]
	else :
		return None

def browseCDX(query) :
	# browse the pages returned by the cdx server
	next = True
	rows = []
	resumeKey = None
	while next :
		if resumeKey is None :
			raw_data = httpRequest(query)
		else :
			raw_data = httpRequest(query + "&resumeKey=" + resumeKey)
		if (raw_data is None or raw_data == "") :
			next = False
		else :
			data = json.loads(raw_data.decode("utf-8"))
			if len(data) == 0 :
				next = False
			else :
				if len(data[-1]) == 1 :
					resumeKey = data[-1][0]
					next = True
					data = data[:-2]
				else :
					next = False
				rows = rows + data[1:]
	if len(rows) == 0 :
		print("  ! something went wrong")
	return rows	

def httpRequest(url,attempt=1) :
	# sent http requests
	data = None
	try :
		req = urllib.request.Request(url)
		with urllib.request.urlopen(req) as res:
			data = res.read()
			res.close()
	except Exception as e :
		print(str(e))
	if data is None or data == "" :
		if attempt <= 2 :
			# try again, there might be an issue with the network
			httpRequest(url,attempt + 1)
		else :
			return None
	else :
		return data	 

def isArchived(url,second_try=True) :
	# search if a given url has been archived
	query = "http://web.archive.org/cdx/search/cdx?url=" + url + "&output=json"
	raw_data = httpRequest(query)
	if (raw_data is None or len(raw_data) == 0) :
		if second_try :
			isArchived(url,False)
		else :
			return False
	else :
		data = json.loads(raw_data.decode("utf-8"))
		if (len(data) == 0) :
			if second_try :
				isArchived(url,False)
			else :
				return False
		else :
			return True		

def getLastSnapshot(provider,url) :
	# get the last archived snapshot of a given url
	snapshot = None
	if   provider == "bnf" :
		print ("! BnF provider not implemented -- skyblogsUtils.py \n")
		sys.exit(0)			
	elif provider == "cdx" :
		query = "http://web.archive.org/cdx/search/cdx?url=" + url + "&output=json&showResumeKey=true&limit=50"
		data = browseCDX(query)
		data.reverse()
		for row in data :
			if (row[3] == "text/html") and (row[4] == "200") :
				snapshot = row
				break
		return snapshot
	else :
		print ("! " + provider +  " provider didn't exist -- skyblogsUtils.py \n")
		sys.exit(0)	