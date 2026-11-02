#######
# metricsToPCA.py
# description : compute a PCA from a collection of ego networks' metrics
# licence : AGPL + CECILL v3
# author : quentin lobbé - quentin.lobbe@gmail.com
#######

import pickle
import pandas as pd
import prince
import matplotlib.pyplot as plt
import plotly.graph_objects as go
import plotly.express as px
from collections import defaultdict

print("\n• Process the PCA") 	

with open("structural_observations.pkl","rb") as f:
	structural_metrics = pickle.load(f)


map_type_to_matrix = {
	"maman" : "2",
	"amitié" : "1",
	"chat" : "1",
	"journal" : "1",
	"pensées" : "3",
	"critique" : "3",
	"militant" : "3",
	"professionnel" : "2",
	"galerie" : "5",
	"passion" : "4",
	"dessin" : "5",
	"fan" : "3",
	"laboratoire d'écriture" : "6",
	"poésie" : "6",
	"fan fiction" : "7",
	"fiction" : "7",
	"jeux de rôle" : "7",
	"troll" : "NA",
	"NA" : "NA"
}

full_data = defaultdict(list)
labels = []
types  = []

for metrics in structural_metrics :
	
	ego = metrics["name"]

	if metrics["type"] == "NA" :
		continue
	
	labels.append(metrics["id"])

	full_data["matrix"].append(map_type_to_matrix[metrics["type"]])
	full_data["type"].append(metrics["type"])
	full_data["density"].append(metrics["density"])
	full_data["size"].append(metrics["nb_nodes"])
	full_data["blocks"].append(metrics["nb_blocks"])
	full_data["nb_blocks_sup_3"].append(metrics["nb_blocks_sup_3"])
	full_data["nb_blocks_inf_3"].append(metrics["nb_blocks_inf_3"])
	full_data["size_biggest_block"].append(metrics["size_biggest_block"])
	full_data["diameter"].append(metrics["diameter"])
	full_data["modularity"].append(metrics["modularity"])
	full_data["triangles"].append(metrics["triangles"])
	full_data["reciprocity"].append(metrics["reciprocity"])
	full_data["betweenness_avg"].append(metrics["betweenness_avg"])
	full_data["clustering_mean"].append(metrics["clustering_mean"])
	full_data["bridging_avg"].append(metrics["bridging_avg"])
	full_data["edge_betweenness_avg"].append(metrics["edge_betweenness_avg"])

full_data = pd.DataFrame(full_data, index = labels)
data_pca = full_data.drop(columns=['type','matrix'])

pca = prince.PCA(
	n_components=3,
	n_iter=3,
	# rescale_with_mean=True,
	rescale_with_std=True,
	copy=True,
	check_input=True,
	engine='sklearn',
	random_state=42
)

pca = pca.fit(
	data_pca,
	sample_weight=None,
	column_weight=None,
	supplementary_columns=None
)

# colors
# types = full_data['type']
types = full_data['matrix']
facets = types.unique()
print(facets)
# colors = px.colors.qualitative.Plotly 
# Bluyl
# 1: #f7feae 2: #b7e6a5 3: #7ccba2 4: #46aea0 5: #089099 6: #00718b 7: #045275



# colors = ["#f7feae","#46aea0"]
colors = ['#045275','#089099','#f7feae','#b7e6a5','#46aea0','#00718b','#7ccba2']
map_facet_to_color = {facet: colors[i % len(colors)] for i, facet in enumerate(facets)}
map_facet_to_color = dict(sorted(map_facet_to_color.items()))

map_facet_to_label = {
	"1": 'Friendship, chat, diary',
	"2": 'Motherhood, professional',
	"3": 'Activist, reviews, thoughts, fan',
	"4": 'Passion',
	"5": 'Gallery, drawing',
	"6": 'Poetry, writing workshop',
	"7": 'Fiction, fan fiction, role-playing'
}

facets_sorted = list(map_facet_to_color)  # déjà trié
n = len(facets_sorted)
colorscale = [[i / (n - 1), map_facet_to_color[f]] for i, f in enumerate(facets_sorted)]


blog_coords = pca.row_coordinates(data_pca)
attr_coords = pca.column_coordinates_

print(pca.eigenvalues_summary)

fig = go.Figure()

# facet by facet, we print the blogs
for facet in facets:
	mask = types == facet
	fig.add_trace(go.Scatter(
		x=blog_coords[0][mask],
		y=blog_coords[1][mask],
		mode='markers',
		name=facet,
		showlegend=False,
		text=full_data.index[mask],
		hovertemplate='<b>%{text}</b><br>PC1: %{x:.3f}<br>PC2: %{y:.3f}<extra></extra>',
		marker=dict(color=map_facet_to_color[facet], size=13, opacity=0.8, line=dict(color='#272930',width=1.5))
	))

fig.add_trace(go.Scatter(
	x=[blog_coords[0].iloc[0]], y=[blog_coords[1].iloc[0]],
	mode='markers', showlegend=False, hoverinfo='skip',
	marker=dict(
		color=[0], colorscale=colorscale, cmin=0, cmax=n - 1, showscale=True,
		opacity=0, size=1,
		colorbar=dict(
			title=dict(text='<b>Entanglement Gradient</b><br> ', font=dict(size=13), side='top'),
			tickvals=list(range(n)),
			ticktext=[map_facet_to_label[f] for f in facets_sorted],
			thickness=20, len=0.8, y=0.5
		)
	)
))

# we print the pca attributes as arrows
fig.add_trace(go.Scatter(
	x=attr_coords[0],
	y=attr_coords[1],
	mode='markers+text',
	name='<b>Structural Variables</b>',
	text=attr_coords.index,
	textposition='top center',
	hovertemplate='<b>%{text}</b><br>PC1: %{x:.3f}<br>PC2: %{y:.3f}<extra></extra>',
	marker=dict(color='#dddddd', symbol='diamond', size=12, opacity=0.8, line=dict(color='#272930',width=1.5))))

# axis
fig.add_hline(y=0, line=dict(color='grey', dash='dash', width=1))
fig.add_vline(x=0, line=dict(color='grey', dash='dash', width=1))

# axis labels
fig.update_layout(
	xaxis_title='<b>component 0</b>',
	yaxis_title='<b>component 1</b>',
	# title='<b>ACP réseaux égocentrés Skyblogs</b>',
	template='simple_white'
)

fig.write_image("pca_ego_networks.svg",  width=1600, height=800, scale=1 )
fig.show()
