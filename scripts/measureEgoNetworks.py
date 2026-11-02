#######
# measureEgoNetworks.py
# description : compute a set of metrics from ego networks
# licence : AGPL + CECILL v3
# author : quentin lobbé - quentin.lobbe@gmail.com
#######

import graph_tool.all as gt
import networkx as nx
from networkx.algorithms import community
import pickle
import numpy as np
from collections import defaultdict
from kneed import KneeLocator,find_shape
import multiprocessing as mp
from tqdm import tqdm
from tabulate import tabulate
import os
import pandas as pd
import sys
import math

####
## Functions
#### 

def loadGraph(ego):
	with open(ego + ".pkl","rb") as f:
		g_nx = pickle.load(f)
		return g_nx	

def saveGraph(ego,g):
	with open(ego + ".pkl","wb") as f:
		pickle.dump(g,f)	
		nx.write_graphml(g, ego + ".graphml")	

####
## Parse the files
#### 

print("\n• Parse the files") 	

data = open("./blogs_fans",'r')
rows = data.readlines()

map_egos_and_attr = {}
map_graphs_and_unknowns = {}

# --- Step 0 : we map egos and attributes

for row in rows :
	row = row.replace('\n','').split(' ')
	ego = row[0].lower()
	if ego not in map_egos_and_attr.keys() :
		map_egos_and_attr[ego] = {"raw_ego":row[0]}

data = open("../analyse traces migratoires/corpus_loups_migration_edges.csv",'r')
rows = data.readlines()

def getPseudo(url) :
	pseudo = url.replace("http://","").replace("https://","").replace("www.","").split('.')[0].lower()
	return pseudo

for row in rows :
	row = row.replace('\n','').split('\t')
	ego = getPseudo(row[2])
	if ego in map_egos_and_attr.keys() :
		map_egos_and_attr[ego]["trace"] = row[0]
		map_egos_and_attr[ego]["id"] = row[1]
		map_egos_and_attr[ego]["type"] = row[5]
		map_egos_and_attr[ego]["year"] = int((row[4]).split('/')[2])

map_egos_and_attr = {k: v for k, v in map_egos_and_attr.items() if "id" in v}

# --- Step 1 : we create a map of tuples (graph,unknown nodes)

for ego,val in map_egos_and_attr.items() :
	g_nx = loadGraph(val["raw_ego"])
	unknown_nodes = []
	for node,attr in g_nx.nodes(data=True):
		if attr.get("archived") == "0" :
			unknown_nodes.append(node)
	unknown_ratio = (len(unknown_nodes) * 100) / len(g_nx.nodes(data=True))
	unknown_ratio = "{:.2f}".format(unknown_ratio)
	map_egos_and_attr[ego]["nb_nodes"] = len(g_nx.nodes(data=True))
	map_egos_and_attr[ego]["nb_unknowns"] = len(unknown_nodes)
	map_egos_and_attr[ego]["unknown_ratio"] = unknown_ratio
	map_graphs_and_unknowns[ego] = (g_nx,unknown_nodes)

####
## Read ego depths 
#### 

def read_ego_depths(g_nx):

	depth = {}
	ego_node = None

	for node, attrs in g_nx.nodes(data=True):
		d = attrs.get("depth")
		depth[node] = d
		if d == "ego":
			ego_node = node

	n0 = sum(1 for v in depth.values() if v == "ego")
	n1 = sum(1 for v in depth.values() if v == "alter 1")
	n2 = sum(1 for v in depth.values() if v == "alter 2")
	print(f"\t → depths : {n0} ego | {n1} alters-1 | {n2} alters-2")

	return depth, ego_node

####
## Conversion NetworkX → graph-tool
#### 

def nx_to_gt(g_nx):

	g_gt = gt.Graph(directed=True)
	g_gt.add_vertex(g_nx.number_of_nodes())

	map_nx_to_gt = {node: i for i, node in enumerate(g_nx.nodes())}
	map_gt_to_nx = {i: node for node, i in map_nx_to_gt.items()}

	for u, v in g_nx.edges():
		g_gt.add_edge(map_nx_to_gt[u], map_nx_to_gt[v])

	return g_gt, map_nx_to_gt, map_gt_to_nx

####
## Fit the DC-SBM
#### 

def fit_best_dcsbm(g_gt, n_init, n_sweep):

	best_state = None
	best_dl = np.inf

	for _ in tqdm(range(n_init)):
		state = gt.minimize_blockmodel_dl(
			g_gt,
			state_args=dict(deg_corr=True),
			multilevel_mcmc_args=dict(niter=n_sweep,verbose=False))

		dl = state.entropy()
		if dl < best_dl:
			best_dl = dl
			best_state = state.copy()

	print(f"\t → Best description length : {best_dl:.2f}")
	print(f"\t → Number of blocks : {best_state.get_nonempty_B()}")
	return best_state

def fit_best_dcsbm_optimized(g_gt,n_init,n_sweep):

	import gc

	best_state = None
	best_dl = np.inf
	no_improve_count = 0
	patience = max(2, n_init // 4)

	for i in tqdm(range(n_init)):

		state = gt.minimize_blockmodel_dl(
			g_gt,
			state_args=dict(deg_corr=True),
			multilevel_mcmc_args=dict(
				niter=n_sweep,
				verbose=False,
				B_min=2,				
				entropy_args=dict(dl=True, partition_dl=True)
			)
		)

		dl = state.entropy()

		if dl < best_dl:
			best_dl = dl
			
			del best_state
			best_state = state.copy()
			no_improve_count = 0
		else:
			no_improve_count += 1
			del state 
			gc.collect()

		if no_improve_count >= patience:
			print(f"\t → Stop at run {i+1}/{n_init} (no amelioration sinc {patience} runs)")
			break
	print(f"\t → Converging toward best state...")
	for _ in range(100):
		best_state.multiflip_mcmc_sweep(beta=np.inf, niter=10)

	dl_final = best_state.entropy()
	print(f"\t → Best description length : {dl_final:.2f}")
	print(f"\t → Number of blocks : {best_state.get_nonempty_B()}")
	return best_state	


####
## Compute structural metrics
#### 

def computeBridging(g,g_un):

	# Hwang, et al. "Bridging centrality: graph mining from element level to group level." 
	# Proceedings of the 14th ACM SIGKDD international conference on Knowledge discovery and data mining. 2008.

	betweenness = nx.betweenness_centrality(g,normalized=True)
	bridging = {}
	
	for n in g_un.nodes():
		
		deg = g_un.degree(n)
		neighbors = list(g_un.neighbors(n))

		if deg == 0 or not neighbors:
			bridging[n] = 0.0
			continue

		inv_deg = 1/deg
		sum_inv_deg_neigh = sum(1/g_un.degree(u) for u in neighbors if g_un.degree(u) > 0)

		if sum_inv_deg_neigh == 0:
			bridging_coeff = 0
		else:
			bridging_coeff = inv_deg / sum_inv_deg_neigh

		bridging[n] = float(betweenness[n] * bridging_coeff)

	return bridging

def compute_metrics(g_ego,ego_node) :

	metrics = {}

	# alter graph (without ego)
	g_alter = g_ego.copy()
	if ego_node in g_alter:
		g_alter.remove_node(ego_node)
	
	# undirected alter graph 
	g_alter_un = g_alter.to_undirected()

	# undirected ego graph
	g_ego_un = g_ego.to_undirected()

	# largest connected component of ego graph
	sccs  = list(nx.strongly_connected_components(g_alter))
	largest_scc = max(sccs, key=len) if sccs else set()
	g_alter_lscc = g_alter.subgraph(largest_scc)

	# --- 1. density
	# computed on g_alter
	metrics["density"] = nx.density(g_alter)

	# --- 2. diameter
	# as g_ego is oriented, the diameter is computed on g_alter_lscc
	if len(g_alter_lscc) > 1 :
		metrics["diameter"] = nx.diameter(g_alter_lscc)
	else :
		metrics["diameter"] = 0

	# --- 3. modularity
	# computed on g_alter_un
	try :
		communities = nx.community.greedy_modularity_communities(g_alter_un)
		metrics["modularity"] = nx.community.modularity(g_alter_un, communities)
	except Exception as e :
		metrics["modularity"] = 0.0
	
	# --- 4. transitivity (ratio of triangles)
	# computed on g_alter_un
	metrics["triangles"] = nx.transitivity(g_alter_un)

	# --- 5. reciprocity
	# computed on g_alter
	try :
		metrics["reciprocity"] = nx.overall_reciprocity(g_alter)
	except Exception as e :
		metrics["reciprocity"] = 0.0

	# --- 6. betweenness centrality
	# computed on g_alter
	betweenness = list(nx.betweenness_centrality(g_alter, normalized=True).values())
	metrics["betweenness_avg"] = float(np.mean(betweenness))
	metrics["betweenness_max"] = float(np.max(betweenness))

	# --- 7. average clustering
	# computed on g_alter_un
	metrics["clustering_mean"] = nx.average_clustering(g_alter_un)

	# --- 8. bridging centrality
	# computed on g_alter and g_alter_un
	bridging = list(computeBridging(g_alter,g_alter_un).values())
	metrics["bridging_avg"] = float(np.mean(bridging))
	metrics["bridging_max"] = float(np.max(bridging))	

	# --- 9. edge betweenness
	# computed on g_alter
	try :
		edge_betweenness = list(nx.edge_betweenness_centrality(g_alter, normalized=True).values())
		metrics["edge_betweenness_avg"] = float(np.mean(edge_betweenness))
		metrics["edge_betweenness_max"] = float(np.max(edge_betweenness))
	except Exception as e :
		metrics["edge_betweenness_avg"] = 0.0
		metrics["edge_betweenness_max"] = 0.0

	table = tabulate(metrics.items(), headers=["Metric", "Value"], floatfmt=".4f")
	indented = "\n".join("\t   " + line for line in table.splitlines())
	print(indented)

	return metrics	

####
## Reconstruction process
#### 

def getBlock(v,state) :
	return int(state.get_blocks()[int(v)])

def getInterBlockEdges(state,b1,b2) :
	blocks = state.get_blocks()
	meta_g = state.g
	return sum(
		1 for e in meta_g.edges()
		if int(blocks[int(e.source())]) == b1 and int(blocks[int(e.target())]) == b2)	
import numpy as np


def findElbow(intensity):

	# https://en.wikipedia.org/wiki/Knee_of_a_curve
	# the intuition is that, in the sorted distribution of intensity, there are a few high scores at 
	# the start of the distribution, followed by a long tail of low scores that are broadly similar  

	intensity = np.asarray(intensity, dtype=float)
	d1 = intensity[:-1] - intensity[1:]
	d2 = d1[:-1] - d1[1:]
	elbow_index = np.argmax(d2) + 1

	return elbow_index

def findElbow2(intensity) :

	# Finding a “Kneedle” in a Haystack: Detecting Knee Points in System Behavior
	# https://ieeexplore.ieee.org/abstract/document/5961514
	# the intuition is that, in the sorted distribution of intensity, there are a few high scores at 
	# the start of the distribution, followed by a long tail of low scores that are broadly similar  

	idx = np.arange(len(intensity))
	_,curve = find_shape(idx,intensity)
	kneedle = KneeLocator(idx,intensity,curve=curve,direction="decreasing")

	return kneedle.knee


def reconstruct_unknown_edges(ego,g_nx,g_gt,state,unknowns_nx,unknowns_gt,map_gt_to_nx) :

	# https://www.sciencedirect.com/science/article/abs/pii/S037843711300811X
	# poisson edge rate <=> expected edge intensity

	# --- 1. map nodes' in & out degrees

	map_node_to_in_degree  = {int(v): v.in_degree()  for v in g_gt.vertices()}
	map_node_to_out_degree = {int(v): v.out_degree() for v in g_gt.vertices()}

	# --- 2. map nodes to block
	
	map_node_gt_to_block = {int(v): getBlock(v,state) for v in g_gt.vertices()}
	map_node_nx_to_block = {map_gt_to_nx[int(v)]: getBlock(v,state) for v in g_gt.vertices()}

	nx.set_node_attributes(g_nx,map_node_nx_to_block,name="block")
	
	# --- 3. connectivity between blocks

	blocks = list(set(map_node_gt_to_block.values()))
	inter_block_edges = defaultdict(int)
	
	for bi in blocks :
		for bj in blocks :
			inter_block_edges[(bi,bj)] = getInterBlockEdges(state,bi,bj)

	# --- 4. map blocks' in & out degrees	

	map_block_to_in_degree  = defaultdict(int)
	map_block_to_out_degree = defaultdict(int)
	map_block_to_nodes = defaultdict(list)

	for v in g_gt.vertices() :
		block = map_node_gt_to_block[int(v)]
		map_block_to_nodes[block].append(int(v))
		map_block_to_in_degree[block]  += v.in_degree()
		map_block_to_out_degree[block] += v.out_degree()

	# --- 5. we compute Ⲗij : the intensity score for each pair of unknown nodes 	

	intensity = defaultdict(float)

	for i in unknowns_gt :
		bi = map_node_gt_to_block[i]
		for j in unknowns_gt :
			if i == j :
				continue
			bj = map_node_gt_to_block[j]
			edges_bi_bj = inter_block_edges[(bi,bj)]
			deg_out_i = map_node_to_out_degree[i]
			deg_in_j  = map_node_to_in_degree[j]
			deg_out_bi = map_block_to_out_degree[bi]
			deg_in_bj  = map_block_to_in_degree[bj]
			if edges_bi_bj == 0 or deg_out_i == 0 or deg_in_j == 0 or deg_out_bi == 0 or deg_in_bj == 0:
				continue
			else :
				Ⲗij = (deg_out_i * deg_in_j * edges_bi_bj) / ((deg_out_bi ** 2) * (deg_in_bj ** 2))
				intensity[(i,j)] = Ⲗij
	
	intensity = dict(sorted(intensity.items(), key=lambda item: item[1], reverse=True))

	# --- 6. we search for the elbow point in the sorted distribution of intensity 

	if len(intensity.keys()) > 3 :
		idx = findElbow(list(intensity.values()))
		missing_edges = list(intensity.keys())[:(idx + 1)]
	else :
		missing_edges = list(intensity.keys())

	for edge_gt in missing_edges :
		if not g_nx.has_edge(map_gt_to_nx[edge_gt[0]],map_gt_to_nx[edge_gt[1]]) :
			g_nx.add_edge(map_gt_to_nx[edge_gt[0]],map_gt_to_nx[edge_gt[1]],origin="reconstructed")	

	print(f"\t → Reconstruct {len(missing_edges)} unknown edges")

	saveGraph(ego + "_reconstructed",g_nx)

	return g_nx, blocks, map_block_to_nodes


print("\n• Run the structural analysis")

def reconstruct_and_analyse(graph_name,g_nx,unknowns_nx,n_init=10,n_sweep=10) :

	# --- Step 1 : read depths from the “depth” attribute
	print("\t[1/5] Read depths from the “depth” attribute")
	depths, ego_node = read_ego_depths(g_nx)	

	if os.path.isfile(graph_name + "_reconstructed.pkl") :
		with open(graph_name + "_reconstructed.pkl","rb") as f:
			g_nx_reconstructed = pickle.load(f)
			block_to_nodes = defaultdict(list)
			for node, data in g_nx_reconstructed.nodes(data=True):
				block_to_nodes[data["block"]].append(node)
			blocks = list(set(block_to_nodes.keys()))
			print("\t → Load an existing reconstructed graph and jump to step n°5")
	else :
		# --- Step 2 : Conversion NetworkX → graph-tool ---
		print("\t[2/5] Conversion NetworkX → graph-tool")
		g_gt, map_nx_to_gt, map_gt_to_nx = nx_to_gt(g_nx)	

		# --- Step 3 : Fit the DC-SBM ---
		print(f"\t[3/5] Fit the DC-SBM ({n_init} initialisations, {n_sweep} sweeps MCMC)")
		if (len(map_nx_to_gt.keys()) > 1000) :
			state = fit_best_dcsbm_optimized(g_gt, n_init=n_init, n_sweep=n_sweep)
		else :
			state = fit_best_dcsbm(g_gt, n_init=n_init, n_sweep=n_sweep)

		# --- Step 4 : Reconstruct unknown edges ---
		print("\t[4/5] Reconstruct unknown edges from the DC-SBM")
		unknowns_gt = set([map_nx_to_gt[u] for u in unknowns_nx])
		g_nx_reconstructed, blocks, block_to_nodes = reconstruct_unknown_edges(graph_name, g_nx, g_gt, state, unknowns_nx, unknowns_gt, map_gt_to_nx)

	# --- Step 5 : Compute metrics on reconstructed ego-network ---
	print("\t[5/5] Compute metrics on reconstructed ego-network")

	# if os.path.isfile(graph_name + "_metrics.pkl") :
	# 	with open(graph_name + "_metrics.pkl","rb") as f:
	# 		metrics = pickle.load(f)
	# 		print("\t → Load an existing metrics file")
	# else :
	metrics = compute_metrics(g_nx_reconstructed,ego_node)
	metrics["nb_blocks"] = len(blocks)
	metrics["nb_blocks_sup_3"] = sum(1 for v in block_to_nodes.values() if len(v) > 3)
	metrics["nb_blocks_inf_3"] = len(blocks) - metrics["nb_blocks_sup_3"]
	metrics["size_biggest_block"] = max(len(v) for v in block_to_nodes.values())
	metrics["name"]  = graph_name
	metrics["trace"] = map_egos_and_attr[graph_name]["trace"]
	metrics["id"]	= map_egos_and_attr[graph_name]["id"]
	metrics["type"]  = map_egos_and_attr[graph_name]["type"]
	metrics["year"]  = map_egos_and_attr[graph_name]["year"]
	metrics["nb_nodes"] = map_egos_and_attr[graph_name]["nb_nodes"]
	metrics["unknown_ratio"] = map_egos_and_attr[graph_name]["unknown_ratio"]	

	with open(graph_name + "_metrics.pkl","wb") as f:
		pickle.dump(metrics,f)		
			
	return metrics

####
## Main loop
#### 

def getSubGraph(g_nx, sup=2000) :
    top_nodes = set(node for node, _ in sorted(g_nx.degree(), key=lambda x: x[1], reverse=True)[:sup])
    return g_nx.subgraph(top_nodes).copy()

observations = []
egos = list(map_graphs_and_unknowns.keys())
graphs_and_unknowns = list(map_graphs_and_unknowns.values())
nb_graphs = len(graphs_and_unknowns)

for i, (g_nx,unknown_nodes) in enumerate(graphs_and_unknowns):

	# if i < 57 :
	# 	continue
	
	graph_name = egos[i]

	print(f"\n   ↪ [{i+1}/{nb_graphs}] {graph_name} "
		  f"({g_nx.number_of_nodes()} nodes, {g_nx.number_of_edges()} edges, "
		  f"{(len(unknown_nodes) / g_nx.number_of_nodes()) * 100:.1f}% of unknown nodes)")

	if g_nx.number_of_nodes() > 2000 :
		print(f"\t !! Graph is too big")
		g_nx = getSubGraph(g_nx)
		unknown_nodes = [n for n in unknown_nodes if n in g_nx]
		print(f"\t ↪  Filter it until {g_nx.number_of_nodes()} nodes and {len(unknown_nodes)} unknowns and {g_nx.number_of_edges()} edges.")

	metrics = reconstruct_and_analyse(graph_name,g_nx,unknown_nodes)
	observations.append(metrics)

	# if i > 3 :
	# 	break

print("\n• Structural analysis done") 	

with open("structural_observations.pkl","wb") as f:
	pickle.dump(observations,f)		