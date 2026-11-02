#######
# findClosures.py
# description : examine the archived pages to find traces of digital migrations
# licence : AGPL + CECILL v3
# author : quentin lobbé - quentin.lobbe@gmail.com
#######

import glob
import os
import sys

from bs4 import BeautifulSoup
from skyblogsUtils import *

####
## Parse the metadata file and set up results file
#### 

print("\n• Parse the metadata file") 

corpus_name = "corpus_random"
corpus_metadata = {}

raw_metadata = open("./corpus_bnf/" + corpus_name + "/" + corpus_name + "_stats.csv",'r')

rows = raw_metadata.readlines()
rows = rows[1:]

for row in rows :
	cell = row.split(';')
	url  = cell[0]
	pseudo = cell[1]
	nb_visite = int(cell[2])
	nb_follow = int(cell[4])
	corpus_metadata[pseudo] = {"url":url,"nb_visite":nb_visite,"nb_follow":nb_follow}

results = open("./corpus_bnf/" + corpus_name + "/" + corpus_name + "_maybe_migration.csv", "w")
results_header = "id\turl\tpseudo\tarchive_id\tmigration\n"
results.write(results_header)

####
## Examine the pages
####

print("\n• Examine the archived pages")

def isCrap(pseudo) :
	# remove possible SEO / Ad / Bot pages
	if (corpus_metadata[pseudo]["nb_visite"] < 10) and (corpus_metadata[pseudo]["nb_follow"] < 3) :
		return True
	else :
		return False

def isMusic(page) :
	# remove music pages
	music_tag_1 = getTagById(page,"ul","switchitem")
	music_tag_2 = getTagByClass(page,"div","skyrock-music")
	if music_tag_1 is not None :
		music_tag_1_txt = htmlToString(music_tag_1)
		if "music blog" in music_tag_1_txt or "blog music" in music_tag_1_txt :
			return True 
		else :
			return False
	elif music_tag_2 is not None :
		return True
	else :
		return False	

terms_in_title_to_be_filtered = ["gagner","download","questionnaire","age","bonne visite","blog","via","prenom","blog music","blog musique","information","vote","votez","design by","habillage","description","concours","gagnez","presentation","prologue","newsletter","bienvenu","sommaire","resume","welcome","commencement","pub","presente"]


def isPresentation(html_title) :
	itIs = False
	title = htmlToString(html_title)
	for term in terms_in_title_to_be_filtered :
		if term in title :
			itIs = True
	return itIs

link_to_be_filtered = ["photo.html","allocine","blinge","video","share-widget","youtu.be","youtube","iframe","pics","quizz","boosterblog","mp3","gif","download","video","actu","quisontmesamis"]

def isLink(url,blog_url) :
	itIs = True
	for marker in link_to_be_filtered :
		if marker in url :
			itIs = False
	if blog_url in url :
		itIs = False		
	return itIs	

migration_terms = ["retrouve","retrouvez","retrouver","termine","terminer","change","changement","changer","fin","finit","ferme","fermer","end","arreter","arrete"]

def containsKeyWords(html_title) :
	title = htmlToString(html_title)
	title_terms = title.split(" ")
	inter = list(set(title_terms) & set(migration_terms))
	if len(inter) > 0 :
		return True
	else :
		return False

def getPostFromArticleItem(div) :
	title = getTagByClass(div,"h2","bloc_title")
	article = getTagByClass(div,"div","text-image-container")
	return (title,article)

def getPostFromArticle(div) :
	title = getTagByClass(div,"h2","article-title")
	article = getTagByClass(div,"div","text-container")
	return (title,article)

def getPostFromBloc(div) :
	title = getTagByClass(div,"h2","bloc_title")
	article = getTagByClass(div,"div","text-container")
	return (title,article)

def getLastPost(page) :
	# get the last post of a given page
	if getTagByClass(page,"div","article_item") is not None :
		# page template n°1
		post = getTagByClass(page,"div","article_item")
		return getPostFromArticleItem(post)
	elif getTagByClass(page,"div","article") is not None :			
		# page template n°2
		post = getTagByClass(page,"div","article")
		return getPostFromArticle(post)
	elif getTagByClass(page,"div","bloc") is not None :		
		# page template n°3
		post = getTagByClass(page,"div","bloc")
		return getPostFromBloc(post)
	else :
		return None			

cpt = 0
cpt_positive = 1

for path_to_last_page in glob.glob(os.path.join("./corpus_bnf/" + corpus_name + "/" + corpus_name + "_last_pages/", '*.html')):

	if (cpt % 500 == 0) :
		print("   ↪ " + str(cpt))

	archive_id = path_to_last_page.split("/")[4]
	pseudo = archive_id.split('_')[0]
	url = corpus_metadata[pseudo]["url"]

	if isCrap(pseudo) :
		# 1. remove crap pages
		continue

	with open(path_to_last_page) as f:

		last_page = f.read()
		soup = BeautifulSoup(last_page, "html.parser")	

		if isMusic(soup) :
			# 2. remove music pages (because I've never found any migration inside)
			continue	

		last_post = getLastPost(soup)

		if last_post is None :
			continue

		title = last_post[0]
		article = last_post[1]

		maybe_migration = False

		if article is not None :
			links = article.find_all('a', href=True)
			if len(links) > 5 :
				continue
			else :
				for a in links:
					if isLink(a["href"],url) :
						# 3. keep articles that contain non-self html links
						maybe_migration = True

		if not maybe_migration and title is not None :
			if containsKeyWords(title) :
				# 5. give a second chance to articles that contains key migration terms inside title
				maybe_migration = True

		if maybe_migration and title is not None :
			if isPresentation(title) :
				# 4. but remove articles that are presentation or prologue articles
				maybe_migration = False	
			if isPresentation(article) :
				# 4. but remove articles that are presentation or prologue articles
				maybe_migration = False				

		if maybe_migration :
			results.write( "R" + str(cpt_positive) + "\t"
				    + url + "\t"
					+ pseudo + "\t"
					+ archive_id + "\t"
					+ "\n")	
			cpt_positive += 1

	cpt += 1

print ("• end")	
sys.exit()
