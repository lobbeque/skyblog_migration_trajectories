#######
# fansToEgoNetworks.py
# description : change a list of fans and fans of fans into ego networks
# licence : AGPL + CECILL v3
# author : quentin lobbé - quentin.lobbe@gmail.com
#######

import os
import sys
import networkx as nx
import pickle
from collections import defaultdict

# note : we filter lequipe-Skyrock and difool as they are massive relashionships attractors
#        we also filter the children of ego from the alters 1 & 2

####
## Functions
#### 

def saveGraph(ego,g):
	with open(ego + ".pkl","wb") as f:
		pickle.dump(g,f)
		nx.write_graphml(g, ego + ".graphml")

def loadGraph(ego):
	with open(ego + ".pkl","rb") as f:
		g = pickle.load(f)
		return g	

def intersect(l1,l2) :
	inter = list(set(l1).intersection(set(l2)))
	return len(inter) > 0		

def initGraph(ego):
	g = nx.DiGraph()
	g.graph["name"] = ego + "'s ego network"
	g.graph["status"] = {"ego":True,"alter_1":False,"alter_2":False,"pruned":False}
	progress[ego] = True
	g.add_node(ego,depth="ego",archived="1")
	return g

def checkProgress(ego,status):
	path = ego + ".pkl"
	if os.path.isfile(path) :
		with open(path, "rb") as f:
			g = pickle.load(f)
			return g.graph[status]
	else :
		return False

####
## Parse the file of mugration traces
#### 

data = open("../analyse traces migratoires/corpus_loups_migration_edges.csv",'r')
rows = data.readlines()

map_trace_to_blogs = defaultdict(list)
map_blog_to_trace  = {}

def getPseudo(url) :
	pseudo = url.replace("http://","").replace("https://","").replace("www.","").split('.')[0].lower()
	return pseudo

for row in rows :
	row = row.replace('\n','').split('\t')
	b1 = getPseudo(row[2])
	b2 = getPseudo(row[7])
	trace_id = row[0]
	if b1 not in map_trace_to_blogs[trace_id] :
		map_trace_to_blogs[trace_id].append(b1)
	if b2 not in map_trace_to_blogs[trace_id] :
		map_trace_to_blogs[trace_id].append(b2)
	map_blog_to_trace[b1] = trace_id
	map_blog_to_trace[b2] = trace_id

####
## Parse the list of fans
#### 

print("\n• Parse the list of fans") 	

data = open("./blogs_fans",'r')
rows = data.readlines()
egos = {}

# init the process	

for row in rows :
	row = row.replace('\n','').split(' ')
	ego = row[0]
	if ego not in egos.keys() :
		egos[ego] = [row]
	else :
		egos[ego].append(row)

####
## Create the alter 1 networks
#### 

print("\n• Create the alter 1 networks") 

for ego in egos.keys() :

	# if checkProgress(ego,"alter 1") :
	# 	print("   ✓ " + ego + " network already created")
	# 	continue	
	
	print("   ↪ process " + ego + " network")
	
	ego_g = nx.DiGraph()
	ego_g.graph["name"] = ego + "'s ego network"
	chaine_id = map_blog_to_trace[ego.lower()]
	ego_g.graph["chaine"] = chaine_id
	ego_g.add_node(ego,depth="ego",archived="1")

	for row in egos[ego] :

		# add alter nodes and edges
		
		alter = row[1]		
		mutual = bool(int(row[3]))
		archived = row[4]

		if intersect([ego,alter],["difool","lequipe-Skyrock"]) :
			continue
		if alter.lower() in map_trace_to_blogs[chaine_id] :
			continue

		ego_g.add_node(alter,depth="alter 1",archived=archived)
		ego_g.add_edge(alter,ego,origin="archived")

		if mutual :
			ego_g.add_edge(ego,alter,origin="archived")

	ego_g.graph["alter 1"] = True
	saveGraph(ego,ego_g)
	print("     ✓ created")

####
## Parse the list of fans of fans
#### 

print("\n• Parse the list of fans of fans") 

# init the process	

data = open("./blogs_fans_fans",'r')
rows = data.readlines()	
egos = {}

if os.path.isfile("fans_fans.pkl") :
	with open("fans_fans.pkl", "rb") as f:
		egos = pickle.load(f)
else :
	for row in rows :
		row = row.replace('\n','').split(' ')
		ego = row[0] 
		if ego not in egos.keys() :
			egos[ego] = {}
		alter_1 = row[1]
		alter_2 = row[5]
		new_row = [alter_1,alter_2,row[6],row[7],row[8]]
		if intersect([ego,alter_1,alter_2],["difool","lequipe-Skyrock"]) :
				continue	
		if alter_1 not in egos[ego].keys() :
			egos[ego][alter_1] = [new_row]
		else :
			egos[ego][alter_1].append(new_row)
	with open("fans_fans.pkl","wb") as f:
		pickle.dump(egos,f)

####
## Create the alter 2 networks
#### 

print("\n• Create the alter 2 networks") 		

for ego in egos.keys() :

	# if checkProgress(ego,"alter 2") :
	# 	print("   ✓ " + ego + " network already updated")
	# 	continue	
	
	print("   ↪ update " + ego + " network")
	
	ego_g = loadGraph(ego)
	chaine_id = map_blog_to_trace[ego.lower()]

	for alter_1 in egos[ego].keys() :

		if alter_1.lower() in map_trace_to_blogs[chaine_id] :
			continue
		
		for row in egos[ego][alter_1] :	
			
			# add alter nodes and edges
			alter_2 = row[1]		
			mutual = bool(int(row[3]))
			archived = row[4]	

			if not ego_g.has_node(alter_2) : 		
				ego_g.add_node(alter_2,depth="alter 2",archived=archived)

			if alter_2 == alter_1 :
				continue

			if alter_2.lower() in map_trace_to_blogs[chaine_id] :
				continue					
			
			ego_g.add_edge(alter_2,alter_1,origin="archived")

			if mutual and not ego_g.has_edge(alter_1,alter_2) :
				ego_g.add_edge(alter_1,alter_2,origin="archived")

	ego_g.graph["alter 2"] = True
	saveGraph(ego,ego_g)
	print("     ✓ updated")

####
## Filter the entire ego networks
#### 

print("\n•Filter the entire ego networks") 

for ego in egos.keys() : 

	print("   ↪ filter " + ego + " network")
	ego_g = loadGraph(ego)

	nodes_to_remove = []

	for alter, metadata in ego_g.nodes(data=True):
 
		if metadata.get("depth") != "alter 2":
		    continue

		neighbors = list(set(ego_g.predecessors(alter)) | set(ego_g.successors(alter)))

		if (len(neighbors)) == 1 and (ego_g.nodes[neighbors[0]].get("depth") == "alter 1") :
			# remove leaf
			nodes_to_remove.append(alter)
		if (len(neighbors)) == 2 and (ego_g.nodes[neighbors[0]].get("depth") == "alter 1") and (ego_g.nodes[neighbors[1]].get("depth") == "alter 1") :
			# remove false hub
			nodes_to_remove.append(alter)			

	ego_g.remove_nodes_from(nodes_to_remove)
	isolated = list(nx.isolates(ego_g))
	ego_g.remove_nodes_from(isolated)
	ego_g.graph["pruned"] = True
	saveGraph(ego,ego_g)
	print("     ✓ filtered")	