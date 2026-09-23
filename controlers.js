

function reset() {
	chart_svg.call(zoom.transform, d3.zoomIdentity); 
	filterAndSort(false)
}

/* 
 * when zoomBtn is clicked
 * reset chart 
 */
document.getElementById("zoomBtn").onclick = function(){
	reset()
}

/* 
 * when toggleBtn is clicked
 * collapse filter panel
 */
document.getElementById("toggleBtn").onclick = function(){
	document.getElementById("filterPanel").classList.toggle("collapsed")
	document.getElementById("toggleBtn").classList.toggle("button-active")
}

/*
 * when sortBy is changed 
 * reset chart
 */
document.getElementById("sortBy").onchange   = function(){
	reset()
}

/*
 * when filterBy is changed 
 * reset chart
 */
document.getElementById("filterByCorpus").onchange = function(){
	filterAndSort(true)
}

document.getElementById("filterByFst").onchange = function(){
	filterAndSort(true)
}

document.getElementById("filterByLst").onchange = function(){
	filterAndSort(true)
}

document.getElementById("filterByMig").onchange = function(){
	filterAndSort(true)
}

document.getElementById("max_duration").onchange = function(){
	filterAndSort(true)
}

document.getElementById("min_duration").onchange = function(){
	filterAndSort(true)
}
